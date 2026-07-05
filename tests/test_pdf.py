import numpy as np
import pandas as pd
import pytest

pytest.importorskip("matplotlib")  # PDF export is gated behind the [pdf] extra

from tsauditor.report.summary import GuardReport, Issue, WARNING


def _idx(n):
    return pd.date_range("2020-01-01", periods=n, freq="D")


def _df_and_report():
    n = 120
    rng = np.random.default_rng(0)
    price = rng.normal(50, 1, n)
    price[60] = 500.0
    df = pd.DataFrame({"price": price, "clean": np.linspace(0, 5, n)}, index=_idx(n))
    df.iloc[20:30, df.columns.get_loc("price")] = np.nan
    rep = GuardReport(
        warnings=[
            Issue("anomaly", "ANO002", WARNING, "Point anomalies in 'price'.", "price"),
            Issue("profiler", "PRF002", WARNING, "Clustered NaNs in 'price'.", "price"),
        ],
        metadata={"rows": n, "columns": 2, "domain": None, "target": None},
    )
    return df, rep


def test_to_pdf_creates_valid_pdf(tmp_path):
    df, rep = _df_and_report()
    out = tmp_path / "report.pdf"
    rep.to_pdf(str(out), df=df)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes()[:4] == b"%PDF"  # real PDF header


def test_to_pdf_with_before_after(tmp_path):
    df, rep = _df_and_report()
    fixed = rep.apply_fixes(df, outliers="clip", missing="interpolate")
    out = tmp_path / "before_after.pdf"
    rep.to_pdf(str(out), df=df, fixed_df=fixed)
    assert out.read_bytes()[:4] == b"%PDF"


def test_to_pdf_without_df_still_renders(tmp_path):
    _, rep = _df_and_report()
    out = tmp_path / "nodf.pdf"
    rep.to_pdf(str(out))  # no df -> scorecard + issues, no charts
    assert out.read_bytes()[:4] == b"%PDF"
