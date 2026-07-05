# Beyond price and direction

Concrete proof that `tsauditor` is **column-agnostic** — it audits far more than a
`price` column and a `Direction` target.

Using the *real* OGDC dataset (reused from
[`../ogdc_leakage_case`](../ogdc_leakage_case)), `beyond_price_direction.ipynb` declares
domain-validity rules for three very different column types and verifies them:

| Column | Rule | Check |
|--------|------|-------|
| `Volume` | non-negative | VAL001 bound |
| `RSI` | bounded oscillator, `[0, 100]` | VAL001 bound |
| `Open` / `High` / `Low` | `Low <= Open <= High`, `Low <= High` | VAL002 relations |

The notebook first runs the rules on the clean real data — which reports **nothing**
(the auditor is specific, not trigger-happy) — then injects three clearly-labelled feed
glitches (a negative volume, an RSI of 130, a crossed bar) into a copy and shows each one
caught. None of it involves the target or leakage.

For the remaining alternative-data column types — **macro** series with a publication lag
(LEK004 as-of) and **sentiment** bounds — see
[`../new_features_walkthrough.ipynb`](../new_features_walkthrough.ipynb).

## Run / regenerate

```bash
python examples/beyond_price_direction/build_beyond_notebook.py
```

Writes and executes `beyond_price_direction.ipynb`; a failure means the example has drifted
from the library.
