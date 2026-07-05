"""
Builder for beyond_price_direction/beyond_price_direction.ipynb.

Demonstrates that tsauditor is column-agnostic: it audits volume, a bounded
oscillator (RSI), and OHLC-bar ordering — not just price and direction — using
the VAL001/VAL002 validity checks on the *real* OGDC dataset already vendored in
examples/ogdc_leakage_case/.

Run:  python examples/beyond_price_direction/build_beyond_notebook.py
It writes the .ipynb next to this file and executes it to confirm it is clean.
"""

from __future__ import annotations

import pathlib

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "beyond_price_direction.ipynb"
CSV = "../ogdc_leakage_case/ogdc_with_regimes.csv"


def md(text: str):
    return new_markdown_cell(text)


def code(text: str):
    return new_code_cell(text)


cells = [
    md(
        "# Beyond price and direction\n"
        "\n"
        "A common misconception about tsauditor is that it only handles a `price`\n"
        "column and a `Direction` target. It doesn't — it is **column-agnostic**. This\n"
        "notebook audits three very different column types on the *real* OGDC dataset:\n"
        "\n"
        "* **Volume** — must be non-negative\n"
        "* **RSI** — a bounded oscillator, must sit in [0, 100]\n"
        "* **OHLC bars** — must satisfy `Low <= Open <= High` and `Low <= High`\n"
        "\n"
        "None of these are the target, and none involve leakage — they are *domain\n"
        "validity* rules (VAL001 bounds, VAL002 relations) that you declare and\n"
        "tsauditor verifies."
    ),
    code(
        "import pandas as pd\n"
        "import tsauditor as tsa\n"
        "\n"
        'df = pd.read_csv("' + CSV + '", index_col="Date", parse_dates=True)\n'
        'df = df.dropna(subset=["Direction"])\n'
        'print("rows:", len(df))\n'
        'print("RSI range:", round(df.RSI.min(), 1), "-", round(df.RSI.max(), 1))\n'
        'print("Volume min:", df.Volume.min())\n'
        'df[["Open", "High", "Low", "Volume", "RSI"]].head()'
    ),
    md(
        "## The rules, on clean real data\n"
        "\n"
        "We declare bounds for Volume and RSI, and ordering relations for the OHLC\n"
        "bars. Real, well-formed market data should satisfy all of them — so a specific\n"
        "auditor reports **nothing**. (An auditor that fired here would be crying wolf.)"
    ),
    code(
        "constraints = {\n"
        '    "bounds": {\n'
        '        "RSI": {"min": 0, "max": 100},\n'
        '        "Volume": {"min": 0},\n'
        "    },\n"
        '    "relations": [("Low", "High"), ("Low", "Open"), ("Open", "High")],\n'
        "}\n"
        "\n"
        "report = tsa.scan(df, constraints=constraints, run_stationarity=False)\n"
        'validity = report.filter(module="validity")\n'
        'print("validity issues on clean data:", len(validity))'
    ),
    md(
        "## Now inject three realistic feed glitches\n"
        "\n"
        "Exactly the kinds of corruption a live market feed produces — and each one is\n"
        "invisible to a price/direction-only mindset. We inject them into a **copy** and\n"
        "clearly label them, then run the same audit."
    ),
    code(
        "bad = df.copy()\n"
        "i = bad.index\n"
        'bad.loc[i[100], "Volume"] = -500_000.0   # impossible negative volume\n'
        'bad.loc[i[200], "RSI"] = 130.0            # RSI outside [0, 100]\n'
        'bad.loc[i[300], "High"] = bad.loc[i[300], "Low"] - 1.0  # crossed bar (High < Low)\n'
        "\n"
        "report = tsa.scan(bad, constraints=constraints, run_stationarity=False)\n"
        'for iss in report.filter(module="validity"):\n'
        "    ev = iss.evidence\n"
        '    if iss.code == "VAL002":\n'
        '        what = ev["low_col"] + " <= " + ev["high_col"] + " violated"\n'
        "    else:\n"
        '        what = iss.column + " out of bounds"\n'
        '    print(iss.severity.upper(), iss.code, "|", what, "| n =", ev["n_violations"])'
    ),
    md(
        "Three columns, three column *types*, all caught — and `Direction`/`price`\n"
        "leakage never entered the picture. VAL002 (the crossed bar) is CRITICAL; the\n"
        "out-of-range Volume and RSI are VAL001 warnings.\n"
        "\n"
        "For the other alternative-data column types — **macro** series with a publish\n"
        "lag (LEK004 as-of) and **sentiment** bounds — see\n"
        "[`../new_features_walkthrough.ipynb`](../new_features_walkthrough.ipynb).\n"
        "\n"
        "**Try it on your own data.** Any numeric time-series frame works — e.g. load a\n"
        "public CSV straight from GitHub and declare the rules your columns must obey:\n"
        "\n"
        "```python\n"
        'url = "https://raw.githubusercontent.com/<user>/<repo>/main/data.csv"\n'
        "df = pd.read_csv(url, index_col=0, parse_dates=True)\n"
        'tsa.scan(df, constraints={"bounds": {"my_ratio": {"min": 0, "max": 1}}})\n'
        "```"
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
