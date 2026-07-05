"""
Builder for validation_comparison/time_series_validation_vs_general_profiling.ipynb.

Contrasts a general-purpose data profiler (which treats rows as i.i.d.) with
tsauditor (which enforces the rules of time). Runs with only tsauditor + pandas —
the general-profiling baseline uses plain pandas summaries, so there is no
third-party profiling dependency.

Run:  python examples/validation_comparison/build_validation_notebook.py
It writes the .ipynb next to this file and executes it to confirm it is clean.
"""

from __future__ import annotations

import pathlib

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "time_series_validation_vs_general_profiling.ipynb"


def md(text: str):
    return new_markdown_cell(text)


def code(text: str):
    return new_code_cell(text)


cells = [
    md(
        "# Time-series validation vs general profiling\n"
        "\n"
        "General-purpose data profilers summarize each column in isolation — they treat\n"
        "rows as independent. **tsauditor** enforces the rules of *time*. This notebook\n"
        "builds one dataset with three flaws that look clean to a general profiler but\n"
        "are exactly what breaks a live model:\n"
        "\n"
        "1. **Data-feed outage** — a clustered block of missing values (not scattered).\n"
        "2. **Silent flash crash** — a value extreme *locally* but inside the global range.\n"
        "3. **Data leakage** — a same-day feature that reproduces the target.\n"
        "\n"
        "It runs with just `tsauditor` and `pandas` — no third-party profiler needed.\n"
        "\n"
        "Check out [tsauditor](https://github.com/imann128/tsauditor) on GitHub!"
    ),
    code(
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "rng = np.random.default_rng(42)\n"
        'dates = pd.date_range("2026-01-01", periods=200, freq="B")\n'
        "price = 100 + np.cumsum(rng.normal(0, 1, 200))\n"
        "\n"
        "df = pd.DataFrame(\n"
        '    {"Price": price, "Volume": rng.integers(10_000, 50_000, 200).astype(float)},\n'
        "    index=dates,\n"
        ")\n"
        "\n"
        "# 1. Feed outage: 6 consecutive missing days in Volume (a clustered gap).\n"
        'df.iloc[50:56, df.columns.get_loc("Volume")] = np.nan\n'
        "\n"
        "# 2. Flash crash: one point 30 below its neighbours but inside the global range.\n"
        'df.iloc[115, df.columns.get_loc("Price")] = price[115] - 30\n'
        "\n"
        "# 3. Leakage: a same-day % change whose sign defines the Direction target.\n"
        "ret = pd.Series(price, index=dates).pct_change()\n"
        'df["ChangeP"] = ret * 100\n'
        'df["Target"] = (ret > 0).astype(int)\n'
        "df.head()"
    ),
    md(
        "## Test 1 — a general profiler (pandas summaries)\n"
        "\n"
        "This is what column-in-isolation profiling sees. Nothing here is wrong, exactly —\n"
        "it just misses everything that matters about *time*."
    ),
    code(
        'print("Missing % per column:")\n'
        "print((df.isna().mean() * 100).round(1).to_string())\n"
        "\n"
        'print("\\nPrice — global describe:")\n'
        'print(df["Price"].describe().round(2).to_string())\n'
        "\n"
        'print("\\nCorrelation with Target:")\n'
        'print(df.corr(numeric_only=True)["Target"].round(3).to_string())'
    ),
    md(
        "**What the general view concludes — and misses:**\n"
        "\n"
        "- *Missing:* `Volume` is ~3% missing. Looks like a few scattered rows; it never\n"
        "  says the feed went **dark for a solid week**.\n"
        "- *Anomaly:* `Price` ranges ~70–120 globally, so a value of ~85 during the crash\n"
        "  sits comfortably inside the range and raises no flag. The **local** collapse is\n"
        "  invisible to a global histogram.\n"
        "- *Leakage:* `ChangeP` correlates ~0.80 with `Target`, which a profiler reports as\n"
        '  a "highly predictive feature" — praise for what is actually structural cheating.'
    ),
    md(
        "## Test 2 — tsauditor (time-aware)\n"
        "\n"
        "The same dataset, through the checks that reason about chronology."
    ),
    code(
        "from tsauditor.profiler.missing import audit_missing\n"
        "from tsauditor.anomaly.contextual import audit_contextual_anomalies\n"
        "from tsauditor.leakage.equivalence import audit_equivalence\n"
        "\n"
        "\n"
        "def show(issues):\n"
        "    for i in issues:\n"
        '        print(f"  [{i.severity.upper()}] {i.code} | {i.column} | {i.description}")\n'
        "\n"
        "\n"
        'print("Clustered feed outage (PRF002):")\n'
        'show([i for i in audit_missing(df, domain="finance") if i.code == "PRF002"])\n'
        "\n"
        'print("\\nLocal flash crash (ANO003):")\n'
        "show(\n"
        "    [\n"
        "        i\n"
        '        for i in audit_contextual_anomalies(df, domain="finance")\n'
        '        if i.code == "ANO003"\n'
        "    ]\n"
        ")\n"
        "\n"
        'print("\\nTarget leakage (LEK001):")\n'
        'show(audit_equivalence(df, target="Target"))'
    ),
    md(
        "## Why tsauditor wins\n"
        "\n"
        "A general profiler tells you what data *looks like* in a vacuum. tsauditor enforces\n"
        "the rules of time — catching **clustered outages (PRF002)**, **contextual\n"
        "disruptions (ANO003)**, and **target leakage (LEK001)** — so you don't ship a model\n"
        "that passes standard validation and then fails under live conditions.\n"
        "\n"
        'The full one-call version is just `tsa.scan(df, target="Target", domain="finance")`.'
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
