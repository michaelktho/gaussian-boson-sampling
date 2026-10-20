# Gaussian Boson Sampling for Weighted Densest Subgraph Search

A standalone Streamlit research application built with [The Walrus](https://the-walrus.readthedocs.io/en/stable/) to evaluate **threshold Gaussian Boson Sampling (GBS)** outcomes as candidate weighted densest subgraphs.

**This is classical simulation of GBS**, not access to quantum hardware and not an exact densest-subgraph algorithm.

## Scientific definition

For undirected, non-negative weighted adjacency matrix `A`, the density of a non-empty selected vertex set `S` is

\[ \rho(S) = \frac{1}{|S|} \sum_{i<j,\,i,j\in S} A_{ij}. \]

Every threshold detector click selects its graph vertex. No fixed `k` is imposed: all non-empty click patterns are considered. The original adjacency matrix is used to calculate the density; graph-state scaling is handled by The Walrus.

The number of selected vertices depends on the GBS distribution, mean photon number and numerical truncation. Samples can be empty. The result is **the best sampled density**, not a certified global optimum. Optimising over the sample set is not equivalent to exact graph optimisation.

## Files

- `app.py`: Streamlit interface, results and timeout supervision.
- `worker.py`: independent Python sampling process, atomic progress snapshots and exception handling.
- `gbs_engine.py`: matrix validation, graph density and click-to-vertex mapping.
- `requirements.txt`: dependencies.
- `.streamlit/config.toml`: interface theme.
- `tests/test_engine.py`: simple mathematical and validation tests.
- `SETUP_GUIDE.md`: installation and GitHub deployment instructions.

## Local installation

Use **Python 3.11 or 3.12**, preferably in a fresh environment.

```bash
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

## Execution and stopping

A new sampling run starts a separate Python subprocess. A background supervisor terminates the subprocess after the chosen wall-clock time. Each completed batch writes an atomic JSON snapshot, preserving the best outcome even if a later batch is interrupted. Users can cancel active work. Note that operating-system scheduling and termination add small timing overhead, and a killed batch is not retained. The timeout covers process startup and input preparation as well as sampling.

**No fixed vertex-count ceiling is imposed in the code.** The matrix still requires O(n²) storage and GBS simulation can be much more expensive. Insufficient memory or deployment limits may interrupt large runs. The `max_photons` input is a simulator-specific truncation parameter, not a vertex limit or a prescribed `k`.

For initial trials use the included 6×6 example, 4 mean photons, 5–20 sampling events and a 120-second timeout. First-run JIT compilation can take noticeable time. Increase parameters gradually.

## Deployment

Create a separate GitHub repository and push these files **including the hidden `.streamlit` directory**. On [Streamlit Community Cloud](https://share.streamlit.io), create an app from this repository with entrypoint `app.py` and preferably Python 3.11 or 3.12. The platform will install `requirements.txt`.

Community Cloud has shared-hosting resource limits. A local or dedicated Python host may be necessary for larger GBS simulations. Verify that your chosen hosting platform permits child processes and process termination. Each browser session can start a worker, so a production multi-user deployment also requires concurrency quotas, authentication or usage controls.

## Reference

Gupt, B., Izaac, J. and Quesada, N. (2019). The Walrus: a library for the calculation of hafnians, Hermite polynomials and Gaussian boson sampling. *Journal of Open Source Software*, 4(44), 1705. https://doi.org/10.21105/joss.01705

API reference: https://the-walrus.readthedocs.io/en/stable/code/samples.html
