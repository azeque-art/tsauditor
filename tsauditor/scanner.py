"""
tsauditor.scanner
-----------------
The main entry point. scan() orchestrates all audit modules and
assembles a GuardReport.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from tsauditor.report.summary import GuardReport, Issue, CRITICAL, WARNING
from tsauditor.utils.validation import validate_dataframe, infer_frequency


def scan(
    df: pd.DataFrame,
    target: Optional[str] = None,
    time_col: Optional[str] = None,
    domain: Optional[str] = None,
    available_at: Optional[dict] = None,
    constraints: Optional[dict] = None,
    # Fine-grained toggles — all enabled by default
    run_profiler: bool = True,
    run_anomaly: bool = True,
    run_leakage: bool = True,
    run_stationarity: bool = True,
) -> GuardReport:
    """
    Audit a time-series DataFrame for data quality issues.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame. Must have a DatetimeIndex or a datetime column
        specified via time_col.
    target : Optional[str]
        Name of the target/label column. Required for leakage detection.
        If None, leakage checks are skipped.
    time_col : Optional[str]
        Name of a datetime column to use as the index. If None, the
        DataFrame index must already be a DatetimeIndex.
    domain : Optional[str]
        Domain hint for domain-specific heuristics.
        One of: "finance", "sensor", None.
    available_at : Optional[dict]
        Point-in-time availability metadata for the as-of leakage check (LEK004),
        mapping column name -> per-row publish timestamps (a pd.Series indexed by
        df.index) or a fixed publication lag (a pd.Timedelta). Only the columns
        provided are checked. Omitted (default) skips the as-of check, which
        cannot be inferred from values alone.
    constraints : Optional[dict]
        Domain-validity rules (VAL001/VAL002). A dict with optional keys
        ``"bounds"`` (per-column min/max, e.g.
        ``{"spread": {"min": 0, "min_exclusive": True}}``) and ``"relations"``
        (ordered ``(low, high)`` column pairs that must satisfy ``low <= high``,
        e.g. ``[("bid", "ask")]``). A flat ``{col: {...}}`` mapping is treated as
        bounds. Omitted (default) skips validity checks.
    run_profiler : bool
        Run structural profiling checks. Default True.
    run_anomaly : bool
        Run anomaly detection checks. Default True.
    run_leakage : bool
        Run leakage detection checks. Default True.
        Silently skipped if target is None.
    run_stationarity : bool
        Run the ADF stationarity test (PRF003). Default True. This is the most
        expensive check by far (statsmodels ADF dominates runtime); set False to
        skip it when you only need structural, anomaly and leakage checks.

    Returns
    -------
    GuardReport
        Structured report with critical issues, warnings, and info.

    Examples
    --------
    >>> import tsauditor as tsa
    >>> report = tsa.scan(df, target="Direction", domain="finance")
    >>> report.summary()
    >>> report.to_json("report.json")
    """
    # ── Validate domain argument ──────────────────────────────────────────────
    valid_domains = {"finance", "sensor", None}
    if domain not in valid_domains:
        raise ValueError(f"domain must be one of {valid_domains}, got '{domain}'.")

    # ── Validate and normalize input ──────────────────────────────────────────
    df = validate_dataframe(df, target=target, time_col=time_col)

    # ── Build metadata ────────────────────────────────────────────────────────
    metadata = {
        "rows": len(df),
        "columns": len(df.columns),
        "time_start": str(df.index.min().date()),
        "time_end": str(df.index.max().date()),
        "frequency": infer_frequency(df.index),
        "target": target,
        "domain": domain,
    }

    report = GuardReport(metadata=metadata)

    # ── Profiler ──────────────────────────────────────────────────────────────
    if run_profiler:
        from tsauditor.profiler import (
            audit_frequency,
            audit_stationarity,
            audit_missing,
        )

        # audit_frequency is run once and its issues routed by severity.
        # (Previously it was called three times — once per bucket.)
        for issue in audit_frequency(df, domain=domain):
            _append_issue(report, issue)

        # ADF is the heaviest check; allow opting out.
        if run_stationarity:
            for issue in audit_stationarity(df, domain=domain):
                _append_issue(report, issue)

        for issue in audit_missing(df, domain=domain):
            _append_issue(report, issue)

    # ── Anomaly ───────────────────────────────────────────────────────────────
    if run_anomaly:
        from tsauditor.anomaly import (
            audit_point_anomalies,
            audit_contextual_anomalies,
        )

        for issue in audit_point_anomalies(df, domain=domain):
            _append_issue(report, issue)

        for issue in audit_contextual_anomalies(df, domain=domain):
            _append_issue(report, issue)

    # ── Leakage ───────────────────────────────────────────────────────────────
    if run_leakage and target is not None:
        from tsauditor.leakage import (
            audit_equivalence,
            audit_correlation_leakage,
            audit_temporal_leakage,
        )

        for issue in audit_equivalence(df, target=target, domain=domain):
            _append_issue(report, issue)

        for issue in audit_correlation_leakage(df, target=target, domain=domain):
            _append_issue(report, issue)

        for issue in audit_temporal_leakage(df, target=target, domain=domain):
            _append_issue(report, issue)

    # As-of leakage is target-independent and only runs when the caller supplies
    # availability metadata (it cannot be inferred from values alone).
    if run_leakage and available_at:
        from tsauditor.leakage import audit_asof_leakage

        for issue in audit_asof_leakage(df, available_at=available_at):
            _append_issue(report, issue)

    # Domain-validity rules only run when the caller declares them.
    if constraints:
        from tsauditor.validity import audit_validity

        bounds = constraints.get("bounds")
        relations = constraints.get("relations")
        if bounds is None and relations is None:
            bounds = constraints  # flat {col: spec} mapping treated as bounds
        for issue in audit_validity(df, bounds=bounds, relations=relations):
            _append_issue(report, issue)

    return report


def _append_issue(report: GuardReport, issue: Issue) -> None:
    """Route an Issue to the correct severity bucket in the report."""
    if issue.severity == CRITICAL:
        report.critical.append(issue)
    elif issue.severity == WARNING:
        report.warnings.append(issue)
    else:
        report.info.append(issue)
