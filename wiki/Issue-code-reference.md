Every issue `tsauditor` raises has a short code. Use these codes to filter the report programmatically or to look up what a specific finding means.

```python
# Filter to a specific code
report.filter(code="LEK001")
```

---

## Profiler codes (PRF)

| Code | Severity | Trigger | What to do |
| ---- | -------- | ------- | ---------- |
| PRF001 | WARNING | A gap between consecutive timestamps exceeds the domain threshold | Resample to a regular frequency, or document why irregular timestamps are expected |
| PRF002 | WARNING | 3+ consecutive NaN values (sensor) or 5+ (finance) | Interpolate, forward-fill with a limit, or drop the affected span — check for a known outage |
| PRF003 | INFO | ADF test p-value > 0.05 — column is non-stationary | Consider differencing or log-transforming; non-stationarity is expected for price series but biases many ML methods |
| PRF004 | CRITICAL | Duplicate timestamps in the index | Remove or aggregate duplicates — they silently corrupt rolling, lag, and resampling operations |
| PRF005 | WARNING | A run of consecutive large timestamp gaps | Review the cluster — likely a feed outage requiring explicit handling |
| PRF006 | WARNING | A column is >30% missing overall | Consider dropping or imputing carefully; check whether the missingness is informative |

---

## Anomaly codes (ANO)

| Code | Severity | Trigger | What to do |
| ---- | -------- | ------- | ---------- |
| ANO001 | WARNING | A value repeats consecutively beyond the stuck window (5 finance, 3 sensor) | Investigate a stuck sensor or forward-fill artefact |
| ANO002 | WARNING | A value exceeds the z-score threshold (5.0 finance, 3.5 sensor, 4.0 default) or 1.5×IQR | Winsorize, transform, or treat as a data error |
| ANO003 | WARNING | A value deviates sharply from its immediate neighbours (excluding-self rolling z-score) | Examine the flagged timestamps — contextually extreme even if globally plausible |

---

## Leakage codes (LEK)

| Code | Severity | Trigger | What to do |
| ---- | -------- | ------- | ---------- |
| LEK001 | CRITICAL | Feature reproduces the target — AUC separation ≥ 0.95 (binary) or \|Spearman ρ\| ≥ 0.95 (continuous) | Remove or reconstruct the feature; keep only if it is genuinely available at prediction time |
| LEK002 | WARNING | Feature's peak cross-correlation with the target falls at a *positive* lag | Inspect construction — the feature aligns most strongly with the *future* target |
| LEK003 | WARNING | Feature correlates with the future target beyond what the target's own autocorrelation explains | Verify the feature uses only past data (signature of a centered/forward-looking window) |
| LEK004 | CRITICAL | A value is used before it was available (its release timestamp is later than the row it occupies) | **Opt-in** via `scan(available_at=...)`. Shift the column to its release schedule, not its reference date |

**Rank-based by design.** LEK001 uses AUC separation for binary targets because Pearson against a 0/1 target (point-biserial) is capped near `√(2/π) ≈ 0.798` — a feature that *defines* the target's sign scores only ~0.8 in Pearson and slips under a naive threshold, but AUC scores it 1.0. LEK002/LEK003 use Spearman.

**As-of leakage (LEK004)** cannot be inferred from values alone — you declare availability per column, either a `pd.Series` of per-row publish timestamps or a fixed `pd.Timedelta` publication lag.

---

## Validity codes (VAL)

Domain-constraint checks: values that are *definitionally* wrong. **Opt-in** via `scan(constraints=...)`.

| Code | Severity | Trigger | What to do |
| ---- | -------- | ------- | ---------- |
| VAL001 | WARNING | A value falls outside a declared per-column bound (`bounds`) — e.g. sentiment outside [-1, 1], a non-positive spread | Correct or drop the out-of-range values; likely a feed glitch or scaling error |
| VAL002 | CRITICAL | An ordering `relation` is broken — e.g. `("bid", "ask")` with bid > ask (a crossed book) | Inspect the flagged timestamps for feed glitches |

Validity issues are data errors, so they are **not** counted as leakage in `leaky_columns()`.

---

## Severity levels

| Severity | Meaning |
| -------- | ------- |
| CRITICAL | Must be resolved before modeling — it will directly corrupt training or evaluation |
| WARNING | Worth reviewing — may or may not require action depending on domain context |
| INFO | Informational — no immediate action required |

---

## Adding a new code

If you're contributing a new check, follow the prefix convention (`PRF*`, `ANO*`, `LEK*`, `VAL*`) and add a corresponding entry to `tsauditor/report/remediation.py`. See [Contributing](Contributing).
