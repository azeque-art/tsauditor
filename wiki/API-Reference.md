## `tsauditor.scan()`

The single entry point for all audits.

```python
tsauditor.scan(
    df: pd.DataFrame,
    target: Optional[str] = None,
    time_col: Optional[str] = None,
    domain: Optional[str] = None,
    available_at: Optional[dict] = None,
    constraints: Optional[dict] = None,
    run_profiler: bool = True,
    run_anomaly: bool = True,
    run_leakage: bool = True,
    run_stationarity: bool = True,
) -> GuardReport
```

### Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `df` | `pd.DataFrame` | required | Input DataFrame. Must have a `DatetimeIndex`, or pass `time_col`. A polars DataFrame is accepted with `time_col` (needs the `[polars]` extra). |
| `target` | `str` or `None` | `None` | Target/label column. Required for LEK001–003; skipped if `None`. |
| `time_col` | `str` or `None` | `None` | Datetime column to set as the index. |
| `domain` | `str` or `None` | `None` | Threshold preset: `"finance"`, `"sensor"`, or `None`. See [Domain Presets](Domain-Presets). |
| `available_at` | `dict` or `None` | `None` | Point-in-time availability for the as-of check (LEK004). Maps column → per-row publish timestamps (`pd.Series` on `df.index`) or a fixed `pd.Timedelta` lag. Only listed columns are checked. |
| `constraints` | `dict` or `None` | `None` | Domain-validity rules (VAL001/VAL002). `{"bounds": {col: {"min":…, "max":…, "min_exclusive":…, "max_exclusive":…}}, "relations": [(low, high), …]}`. A flat `{col: {...}}` is treated as bounds. |
| `run_profiler` | `bool` | `True` | Run structural checks (PRF). |
| `run_anomaly` | `bool` | `True` | Run anomaly checks (ANO). |
| `run_leakage` | `bool` | `True` | Run leakage checks (LEK). Skipped for target-based checks if `target` is `None`; LEK004 runs whenever `available_at` is given. |
| `run_stationarity` | `bool` | `True` | Run the ADF test (PRF003) — the runtime hot spot. Set `False` for a much faster sweep. |

### Returns

A `GuardReport`.

### Raises

- `TypeError` — `df` is not a `pd.DataFrame`
- `ValueError` — invalid `domain`; `target`/`time_col` not found; empty `df`; a declared `available_at`/`constraints` column is missing or non-numeric

### Example

```python
import pandas as pd
import tsauditor as tsa

report = tsa.scan(df, target="Direction", domain="finance")

# As-of leakage: CPI is published ~30 days after its reference date
report = tsa.scan(df, available_at={"cpi": pd.Timedelta(days=30)})

# Validity: strictly-positive spread and an uncrossed book
report = tsa.scan(df, constraints={
    "bounds": {"spread": {"min": 0, "min_exclusive": True}},
    "relations": [("bid", "ask")],
})
```

---

## `tsauditor.fix()`

One-shot scan-and-repair. Returns **both** the cleaned copy and the report, so the audit trail is never discarded. The input is never modified.

```python
clean_df, report = tsauditor.fix(
    df,
    target=None,
    time_col=None,
    domain=None,
    missing="interpolate",
    outliers="clip",
    stuck="nan",
    leakage=None,
    verbose=False,
)
```

Equivalent to `scan()` then `report.apply_fixes()`. See `apply_fixes` below for the repair options. The **target label is never repaired**.

---

## `tsauditor.adapters.to_timesfm()`

Audit, repair, and format a single series into a finite `float32` array for Google TimesFM (adds no `timesfm` dependency).

```python
array = tsauditor.adapters.to_timesfm(
    df,
    target_col,
    *,
    domain=None,
    context_len=1024,
    min_context=32,
    return_report=False,   # True -> (array, report)
)
```

Cleans the target as an ordinary column (it is the series to forecast, so it is *not* protected), and **verifies the result is finite** before returning — raising rather than letting a NaN reach the model. `context_len` / `min_context` are your knobs, not TimesFM constants.

---

## `GuardReport`

The structured output of `scan()`.

```python
from tsauditor import GuardReport
```

### Attributes

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `critical` | `List[Issue]` | Issues that block modeling |
| `warnings` | `List[Issue]` | Issues worth reviewing |
| `info` | `List[Issue]` | Informational findings |
| `metadata` | `Dict[str, Any]` | rows, columns, time range, frequency, target, domain |
| `last_fixes` | `List[Dict]` | Change log from the most recent `apply_fixes`/`fix` (column, action, cells changed) |

### Properties

**`all_issues`** → `List[Issue]` — all issues, sorted by severity then module.

### Methods

**`filter(code=None, module=None, severity=None)`** → `List[Issue]` — combinable filters.

**`leaky_columns()`** → `List[str]` — sorted list of columns flagged by the leakage module.

**`suggestions()`** → `List[Dict]` — per-issue suggested actions (`code`, `column`, `severity`, `suggestion`).

**`apply_fixes(df, missing="interpolate", outliers="clip", stuck="nan", leakage=None, verbose=False)`** → `pd.DataFrame` — repaired **copy** of `df`, fixing only flagged columns. `outliers`: `"clip"` / `"nan"` / `"drop"` (alias for nan) / `None`; `stuck`: `"nan"` / `None`; `leakage`: `"drop"` / `None`. Never touches the target. Records `last_fixes`.

**`health_score(df)`** → `float` — % of numeric cells not implicated by a quality issue (leakage excluded). Re-scans `df`, so calling it on a `fix()` output gives a true "after" score.

**`summary()`** → `None` — prints a rich CLI table plus suggested actions.

**`to_json(path, df=None, fixed_df=None)`** → `None` — JSON export; with `df` it adds the health block, with `fixed_df` a before/after delta.

**`to_pdf(path, df=None, fixed_df=None, title=None)`** → formal, text-selectable PDF report. Needs the `[pdf]` extra.

**`to_dict()`** → `Dict[str, Any]`.

---

## `Issue`

A single quality issue.

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `module` | `str` | `"profiler"`, `"anomaly"`, `"leakage"`, or `"validity"` |
| `code` | `str` | e.g. `"LEK001"` — see [Issue Code Reference](Issue-code-reference) |
| `severity` | `str` | `"critical"`, `"warning"`, `"info"` |
| `description` | `str` | Human-readable explanation |
| `column` | `str` or `None` | Affected column, or `None` for dataset-level |
| `evidence` | `Dict[str, Any]` | Supporting statistics |

**`suggestion`** → `str` — recommended action derived from the code. **`to_dict()`** → `Dict`.

---

## Severity constants

```python
from tsauditor.report.summary import CRITICAL, WARNING, INFO
```
