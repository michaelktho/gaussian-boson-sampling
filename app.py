"""Standalone Streamlit application for threshold Gaussian Boson Sampling."""
from __future__ import annotations
import atexit
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import numpy as np
import pandas as pd
import streamlit as st
from gbs_engine import EXAMPLE

st.set_page_config(page_title='Gaussian Boson Sampling | Weighted Densest Subgraph', page_icon='◈', layout='wide')
st.markdown('''<style>
.stApp{background:#f5f7fb;color:#172033}
.block-container{max-width:1180px;padding-top:1.4rem}
.gbs-head{background:linear-gradient(135deg,#172554,#3157c8);padding:35px 32px;border-radius:15px;color:white;margin-bottom:24px}
.gbs-head h1{color:#fff;font-size:clamp(1.8rem,3.2vw,2.6rem);margin:0 0 10px}
.gbs-head p{color:#dbe5ff;line-height:1.7;max-width:820px}
.credit{padding-top:15px;margin-top:17px;border-top:1px solid #ffffff33;display:inline-block;font-size:.86rem;color:#e1e8ff}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:15px}
a{color:#3157c8}
</style>''', unsafe_allow_html=True)
st.markdown('''<div class="gbs-head"><h1>Gaussian Boson Sampling for Weighted Densest Subgraph Search</h1>
<p>Explore undirected, non-negative weighted graphs using threshold Gaussian Boson Sampling.
Upload or enter an adjacency matrix, configure the sampling experiment and identify the
highest-density subgraph encountered during simulation.</p>
<div class="credit">DEVELOPED BY &nbsp; <strong>Dr. Michael Ho</strong></div></div>''', unsafe_allow_html=True)

# A subprocess, rather than a background thread, makes a long sampling call terminable.
# A supervisor daemon can enforce the timeout even while the page is rerunning.
JOB_ROOT = Path(tempfile.gettempdir()) / 'gbs_streamlit_jobs'
JOB_ROOT.mkdir(parents=True, exist_ok=True)


def snapshot(job: dict) -> dict:
    path = Path(job['snapshot'])
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def supervisor(proc: subprocess.Popen, deadline: float, snap: Path) -> None:
    remaining = deadline - time.monotonic()
    if remaining > 0:
        try:
            proc.wait(timeout=remaining)
            return
        except subprocess.TimeoutExpired:
            pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        # Preserve the latest completed batch's result.
        current = {}
        try:
            current = json.loads(snap.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            pass
        if current.get('status') == 'running':
            current.update(status='time_limit', phase='Time limit reached', message='Sampling stopped at the time limit. Last completed batch retained.')
            tmp = snap.with_suffix('.timeouttmp')
            tmp.write_text(json.dumps(current), encoding='utf-8')
            os.replace(tmp, snap)


def start_job(raw: bytes, config: dict) -> dict:
    folder = JOB_ROOT / uuid.uuid4().hex
    folder.mkdir(mode=0o700)
    source = folder / 'matrix.csv'
    source.write_bytes(raw)
    cfg = folder / 'config.json'
    cfg.write_text(json.dumps(config), encoding='utf-8')
    snap = folder / 'snapshot.json'
    log = folder / 'error.log'
    # The external process imports and runs The Walrus. No shared GBS state across users.
    proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('worker.py')),
                             str(source), str(cfg), str(snap), str(log)],
                            cwd=str(Path(__file__).parent),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    job = {'pid': proc.pid, 'process': proc, 'snapshot': str(snap),
           'folder': str(folder), 'started': time.monotonic(),
           'max_seconds': config['max_seconds'], 'samples': config['max_samples']}
    threading.Thread(target=supervisor, args=(proc, job['started'] + config['max_seconds'], snap), daemon=True).start()
    return job


def cancel_job(job: dict) -> None:
    proc = job['process']
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    s = snapshot(job)
    if s.get('status') == 'running':
        s.update(status='cancelled', phase='Cancelled', message='User cancelled the experiment. Last completed batch retained.')
        p = Path(job['snapshot'])
        temp = p.with_suffix('.cancelledtmp')
        temp.write_text(json.dumps(s), encoding='utf-8')
        os.replace(temp, p)


