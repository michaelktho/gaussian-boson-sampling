# Step-by-step setup and deployment

## Part A. Download and inspect

1. Download `gaussian-boson-sampling.zip` from ChatGPT.
2. Extract it into a folder called `gaussian-boson-sampling`.
3. Confirm `app.py`, `worker.py`, `gbs_engine.py`, `requirements.txt`, `README.md`, `.gitignore`, `tests/`, and `.streamlit/config.toml` exist.
4. Keep these files together; do not upload `app.py` alone.

## Part B. First test on your computer (strongly recommended)

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/. During Windows installation, enable **Add Python to PATH** if offered.
2. Open Terminal (macOS/Linux) or PowerShell (Windows).
3. Change to the unzipped folder, e.g. `cd path/to/gaussian-boson-sampling`.
4. Create a virtual environment: `python -m venv .venv` (on some Macs/Linux systems, use `python3`).
5. Activate it:
   - Windows PowerShell: `.venv\Scripts\Activate.ps1`
   - macOS/Linux: `source .venv/bin/activate`
6. Install dependencies: `python -m pip install --upgrade pip` then `python -m pip install -r requirements.txt`.
7. Check tests: `python -m unittest discover -s tests -v`.
8. Launch: `streamlit run app.py`.
9. In your browser, select **Load example**, then set max sampling events to **5**, runtime **120 seconds**, total mean photon number **4**, and click **Run Gaussian Boson Sampling**. The first call may compile numerical code, so allow time.
10. Confirm that the app reports the validated matrix size, a sample count and, if a non-empty outcome is returned, a best sampled density. Test cancellation separately.

## Part C. New GitHub repository

1. Sign in to https://github.com and choose **New repository**.
2. Name it `gaussian-boson-sampling` (or another name).
3. Set visibility to **Public** if you want straightforward public deployment. You may choose Private if supported by your hosting arrangement.
4. Create the repository. Do not add the old greedy-peeling or exact-optimisation HTML files; this is a separate project.
5. Click **Add file → Upload files** and upload all project files. GitHub's browser upload UI may not easily upload hidden directories. If `.streamlit/config.toml` is omitted, create the `.streamlit` folder via the GitHub file editor or use Git on your computer.
6. Commit to your main branch. Do **not** upload `.venv`, temporary matrices, result files, credentials or personal datasets.

**Alternative using Git (from the extracted project folder):**

```bash
git init
git add .
git commit -m "Initial Streamlit GBS application"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/gaussian-boson-sampling.git
git push -u origin main
```

The remote repository must already exist, and GitHub authentication may be required.

## Part D. Deploy to Streamlit Community Cloud

1. Visit https://share.streamlit.io and sign in.
2. Click **Create app** (or equivalent create/deploy control).
3. Choose **Deploy from GitHub**, and select your new repository.
4. Branch: `main`.
5. Main file path / entrypoint: `app.py`.
6. In advanced settings, select Python **3.11 or 3.12** to match your local testing environment.
7. Deploy. The service should install dependencies from `requirements.txt`.
8. Open the generated `*.streamlit.app` URL and run the small example.
9. If the build fails, read **Manage app → Logs** and check package installation, Python version and hosting process restrictions.
10. Future edits to the GitHub repository can be redeployed automatically by Streamlit Community Cloud.

## Part E. Operating advice

- **Maximum runtime** bounds computation wall-clock time, including worker startup and data validation. It is a practical ceiling, not a guaranteed exact millisecond cutoff.
- **Sampling events** sets a second stopping condition. A run finishes on whichever is met first.
- **Batch size 1** saves after each returned sampling call; larger batches have less frequent checkpoints.
- **Mean photon number** changes the sampled-click distribution, not the density formula.
- **Simulator maximum photons/clicks** is a truncation setting inside The Walrus. It is not a graph vertex ceiling.
- Do not assume very large graphs will fit in RAM or finish sampling in time. No arbitrary vertex count is rejected by the app, but physical memory and computational complexity still apply.
- For a busy public app, dedicated hosting and user/job concurrency limits are strongly recommended.

## Known validation limitation

The core mathematical tests have been run, but the original development environment did not have Streamlit or The Walrus installed. Run the small end-to-end test above before relying on the application for research calculations. Inspect The Walrus dependency compatibility if installation fails.
