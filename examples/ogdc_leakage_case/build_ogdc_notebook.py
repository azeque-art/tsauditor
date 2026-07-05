"""
Builder for ogdc_leakage_case/ogdc_leakage.ipynb.

Generates (and, when run directly, executes) a notebook that reproduces the
flagship leakage case on real OGDC equity data: tsauditor's LEK001 catching the
same-day features that reproduce the Direction target, and why a rank/AUC test
catches what a Pearson threshold misses.

Run:  python examples/ogdc_leakage_case/build_ogdc_notebook.py
It writes the .ipynb next to this file and executes it to confirm it is clean.
"""

from __future__ import annotations

import pathlib

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "ogdc_leakage.ipynb"


def md(text: str):
    return new_markdown_cell(text)


def code(text: str):
    return new_code_cell(text)


cells = [
    md(
        "# OGDC leakage case — the bug tsauditor was built to catch\n"
        "\n"
        "A direction-prediction model on Pakistani equity (OGDC) data reached ~99.7%\n"
        "accuracy — almost entirely because a same-day percentage-change feature\n"
        "(`ChangeP`) was mathematically near-identical to the `Direction` target it was\n"
        "meant to predict. This notebook shows `tsauditor` catching that leak directly\n"
        "from the data, and why the rank/AUC test succeeds where a Pearson threshold\n"
        "would have missed it.\n"
        "\n"
        "The full model comparison (accuracy with vs. without the leak) lives in\n"
        "`compare_leakage.py` in this folder; here we focus on detection."
    ),
    code(
        "import pandas as pd\n"
        "import tsauditor as tsa\n"
        "\n"
        "df = pd.read_csv('ogdc_with_regimes.csv', index_col='Date', parse_dates=True)\n"
        "df = df.dropna(subset=['Direction'])\n"
        "print('rows:', len(df), '| columns:', len(df.columns))\n"
        "print('target: Direction (binary up/down)')\n"
        "df[['Price', 'ChangeP', 'Returns', 'Direction']].head()"
    ),
    md(
        "## Audit for leakage\n"
        "\n"
        "One call. `leaky_columns()` is the shortlist of features to review or remove\n"
        "before training."
    ),
    code(
        "report = tsa.scan(df, target='Direction', domain='finance', run_stationarity=False)\n"
        "\n"
        "print('critical:', len(report.critical), '| warnings:', len(report.warnings))\n"
        "print('leaky_columns:', report.leaky_columns())"
    ),
    md(
        "`ChangeP` and `Returns` are both **same-day** quantities whose sign *defines*\n"
        "`Direction`, so they reproduce the target. tsauditor flags them **LEK001**\n"
        "(CRITICAL, target equivalence):"
    ),
    code(
        "for i in report.filter(code='LEK001'):\n"
        "    print(i.column, '| metric:', i.evidence['metric'],\n"
        "          '| separation:', i.evidence['separation'])\n"
        "    print('   suggestion:', i.suggestion)\n"
        "    print()"
    ),
    md(
        "## Why Pearson would have missed it\n"
        "\n"
        "`Direction` is binary (0/1). Pearson correlation against a binary target is\n"
        "*point-biserial*, which is capped near `sqrt(2/pi) ~ 0.798` — it can never reach\n"
        "1.0 no matter how perfectly the feature defines the target's sign. So a\n"
        "correlation-threshold detector under-rates the leak (below you'll see `ChangeP`\n"
        "score well under the ceiling), while AUC separation scores it 1.0."
    ),
    code(
        "pearson = abs(df['ChangeP'].corr(df['Direction'].astype(float)))\n"
        "auc_sep = next(i for i in report.filter(code='LEK001')\n"
        "               if i.column == 'ChangeP').evidence['separation']\n"
        "print(f'ChangeP vs Direction  Pearson |r| = {pearson:.3f}  (point-biserial ceiling ~0.798)')\n"
        "print(f'ChangeP vs Direction  AUC sep     = {auc_sep:.3f}  (catches it cleanly)')"
    ),
    md(
        "## The measured impact\n"
        "\n"
        "Removing the leaked features (`ChangeP`, `Returns`, and the same-day `Open`/\n"
        "`High`/`Low`, which are equally unavailable at prediction time) collapses the\n"
        "headline accuracy — the number was mostly an artifact of the leak:\n"
        "\n"
        "| Model | With leakage | Without leakage |\n"
        "|-------|--------------|-----------------|\n"
        "| Random Forest | 99.68% (AUC 0.9987) | 69.81% (AUC 0.7795) |\n"
        "| Gradient Boosting | 99.68% (AUC 0.9967) | 73.70% (AUC 0.8072) |\n"
        "\n"
        "Run `python compare_leakage.py` in this folder to reproduce the full experiment\n"
        "(requires scikit-learn).\n"
        "\n"
        "**Takeaway:** a single `tsa.scan(...)` before training surfaces `leaky_columns()`\n"
        "so this class of mistake never reaches the model."
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