if 'job' not in st.session_state:
    st.session_state.job = None
if 'example' not in st.session_state:
    st.session_state.example = False

left, right = st.columns([1.05, .95], gap='large')
with left:
    with st.container(border=True):
        st.subheader('1. Adjacency matrix')
        st.write('Paste a square, symmetric matrix or upload a CSV/TXT file. Entries must be finite, non-negative numbers, and the diagonal must be zero. Uploaded files are not copied into the text editor.')
        uploaded = st.file_uploader('Upload adjacency matrix', type=['csv','txt'])
        if st.button('Load example', disabled=bool(st.session_state.job and st.session_state.job['process'].poll() is None)):
            st.session_state.example = True
        manual = st.text_area('Or paste adjacency matrix', value=EXAMPLE if st.session_state.example else '',
                              height=170, placeholder='0, 2, 1\n2, 0, 3\n1, 3, 0')
        if uploaded is not None:
            st.info(f'{uploaded.name} selected ({uploaded.size / 1024:.1f} KB). Matrix size will be reported after validation.')
    with st.container(border=True):
        st.subheader('2. GBS configuration')
        n_mean = st.number_input('Total mean photon number', min_value=0.01, value=4.0, step=1.0, help='Controls the sampling distribution, including the number of clicked modes. This does not impose a fixed subgraph size.')
        max_samples = st.number_input('Maximum sampling events', min_value=1, value=200, step=50)
        max_seconds = st.number_input('Maximum runtime (seconds)', min_value=1, value=120, step=30)
        batch_size = st.number_input('Sampling events per batch', min_value=1, max_value=25, value=1, help='A smaller batch provides more frequent progress snapshots. The worker may be stopped during a long call.')
        max_photons = st.number_input('Simulator maximum photons/clicks', min_value=1, value=30, step=5, help='The Walrus truncation parameter. It is not a maximum on graph vertices or a fixed-k requirement.')
        seed = st.number_input('Random seed', min_value=0, value=42, step=1)
        active = st.session_state.job is not None and st.session_state.job['process'].poll() is None
        c1,c2 = st.columns(2)
        with c1:
            run = st.button('Run Gaussian Boson Sampling', type='primary', disabled=active, use_container_width=True)
        with c2:
            stop = st.button('Cancel computation', disabled=not active, use_container_width=True)
        if stop and st.session_state.job:
            cancel_job(st.session_state.job)
            st.rerun()
        if run:
            raw = uploaded.getvalue() if uploaded is not None else manual.encode('utf-8')
            if not raw.strip():
                st.error('Please upload a CSV/TXT file or paste an adjacency matrix.')
            else:
                try:
                    st.session_state.job = start_job(raw, dict(n_mean=float(n_mean),max_samples=int(max_samples),
                        max_seconds=int(max_seconds),batch_size=int(batch_size),
                        max_photons=int(max_photons), seed=int(seed)))
                    st.rerun()
                except Exception as exc:
                    st.error(f'Unable to start the background process: {exc}')
        st.caption('Sampling runs in an independent process. A supervisor terminates it when the chosen runtime expires. Python memory and hosting limits still apply.')

