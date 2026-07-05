Welcome to the tsauditor wiki!

# tsauditor

A data quality auditing library for **time-series tabular data**, with a focus on financial and sensor domains.

`tsauditor` scans a pandas (or polars) DataFrame and returns a structured report of structural problems, anomalies, and — its core contribution — **data leakage** between features and the prediction target. As of **0.2.0** it can also *repair* the flagged issues on a copy, score data health, export a formal report, and hand a clean array to a forecasting model.

---

## Why tsauditor exists

A same-day percentage-change feature (`ChangeP`) in an OGDC stock-direction model was mathematically near-identical to the prediction target. With it included, a Random Forest classifier reached **99.68% accuracy**. Removing it dropped accuracy to **69.81%** — a more honest number. Nothing about the feature looked wrong on inspection. No standard profiling tool caught it, because standard tools treat tabular data as i.i.d. and don't reason about *when* information was actually available relative to the prediction point.

`tsauditor` exists to catch this class of mistake automatically.

---

## Quick navigation

| Page | What it covers |
| ---- | -------------- |
| [Installation](Installation) | pip install, extras, development setup |
| [Quickstart](Quickstart) | Your first scan, repair, and export |
| [How It Works](How-it-works) | The audit modules explained |
| [Issue Code Reference](Issue-code-reference) | Every PRF / ANO / LEK / VAL code |
| [API Reference](API-Reference) | scan(), fix(), GuardReport, Issue, adapters |
| [Domain Presets](Domain-Presets) | finance vs sensor differences |
| [Contributing](Contributing) | How to open a PR or propose a feature |

---

## At a glance

```python
import tsauditor as tsa

report = tsa.scan(df, target="Direction", domain="finance")
report.summary()          # rich CLI table
report.critical           # list of issues that block modeling
report.leaky_columns()    # the shortlist of features to review/remove
report.to_json("out.json")

# Repair on a copy and keep the audit trail (original is untouched):
clean, report = tsa.fix(df, target="Direction", domain="finance")
```

```
────────────────── tsauditor Report ──────────────────

Critical: 1  Warnings: 4  Info: 1

 Severity   Code    Module    Column    Description
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CRITICAL   LEK001  leakage   ChangeP   Feature near-deterministically
                                        reproduces target 'Direction'
                                        (auc=1.0000 >= 0.95)
```

---

## Design philosophy

- **Advisory by default.** `tsauditor` detects and suggests. It never edits your data *unless* you explicitly call `apply_fixes()` / `fix()` — and even then it works on a **copy**, leaving your original untouched, and it never repairs the target label.
- **Time-aware.** Every check reasons about the temporal order of your data — not just its distribution. This extends to *point-in-time* availability (LEK004): a value must not be used before it was published.
- **Declarative, not magical.** tsauditor never guesses release dates or validity rules. As-of leakage (`available_at=`) and validity constraints (`constraints=`) are opt-in: you declare them, tsauditor verifies them.
- **Domain-aware.** Finance and sensor data have different thresholds for "normal." The `domain` parameter tunes every check accordingly.
- **Programmatic-first.** The report is a structured Python object, not just a printed table. Filter by code, module, or severity; export to JSON or PDF; integrate into pipelines.
