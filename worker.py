"""Run The Walrus in a separate OS process and save resumable progress snapshots.

Usage: python worker.py INPUT CONFIG SNAPSHOT LOG
"""
from __future__ import annotations
import json
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
import numpy as np
from gbs_engine import parse_matrix, all_graph_density, density, sample_vertices


def publish(path: Path, state: dict) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)


def run(source: Path, cfg: dict, snapshot: Path) -> None:
    start = time.monotonic()
    max_seconds = float(cfg['max_seconds'])
    total_samples = int(cfg['max_samples'])
    batch = int(cfg['batch_size'])
    n_mean = float(cfg['n_mean'])
    max_photons = int(cfg['max_photons'])
    seed = int(cfg['seed'])
    # Older The Walrus releases use the NumPy global RNG for sampling.
    np.random.seed(seed)
    state = dict(status='running', phase='Validating uploaded matrix', samples_attempted=0,
                 samples_nonempty=0, empty_samples=0, best_vertices=[], best_density=None,
                 best_weight=None, histogram={}, improvements=[], elapsed_seconds=0.0,
                 message='Preparing GBS simulation')
    publish(snapshot, state)
    matrix = parse_matrix(source.read_bytes())
    n = matrix.shape[0]
    original = all_graph_density(matrix)
    state.update(n=n, original_density=original, phase='Sampling with The Walrus')
    if not np.any(matrix):
        raise ValueError('The adjacency matrix contains no positive edge weights. A non-vacuum graph-encoded GBS state cannot be constructed from an all-zero graph.')
    publish(snapshot, state)
    from thewalrus.samples import torontonian_sample_graph
    histogram = Counter()
    # No fixed k is imposed. Every nonempty click pattern is a candidate.
    while state['samples_attempted'] < total_samples:
        if time.monotonic() - start >= max_seconds:
            state['status'] = 'time_limit'
            break
        count = min(batch, total_samples - state['samples_attempted'])
        # max_photons is a simulation truncation parameter, not a vertex limit.
        result = np.asarray(torontonian_sample_graph(
            matrix, n_mean=n_mean, samples=count,
            max_photons=max_photons, parallel=False
        ))
        if result.ndim == 1:
            result = result.reshape(1, -1)
        if result.shape[1] != n:
            raise RuntimeError(f'The Walrus returned {result.shape[1]} modes, expected {n}.')
        for row in result:
            vertices = sample_vertices(row)
            state['samples_attempted'] += 1
            size = int(len(vertices))
            histogram[size] += 1
            if size == 0:
                state['empty_samples'] += 1
                continue
            state['samples_nonempty'] += 1
            val = density(matrix, vertices)
            if state['best_density'] is None or val > state['best_density'] + 1e-12:
                state['best_density'] = val
                state['best_weight'] = val * size
                state['best_vertices'] = (vertices + 1).tolist()
                state['improvements'].append({'sample': state['samples_attempted'], 'density': val})
        state.update(histogram={str(k): v for k, v in sorted(histogram.items())},
                     elapsed_seconds=time.monotonic() - start,
                     message=f"Processed {state['samples_attempted']:,} of {total_samples:,} sampling events")
        publish(snapshot, state)
    if state['status'] == 'running':
        state['status'] = 'completed'
    state['elapsed_seconds'] = time.monotonic() - start
    state['phase'] = 'Finished'
    publish(snapshot, state)


def main() -> None:
    source, config, snapshot, log = map(Path, sys.argv[1:5])
    try:
        run(source, json.loads(config.read_text(encoding='utf-8')), snapshot)
    except Exception as exc:
        # Preserve the last good result, even if a subsequent sampling call fails.
        try:
            state = json.loads(snapshot.read_text(encoding='utf-8')) if snapshot.exists() else {}
        except (OSError, ValueError):
            state = {}
        state.update(status='failed', phase='Failed', error=str(exc))
        publish(snapshot, state)
        log.write_text(traceback.format_exc(), encoding='utf-8')
        sys.exit(1)

if __name__ == '__main__':
    main()
