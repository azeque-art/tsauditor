# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-07-05

Feature release: as-of leakage detection, domain-validity checks, a one-shot
repair API, the TimesFM adapter, and the remediation/health/PDF/polars/joblib
work — all additive and backward compatible with 0.1.x.

### Added
- As-of / point-in-time leakage check (LEK004): `scan(df, available_at=...)` flags
  a feature whose value sits at a timestamp earlier than when it was actually
  published (macro releases, sentiment, earnings). Opt-in — availability cannot be
  inferred from values alone; declare it per column as per-row publish timestamps
  (a `pd.Series`) or a fixed publication lag (a `pd.Timedelta`). CRITICAL.
- Domain-validity checks (`validity` module): `scan(df, constraints=...)` verifies
  declared rules — per-column `bounds` (e.g. a spread must be strictly positive,
  sentiment within [-1, 1]; VAL001, WARNING) and `relations` such as `("bid","ask")`
  to catch a crossed book (VAL002, CRITICAL). Validity issues are not counted as
  leakage.
- TimesFM adapter: `tsa.adapters.to_timesfm(df, target_col=...)` audits, repairs,
  and formats a single series into a 1-D float32 array for Google TimesFM. Cleans
  the target as an ordinary column (not protected — it's the series to forecast),
  verifies the result is finite before returning (so no NaN reaches the model), and
  can return the audit trail via `return_report=True`. Adds no `timesfm` dependency.
- Example notebook `examples/new_features_walkthrough.ipynb` (built and executed by
  `examples/build_new_features_notebook.py`) demonstrating LEK004, validity checks,
  `tsa.fix`, and the TimesFM adapter end-to-end.
- `tsa.fix(df, target=..., domain=...)`: one-shot scan-and-repair convenience
  wrapper returning `(clean_df, report)`. Always returns both, so the audit trail
  (`report.last_fixes`, `leaky_columns()`, issue list) is never silently discarded.
  The original frame is untouched; `clean_df` is an independent copy.
- Performance: LEK002 cross-correlation rank-transforms each series once instead of
  re-ranking on every lag — ~12x faster on wide frames, with identical flags/peak-lags
  (verified). `scan(run_stationarity=False)` skips the ADF test (the runtime hot spot,
  ~6x faster full scan), and `audit_stationarity(max_lag=...)` caps the ADF lag search.
- polars support (issue #28): `scan()` accepts a polars DataFrame, converting to pandas
  at the boundary. polars has no index, so a polars input must pass `time_col=` — the
  error message says so. Optional `[polars]` extra; no new hard dependency.
- joblib/pickle hardening: `GuardReport` and `Issue` round-trip through `pickle`/`joblib`
  (tested), enabling `joblib.Parallel` audits across a symbol universe. README recipe added.
- `leakage` module fully implemented: LEK001 (rank-based target equivalence —
  Spearman for continuous targets, AUC separation for binary), LEK002 (positive-lag
  cross-correlation), LEK003 (rolling-window lookahead via excess-over-persistence).
- Test suites for the leakage module: `test_equivalence.py`, `test_correlation.py`,
  `test_temporal.py`, covering clean/leak/edge cases.
- Standard repository files: `README.md`, `LICENSE`, `CHANGELOG.md`, CI workflow.
- Advisory layer: `Issue.suggestion`, `GuardReport.suggestions()` and `leaky_columns()`.
- Report-driven auto-remediation: `GuardReport.apply_fixes(df, ...)` returns a repaired
  copy (original untouched), fixing only flagged columns — clip/NaN outliers, NaN+impute
  stuck runs, impute missing clusters, opt-in leakage-column drop. Records `report.last_fixes`.
  Contextual spikes (ANO003) are also repaired: clipped to their local rolling band or
  NaN-ed, distinct from global outlier (ANO002) bounds.
- Data Health Score: `GuardReport.health_score(df)` = % of numeric cells not implicated by
  quality issues (leakage excluded). Surfaced in `to_json` with affected/total cells and an
  optional before/after delta.
- PDF export: `GuardReport.to_pdf(path, df=..., fixed_df=...)` — a formal, vector,
  text-selectable report (Times New Roman, black text, headings, tables): Data Health
  Scorecard, dataset overview, before/after, target-leakage callout, executive summary,
  and a paginated issues table. No charts (visualising the series is left to the user)
  and no colour coding. Requires the optional `[pdf]` extra (`pip install 'tsauditor[pdf]'`).

### Fixed
- `scan()` (and `fix()` / `to_timesfm()` through it) no longer crashes on a constant
  numeric column. The ADF stationarity check (PRF003) now skips a zero-variance column
  instead of letting statsmodels' `adfuller` raise "Invalid input, x is constant", and
  guards other numerical failures so one column can never abort the whole audit.
- `apply_fixes` no longer touches the target column. A binary target trips ANO001 (long
  identical runs), and the fixer would NaN-and-interpolate the label into fractions;
  the target (`report.metadata["target"]`) is now excluded from every repair.
- `GuardReport.health_score(df)` re-scans the frame it is given instead of reusing the
  report's (possibly stale) issue list, so the "after" score on an `apply_fixes` output is
  correct. The re-scan skips leakage and ADF, which don't affect the score.
- ANO003 contextual spike detection no longer self-masks: rolling statistics exclude
  the current observation, use a wider window, and handle zero-variance context.
- `scan()` runs end-to-end now that all non-stub modules are implemented; stale
  scaffold tests updated to assert real behavior.
- `.gitignore` re-encoded from UTF-16 to UTF-8 so its patterns take effect.

## [0.1.0]

### Added
- Initial architecture: `profiler`, `anomaly`, `leakage` modules behind a single
  `tsa.scan()` entry point returning a `GuardReport`.
- Profiler checks (PRF001–PRF006), point anomalies (ANO002), CLI/JSON report output.
