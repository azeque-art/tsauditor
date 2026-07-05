import pickle

import pytest

from tsauditor.report.summary import GuardReport, Issue, CRITICAL, WARNING


def _report():
    r = GuardReport(
        critical=[
            Issue(
                "leakage",
                "LEK001",
                CRITICAL,
                "Target equivalence.",
                "ChangeP",
                {"separation": 1.0},
            )
        ],
        warnings=[
            Issue(
                "anomaly",
                "ANO002",
                WARNING,
                "Point outliers.",
                "Price",
                {"max_zscore": 7.2},
            )
        ],
        metadata={
            "rows": 500,
            "columns": 7,
            "domain": "finance",
            "target": "Direction",
        },
    )
    # attach the kind of state apply_fixes records, to guard it stays picklable
    r.last_fixes = [{"column": "Price", "action": "clip_outliers", "cells_changed": 3}]
    return r


def test_issue_pickle_roundtrip():
    issue = Issue("leakage", "LEK001", CRITICAL, "eq", "ChangeP", {"sep": 1.0})
    back = pickle.loads(pickle.dumps(issue))
    assert back.code == "LEK001"
    assert back.column == "ChangeP"
    assert back.evidence == {"sep": 1.0}
    assert back.suggestion == issue.suggestion  # computed property still works


def test_guardreport_pickle_roundtrip_preserves_everything():
    r = _report()
    back = pickle.loads(pickle.dumps(r))
    assert [i.code for i in back.critical] == ["LEK001"]
    assert [i.code for i in back.warnings] == ["ANO002"]
    assert back.metadata == r.metadata
    assert back.last_fixes == r.last_fixes
    # derived accessors keep working after a round-trip
    assert back.leaky_columns() == ["ChangeP"]
    assert len(back.all_issues) == 2
    assert back.to_dict()["counts"]["critical"] == 1


def test_report_has_no_unpicklable_state_after_use():
    """Guard: exercising the report (summary render, JSON) must not attach any
    unpicklable handle (e.g. a rich Console or matplotlib figure)."""
    r = _report()
    r.summary()  # builds and discards a rich Console internally
    pickle.dumps(r)  # must still pickle cleanly


def test_joblib_roundtrip(tmp_path):
    joblib = pytest.importorskip("joblib")
    r = _report()
    path = tmp_path / "report.joblib"
    joblib.dump(r, path)
    back = joblib.load(path)
    assert back.leaky_columns() == ["ChangeP"]
    assert back.last_fixes == r.last_fixes
