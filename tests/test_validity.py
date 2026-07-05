import numpy as np
import pandas as pd
import pytest

from tsauditor.validity import audit_validity
from tsauditor.report.summary import WARNING, CRITICAL


def _idx(n):
    return pd.date_range("2020-01-01", periods=n, freq="D")


# ── Bounds (VAL001) ───────────────────────────────────────────────────────────


def test_clean_within_bounds_no_issue():
    df = pd.DataFrame({"sentiment": np.linspace(-1, 1, 50)}, index=_idx(50))
    assert audit_validity(df, bounds={"sentiment": {"min": -1, "max": 1}}) == []


def test_out_of_range_flagged():
    s = np.linspace(-1, 1, 50)
    s[10] = 1.5  # above max
    s[20] = -2.0  # below min
    df = pd.DataFrame({"sentiment": s}, index=_idx(50))
    issues = audit_validity(df, bounds={"sentiment": {"min": -1, "max": 1}})
    assert len(issues) == 1
    iss = issues[0]
    assert iss.code == "VAL001" and iss.severity == WARNING
    assert iss.evidence["n_violations"] == 2
    assert iss.evidence["observed_max"] == 1.5
    assert iss.evidence["observed_min"] == -2.0


def test_exclusive_min_catches_zero_spread():
    """A spread must be strictly positive: 0 and negatives are glitches."""
    spread = np.full(30, 0.5)
    spread[5] = 0.0  # locked book
    spread[6] = -0.1  # crossed (negative spread)
    df = pd.DataFrame({"spread": spread}, index=_idx(30))
    issues = audit_validity(df, bounds={"spread": {"min": 0, "min_exclusive": True}})
    assert issues[0].evidence["n_violations"] == 2


def test_inclusive_bound_allows_boundary_value():
    spread = np.full(10, 0.0)  # exactly at the inclusive lower bound
    df = pd.DataFrame({"spread": spread}, index=_idx(10))
    assert audit_validity(df, bounds={"spread": {"min": 0}}) == []


def test_nan_not_counted_as_violation():
    s = np.linspace(-1, 1, 20)
    s[3] = np.nan
    df = pd.DataFrame({"sentiment": s}, index=_idx(20))
    assert audit_validity(df, bounds={"sentiment": {"min": -1, "max": 1}}) == []


# ── Relations (VAL002) ────────────────────────────────────────────────────────


def test_crossed_book_flagged():
    bid = np.full(40, 100.0)
    ask = np.full(40, 100.2)
    ask[15] = 99.8  # ask below bid -> crossed book
    df = pd.DataFrame({"bid": bid, "ask": ask}, index=_idx(40))
    issues = audit_validity(df, relations=[("bid", "ask")])
    assert len(issues) == 1
    iss = issues[0]
    assert iss.code == "VAL002" and iss.severity == CRITICAL
    assert iss.column == "ask"
    assert iss.evidence["n_violations"] == 1
    assert iss.evidence["low_col"] == "bid" and iss.evidence["high_col"] == "ask"


def test_equal_values_not_a_violation():
    df = pd.DataFrame(
        {"bid": np.full(10, 5.0), "ask": np.full(10, 5.0)}, index=_idx(10)
    )
    assert audit_validity(df, relations=[("bid", "ask")]) == []


# ── Integration through scan() ────────────────────────────────────────────────


def test_scan_runs_validity_and_excludes_from_leaky():
    import tsauditor as tsa

    bid = np.full(60, 100.0)
    ask = np.full(60, 100.2)
    ask[30] = 99.0
    df = pd.DataFrame({"bid": bid, "ask": ask}, index=_idx(60))
    report = tsa.scan(
        df, constraints={"relations": [("bid", "ask")]}, run_stationarity=False
    )
    assert any(i.code == "VAL002" for i in report.critical)
    assert report.leaky_columns() == []  # validity is not leakage


def test_scan_flat_bounds_mapping_treated_as_bounds():
    import tsauditor as tsa

    s = np.full(60, 0.5)
    s[10] = 5.0
    df = pd.DataFrame({"vol": s}, index=_idx(60))
    report = tsa.scan(df, constraints={"vol": {"max": 1}}, run_stationarity=False)
    assert any(i.code == "VAL001" for i in report.all_issues)


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_missing_column_raises():
    df = pd.DataFrame({"a": np.arange(10.0)}, index=_idx(10))
    with pytest.raises(ValueError, match="not found"):
        audit_validity(df, bounds={"nope": {"min": 0}})


def test_non_numeric_column_raises():
    df = pd.DataFrame({"a": ["x"] * 10}, index=_idx(10))
    with pytest.raises(ValueError, match="not numeric"):
        audit_validity(df, bounds={"a": {"min": 0}})


def test_empty_rules_return_empty():
    df = pd.DataFrame({"a": np.arange(10.0)}, index=_idx(10))
    assert audit_validity(df) == []
