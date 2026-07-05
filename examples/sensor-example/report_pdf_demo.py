"""
Generate a PDF health report from the sensor example — and verify it.

Extends sensor_example.ipynb: scan a faulted sensor stream, repair a copy with
apply_fixes (to drive the Before/After scorecard), export a PDF, then sanity-check
that the PDF is real and non-empty.

Run:
    pip install 'tsauditor[pdf]'
    python examples/sensor-example/report_pdf_demo.py
"""

import os

import numpy as np
import pandas as pd

import tsauditor as tsa


def build_faulted_sensor_frame(seed: int = 0) -> pd.DataFrame:
    """14 days of hourly temperature + humidity with two injected faults:
    a 6-hour STUCK segment in temperature (ANO001) and a 6-hour MISSING gap
    in humidity (PRF002)."""
    rng = np.random.default_rng(seed)
    n = 24 * 14
    idx = pd.date_range("2024-03-01", periods=n, freq="h", name="timestamp")
    h = np.arange(n)
    temperature = 22 + 3 * np.sin(2 * np.pi * h / 24) + rng.normal(0, 0.25, n)
    humidity = 55 + 8 * np.sin(2 * np.pi * (h + 6) / 24) + rng.normal(0, 0.70, n)
    df = pd.DataFrame(
        {"temperature": temperature.round(2), "humidity": humidity.round(2)},
        index=idx,
    )
    stuck = 24 * 5 + 3
    df.iloc[stuck : stuck + 6, df.columns.get_loc("temperature")] = df[
        "temperature"
    ].iloc[stuck]
    gap = 24 * 9 + 3
    df.iloc[gap : gap + 6, df.columns.get_loc("humidity")] = np.nan
    return df


def main(out: str = "sensor_health_report.pdf") -> None:
    df = build_faulted_sensor_frame()

    # 1) audit
    report = tsa.scan(df, domain="sensor")
    report.summary()

    # 2) repaired copy -> Before/After scorecard
    fixed = report.apply_fixes(df, outliers="clip", missing="interpolate", stuck="nan")

    # 3) export the PDF (requires the [pdf] extra)
    report.to_pdf(out, df=df, fixed_df=fixed)

    # 4) verify the PDF
    data = open(out, "rb").read()
    assert os.path.getsize(out) > 0, "PDF is empty"
    assert data[:4] == b"%PDF", "not a valid PDF"
    print(f"\nOK -> {out} ({len(data):,} bytes)")
    print(
        "health before:",
        report.health_score(df),
        "| after:",
        report.health_score(fixed),
    )
    try:
        from pypdf import PdfReader

        print("pages:", len(PdfReader(out).pages))
    except ImportError:
        pass


if __name__ == "__main__":
    main()
