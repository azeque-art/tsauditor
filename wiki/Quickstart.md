# Quickstart

## 1. Scan

```python
import tsauditor as tsa

report = tsa.scan(df, target="Direction", domain="finance")

report.summary()                 # rich-formatted CLI table
report.critical                  # list[Issue] that block modeling
report.filter(module="leakage")  # programmatic filtering
report.leaky_columns()           # shortlist of features to review/remove
```

`scan()` returns a `GuardReport` with issues bucketed by severity (`critical`, `warnings`, `info`) plus dataset metadata.

## 2. Repair (optional, on a copy)

tsauditor is advisory by default. When you want it to act, `fix()` scans and repairs in one call and returns **both** the cleaned copy and the report — your original is never modified, and the target label is never repaired.

```python
clean, report = tsa.fix(df, target="Direction", domain="finance")

print(report.last_fixes)   # exactly what changed: column, action, cells
report.health_score(clean) # % of numeric cells not implicated by a quality issue
```

For fine-grained control, use `report.apply_fixes(df, missing=..., outliers=..., stuck=..., leakage=...)`.

## 3. Guard against subtler leaks

```python
import pandas as pd

# As-of leakage: a macro series published 30 days after its reference date
report = tsa.scan(df, available_at={"cpi": pd.Timedelta(days=30)})

# Validity: a spread must be strictly positive; the book must not cross
report = tsa.scan(df, constraints={
    "bounds": {"spread": {"min": 0, "min_exclusive": True}},
    "relations": [("bid", "ask")],
})
```

## 4. Export or feed a model

```python
report.to_json("report.json", df=df, fixed_df=clean)   # + health, before/after
report.to_pdf("report.pdf", df=df, fixed_df=clean)     # needs tsauditor[pdf]

# Forecast-ready array for Google TimesFM (finite-checked, no timesfm dependency):
array = tsa.adapters.to_timesfm(df, target_col="Price", domain="finance")
```

See the [API Reference](API-Reference) for every parameter, and the repo's
`examples/` folder for runnable notebooks.
