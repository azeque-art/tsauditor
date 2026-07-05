"""
Builder for examples/new_features_walkthrough.ipynb.

Generates (and, when run directly, executes) a notebook that demonstrates the
features added on top of the core scan/anomaly/leakage engine:

  * LEK004 — as-of / point-in-time availability leakage
  * VAL001/VAL002 — domain-validity checks (bounds + relations)
  * tsa.fix() — one-shot scan-and-repair returning (clean_df, report)
  * tsa.adapters.to_timesfm() — the messy-data -> TimesFM-array bridge

Run:  python examples/build_new_features_notebook.py
It writes the .ipynb next to this file and executes it to confirm it is clean.
"""

from __future__ import annotations

import pathlib

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "new_features_walkthrough.ipynb"


def md(text: str):
    return new_markdown_cell(text)


def code(text: str):
    return new_code_cell(text)


cells = [
    md(
        "# tsauditor — production-hardening walkthrough\n"
        "\n"
        "This notebook demonstrates four additions that take tsauditor from a\n"
        "leakage detector toward a production data guard:\n"
        "\n"
        "1. **LEK004 — as-of / point-in-time leakage**: a value used before it was\n"
        "   published (macro releases, sentiment, earnings).\n"
        "2. **Validity checks (VAL001/VAL002)**: values that are *definitionally*\n"
        "   wrong — a non-positive spread, a sentiment score outside [-1, 1], a\n"
        "   crossed order book.\n"
        "3. **`tsa.fix()`**: one-shot scan-and-repair returning `(clean_df, report)`,\n"
        "   so the audit trail is never discarded and the original is never touched.\n"
        "4. **`tsa.adapters.to_timesfm()`**: audit + repair + format a series into the\n"
        "   finite float32 array Google TimesFM expects.\n"
        "\n"
        "Everything here runs with just `tsauditor` installed — no `timesfm` needed."
    ),
    code(
        "import numpy as np\n"
        "import pandas as pd\n"
        "import tsauditor as tsa\n"
        "\n"
        "print('tsauditor', tsa.__version__)"
    ),
    md(
        "## A deliberately messy market frame\n"
        "\n"
        "We build a small daily frame with one problem per feature so each check has\n"
        "something to find:\n"
        "\n"
        "* `price` — a clustered missing gap and a single fat outlier\n"
        "* `cpi` — a macro series aligned to its *reference* date but published ~30\n"
        "  days later (the as-of trap)\n"
        "* `bid` / `ask` — mostly well-ordered, with a couple of crossed-book rows\n"
        "* `sentiment` — meant to live in [-1, 1], with a couple of out-of-range values"
    ),
    code(
        "idx = pd.date_range('2021-01-01', periods=300, freq='B')\n"
        "rng = np.random.default_rng(7)\n"
        "\n"
        "price = 100 + np.cumsum(rng.normal(0, 1, 300))\n"
        "price[120] = price[120] + 60          # fat outlier\n"
        "price[40:50] = np.nan                 # clustered gap\n"
        "\n"
        "cpi = np.repeat(np.linspace(2.0, 5.0, 30), 10)   # stepwise macro series\n"
        "\n"
        "bid = 100 + rng.normal(0, 0.5, 300)\n"
        "ask = bid + rng.uniform(0.02, 0.10, 300)          # ask above bid...\n"
        "ask[[75, 210]] = bid[[75, 210]] - 0.05            # ...except two crossed rows\n"
        "\n"
        "sentiment = rng.uniform(-0.8, 0.8, 300)\n"
        "sentiment[[15, 250]] = [1.7, -2.1]                # out of [-1, 1]\n"
        "\n"
        "df = pd.DataFrame(\n"
        "    {'price': price, 'cpi': cpi, 'bid': bid, 'ask': ask, 'sentiment': sentiment},\n"
        "    index=idx,\n"
        ")\n"
        "df.head()"
    ),
    md(
        "## 1. As-of leakage (LEK004)\n"
        "\n"
        "CPI for a reference month is only released a few weeks later. If the series is\n"
        "aligned to the reference date and used on that date, every row before the real\n"
        "release consumes future information. tsauditor cannot know publication dates on\n"
        "its own, so you declare them — here as a fixed 30-day publication lag.\n"
        "\n"
        "A `pd.Timedelta` says *the value at each row became available 30 days later*,\n"
        "so an unshifted column is used early on every row. (For a real ragged release\n"
        "calendar, pass a `pd.Series` of per-row publish timestamps instead.)"
    ),
    code(
        "report = tsa.scan(\n"
        "    df,\n"
        "    available_at={'cpi': pd.Timedelta(days=30)},\n"
        "    run_stationarity=False,\n"
        ")\n"
        "\n"
        "for i in report.filter(code='LEK004'):\n"
        "    print(i.code, '-', i.column)\n"
        "    print('  ', i.description)\n"
        "    print('  evidence:', i.evidence)"
    ),
    md(
        "The fix is **not** to drop `cpi` — it is to shift it to its release schedule so\n"
        "each value is only used on or after it was published. The suggestion says so:"
    ),
    code("next(s for s in report.suggestions() if s['code'] == 'LEK004')"),
    md(
        "## 2. Domain-validity checks (VAL001 / VAL002)\n"
        "\n"
        "These catch values that are impossible rather than merely surprising. You declare\n"
        "the rules; tsauditor verifies them.\n"
        "\n"
        "* `bounds` — per-column limits (sentiment must be within [-1, 1])\n"
        "* `relations` — ordered `(low, high)` pairs; `('bid', 'ask')` must hold every row,\n"
        "  so a crossed book (ask < bid) is flagged CRITICAL."
    ),
    code(
        "report = tsa.scan(\n"
        "    df,\n"
        "    constraints={\n"
        "        'bounds': {'sentiment': {'min': -1, 'max': 1}},\n"
        "        'relations': [('bid', 'ask')],\n"
        "    },\n"
        "    run_stationarity=False,\n"
        ")\n"
        "\n"
        "for i in report.filter(module='validity'):\n"
        "    print(i.severity.upper(), i.code, '-', i.column, '| n=', i.evidence['n_violations'])\n"
        "\n"
        "# Validity issues are data errors, not leakage:\n"
        "print('leaky_columns:', report.leaky_columns())"
    ),
    md(
        "## 3. One-shot repair with `tsa.fix()`\n"
        "\n"
        "`tsa.fix()` scans and repairs in a single call and returns **both** the cleaned\n"
        "copy and the report, so you keep the audit trail. The original frame is never\n"
        "modified — it is your backup."
    ),
    code(
        "clean, fix_report = tsa.fix(df, domain='finance')\n"
        "\n"
        "print('original still has the gap? ', df['price'].isna().sum(), 'NaNs')\n"
        "print('cleaned gap filled?       ', clean['price'].isna().sum(), 'NaNs')\n"
        "print('original is untouched:    ', not clean.equals(df))\n"
        "print()\n"
        "print('change log (report.last_fixes):')\n"
        "for entry in fix_report.last_fixes:\n"
        "    print('  ', entry['column'], '->', entry['action'], '(', entry['cells_changed'], 'cells )')"
    ),
    md(
        "Because imputed values are *estimates*, the log matters: it tells you exactly\n"
        "which cells were fabricated so you can decide whether to trust them downstream."
    ),
    md(
        "## 4. The TimesFM bridge: `tsa.adapters.to_timesfm()`\n"
        "\n"
        "Zero-shot forecasters like Google TimesFM tokenize a clean, contiguous, finite\n"
        "context window; a raw series with gaps makes tokenization fail. The adapter\n"
        "audits, repairs, and returns a plain `float32` array — and **verifies it is\n"
        "finite** before returning, so a NaN never reaches the model.\n"
        "\n"
        "Note it cleans the target series as an ordinary column (it is the thing you\n"
        "forecast), unlike `fix(target=...)` which protects a label."
    ),
    code(
        "array, prep_report = tsa.adapters.to_timesfm(\n"
        "    df, target_col='price', domain='finance', context_len=1024, return_report=True\n"
        ")\n"
        "\n"
        "print('dtype      :', array.dtype)\n"
        "print('shape      :', array.shape)\n"
        "print('all finite :', bool(np.isfinite(array).all()))\n"
        "print('repaired   :', [e['column'] for e in prep_report.last_fixes])"
    ),
    md(
        "### Handing the array to TimesFM\n"
        "\n"
        "The adapter adds no `timesfm` dependency, so the model call lives in your code.\n"
        "With `pip install timesfm[torch]` it looks like this (left un-run here):\n"
        "\n"
        "```python\n"
        "import timesfm\n"
        "\n"
        "model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(\n"
        "    'google/timesfm-2.5-200m-pytorch'\n"
        ")\n"
        "model.compile(timesfm.ForecastConfig(max_context=1024, max_horizon=64))\n"
        "\n"
        "point_forecast, quantiles = model.forecast(horizon=24, inputs=[array])\n"
        "```\n"
        "\n"
        "`context_len` / `min_context` in the adapter are your knobs, not TimesFM\n"
        "constants — TimesFM 2.5 accepts a wide range of context lengths (up to 16k).\n"
        "Verify the settings for the model version you target."
    ),
    md(
        "## Recap\n"
        "\n"
        "| Concern | Entry point | Code |\n"
        "|---|---|---|\n"
        "| Value used before release | `scan(available_at=...)` | LEK004 |\n"
        "| Impossible / out-of-range values | `scan(constraints=...)` | VAL001 / VAL002 |\n"
        "| One-shot repair + audit trail | `tsa.fix(df)` | — |\n"
        "| Forecast-ready array | `tsa.adapters.to_timesfm(df, col)` | — |\n"
        "\n"
        "All checks are opt-in and declarative: tsauditor never guesses release dates or\n"
        "validity rules, and never edits your data unless you ask it to."
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

    client = NotebookClient(nb, timeout=300, kernel_name="python3")
    client.execute()
    nbformat.write(nb, OUT)
    print("executed and re-wrote", OUT)