with right:
    with st.container(border=True):
        st.subheader('Method')
        st.write('For a non-empty vertex set S, weighted density is **ρ(S) = W(S) / |S|**, where W(S) is the sum of undirected internal edge weights counted once.')
        st.write('The Walrus simulates **threshold Gaussian Boson Sampling**. Every detector click selects its corresponding vertex. All non-empty click patterns, regardless of their size, are evaluated using the original unscaled adjacency matrix.')
        st.write('The graph is internally scaled by The Walrus to obtain a valid Gaussian state with the requested mean photon number. The density objective itself is not rescaled.')
        st.info('This is a stochastic search. The highest sampled density is **not** a certificate of global optimality. A larger runtime or sample count does not guarantee improvement.')
    with st.container(border=True):
        st.subheader('3. Sampling progress and results')
        @st.fragment(run_every='1s')
        def live_results():
            job = st.session_state.job
            if job is None:
                st.caption('Upload a matrix and run a GBS experiment to see the results.')
                return
            state = snapshot(job)
            proc = job['process']
            if not state:
                if proc.poll() is None:
                    st.info('Starting simulator and validating data…')
                else:
                    st.error('Worker ended before producing a status report. Check server logs or try running locally.')
                return
            status = state.get('status','running')
            if proc.poll() is not None and status == 'running':
                status = 'failed'
                st.warning('Worker stopped unexpectedly; the last completed batch is preserved.')
            if status == 'running':
                st.info(f"Running: {state.get('phase', 'Preparing')}")
            elif status == 'completed':
                st.success('Requested sampling workload completed.')
            elif status == 'time_limit':
                st.warning('Maximum runtime reached. Last completed batch retained; no optimality claim is made.')
            elif status == 'cancelled':
                st.warning('Computation cancelled. Last completed batch retained.')
            else:
                st.error(state.get('error','Sampling process failed.'))
            samples = int(state.get('samples_attempted',0))
            elapsed = float(state.get('elapsed_seconds',max(0,time.monotonic()-job['started'])))
            st.progress(min(1.0, samples / job['samples']), text=f'{samples:,} / {job["samples"]:,} sampling events')
            st.caption(f'Elapsed time: {elapsed:.1f} seconds | Runtime limit: {job["max_seconds"]} seconds')
            if state.get('n'):
                st.write(f"**Matrix validated:** {state['n']:,} × {state['n']:,}")
            a,b = st.columns(2)
            a.metric('Original graph density', f"{state.get('original_density',0):.6g}" if 'original_density' in state else '–')
            b.metric('Best sampled density', f"{state['best_density']:.6g}" if state.get('best_density') is not None else '–')
            c,d=st.columns(2)
            c.metric('Non-empty samples', f"{state.get('samples_nonempty',0):,}")
            d.metric('Empty samples', f"{state.get('empty_samples',0):,}")
            vertices = state.get('best_vertices',[])
            if vertices:
                st.markdown(f"**Best sampled subgraph:** {len(vertices):,} vertices")
                st.write(', '.join(f'v{v}' for v in vertices[:60]) + (' …' if len(vertices)>60 else ''))
                csv='vertex_index,vertex_label\n' + '\n'.join(f'{v},v{v}' for v in vertices) + '\n'
                st.download_button('Download best vertex list (CSV)',csv,'gbs_selected_vertices.csv',mime='text/csv')
            else:
                st.caption('No non-empty sample has been evaluated yet.')
            if state.get('histogram'):
                hist=pd.DataFrame([{'Clicked vertices':int(k),'Frequency':v} for k,v in state['histogram'].items()]).sort_values('Clicked vertices')
                st.markdown('**Sampled subgraph sizes**')
                st.bar_chart(hist.set_index('Clicked vertices')['Frequency'])
            if state.get('improvements'):
                df=pd.DataFrame(state['improvements'])
                st.markdown('**Best-density improvements**')
                st.line_chart(df.set_index('sample')['density'])
            if status != 'running' and state.get('best_vertices'):
                result = dict(state)
                result.pop('improvements',None)
                st.download_button('Download experiment summary (JSON)',json.dumps(result,indent=2),
                                   'gbs_result.json',mime='application/json')
        live_results()

st.markdown('---')
st.subheader('References')
st.markdown('''The Walrus: Gupt, B., Izaac, J. and Quesada, N. (2019). *The Walrus: a library for the calculation of hafnians, Hermite polynomials and Gaussian boson sampling*. Journal of Open Source Software, 4(44), 1705. [https://doi.org/10.21105/joss.01705](https://doi.org/10.21105/joss.01705)''')
st.caption('Method reference: [The Walrus threshold graph-sampling documentation](https://the-walrus.readthedocs.io/en/stable/code/samples.html). This application performs classical GBS simulation, not sampling on quantum hardware.')
