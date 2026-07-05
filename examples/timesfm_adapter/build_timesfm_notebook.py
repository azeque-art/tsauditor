"""
Builder for timesfm_adapter/timesfm_adapter.ipynb.

Demonstrates tsauditor.adapters.to_timesfm: auditing, repairing, and formatting a
raw price series into the finite float32 array Google TimesFM expects — including
the finiteness guard and context-window truncation — on the real OGDC dataset.
Adds no ``timesfm`` dependency; the model call is shown but not executed.

Run:  python examples/timesfm_adapter/build_timesfm_notebook.py
It writes the .ipynb next to this file and executes it to confirm it is clean.
"""

from __future__ import annotations

import pathlib

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "timesfm_adapter.ipynb"
CSV = "../ogdc_leakage_case/ogdc_with_regimes.csv"


def md(text: str):
    return new_markdown_cell(text)


def code(text: str):
    return new_code_cell(text)


cells = [
    md(
        "# The TimesFM adapter: messy data -> forecast-ready array\n"
        "\n"
        "Zero-shot forecasters like [Google TimesFM](https://github.com/google-research/timesfm)\n"
        "tokenize a clean, contiguous, finite context window. A raw series with gaps or\n"
        "outliers makes tokenization fail. `tsa.adapters.to_timesfm()` audits, repairs, and\n"
        "returns a plain `float32` numpy array — and **verifies it is finite** before\n"
        "returning, so a NaN never reaches the model.\n"
        "\n"
        "It adds **no `timesfm` dependency**: the adapter only produces numpy; the model\n"
        "call stays in your code. Here we use the real OGDC `Price` series."
    ),
    code(
        "import numpy as np\n"
        "import pandas as pd\n"
        "import tsauditor as tsa\n"
        "\n"
        'raw = pd.read_csv("' + CSV + '", index_col="Date", parse_dates=True)\n'
        'price = raw[["Price"]].dropna()\n'
        "\n"
        "# A realistic mess: a data-feed gap and a fat outlier.\n"
        "dirty = price.copy()\n"
        "dirty.iloc[50:60] = np.nan          # 10-row collection gap\n"
        "dirty.iloc[200] = dirty.iloc[200] * 5  # fat outlier\n"
        'print("rows:", len(dirty), "| NaNs:", int(dirty["Price"].isna().sum()))'
    ),
    md(
        "## One call: audit + repair + format\n"
        "\n"
        "`return_report=True` also hands back the `GuardReport`, so the repair is never a\n"
        "black box — you can see exactly what was cleaned."
    ),
    code(
        "array, report = tsa.adapters.to_timesfm(\n"
        '    dirty, target_col="Price", domain="finance", return_report=True\n'
        ")\n"
        "\n"
        'print("dtype        :", array.dtype)\n'
        'print("input rows   :", len(dirty))\n'
        'print("array length :", len(array), "(truncated to the most recent context_len)")\n'
        'print("all finite   :", bool(np.isfinite(array).all()))\n'
        'print("repaired      :", sorted({e["action"] for e in report.last_fixes}))'
    ),
    md(
        "The 1537-row series comes back as a **1024-point** array — the adapter keeps the\n"
        "most recent `context_len` points (default 1024; raise it for more history, TimesFM\n"
        "2.5 handles up to 16k). The gap and the outlier are gone, and the array is finite."
    ),
    md(
        "## The safety net: it refuses to emit a NaN\n"
        "\n"
        "Repair only touches *flagged* problems. A lone, unclustered NaN isn't flagged, so\n"
        "it would survive — and silently crash tokenization. The adapter checks finiteness\n"
        "and raises instead, telling you to look before you forecast."
    ),
    code(
        "stray = price.copy()\n"
        "stray.iloc[500] = np.nan   # a single, unflagged NaN\n"
        "\n"
        "try:\n"
        '    tsa.adapters.to_timesfm(stray, target_col="Price")\n'
        "except ValueError as e:\n"
        '    print("raised as expected:")\n'
        '    print(" ", str(e)[:130], "...")'
    ),
    md(
        "## Handing the array to TimesFM\n"
        "\n"
        "With `pip install timesfm[torch]`, the model call looks like this (left un-run\n"
        "here so the notebook needs only tsauditor):\n"
        "\n"
        "```python\n"
        "import timesfm\n"
        "\n"
        "model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(\n"
        '    "google/timesfm-2.5-200m-pytorch"\n'
        ")\n"
        "model.compile(timesfm.ForecastConfig(max_context=1024, max_horizon=64))\n"
        "\n"
        "point_forecast, quantiles = model.forecast(horizon=24, inputs=[array])\n"
        "```\n"
        "\n"
        "The separation is the point: tsauditor owns the messy-data step and guarantees a\n"
        "finite array; TimesFM owns the forecast."
    ),
]

nb = new_notebook(cells=cells)
nb.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
nb.metadata["language_info"] = {"name": "python"}

nbformat.write(nb, OUT)
print("wrote", OUT)

if __name__ == "__main__":
    from nbclient import NotebookClient

    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(HERE)}},
    )
    client.execute()
    nbformat.write(nb, OUT)
    print("executed and re-wrote", OUT)
