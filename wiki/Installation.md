# Installation

## From PyPI

```bash
pip install tsauditor
```

Requires **Python ≥ 3.9**. Core dependencies: `pandas`, `numpy`, `scipy`, `statsmodels`, `rich`.

## Optional extras

Install only what you need:

```bash
pip install 'tsauditor[pdf]'      # PDF report export via GuardReport.to_pdf (matplotlib)
pip install 'tsauditor[polars]'   # polars DataFrame input (polars, pyarrow)
```

The **TimesFM adapter** (`tsauditor.adapters.to_timesfm`) needs no extra — it only produces a numpy array and never imports `timesfm`.

## Development setup

```bash
git clone https://github.com/imann128/tsauditor.git
cd tsauditor
pip install -e ".[dev]"
```

The `[dev]` extra adds the test and lint toolchain (`pytest`, `pytest-cov`, `ruff==0.15.18`, `matplotlib`, `polars`, `pyarrow`, `joblib`).

Run the suite:

```bash
pytest -q
```

CI runs the full suite across Python 3.9–3.14 on Linux, Windows, and macOS, and enforces `ruff format --check`.
