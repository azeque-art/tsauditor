import numpy as np
import pandas as pd
import pytest

import tsauditor as tsa

pl = pytest.importorskip("polars")  # polars is an optional [polars] extra


def _frame():
    n = 200
    rng = np.random.default_rng(0)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    price = 100 + np.cumsum(rng.normal(0, 1, n))
    return pl.DataFrame(
        {
            "Date": dates,
            "Price": price,
            "ChangeP": pd.Series(price).pct_change().fillna(0).to_numpy() * 100,
            "Direction": (pd.Series(price).pct_change() > 0).astype(int).to_numpy(),
        }
    )


def test_polars_scan_runs_via_time_col():
    """A polars DataFrame is accepted when its datetime column is named."""
    report = tsa.scan(_frame(), target="Direction", time_col="Date", domain="finance")
    assert hasattr(report, "all_issues")
    assert report.metadata["rows"] == 200


def test_polars_without_time_col_raises_pointing_to_issue_28():
    """polars has no index, so time_col is mandatory — and the error says so."""
    with pytest.raises(ValueError) as exc:
        tsa.scan(_frame(), target="Direction")  # no time_col
    msg = str(exc.value)
    assert "time_col" in msg
    assert "issues/28" in msg


def test_polars_and_pandas_agree():
    """The polars path and the equivalent pandas path produce the same issues."""
    pl_df = _frame()
    pd_df = pl_df.to_pandas().set_index("Date")
    r_pl = tsa.scan(pl_df, target="Direction", time_col="Date", domain="finance")
    r_pd = tsa.scan(pd_df, target="Direction", domain="finance")
    assert {(i.code, i.column) for i in r_pl.all_issues} == {
        (i.code, i.column) for i in r_pd.all_issues
    }
