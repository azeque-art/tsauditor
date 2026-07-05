"""
tsauditor.report.pdf
--------------------
PDF export for a GuardReport. This is the only module that imports matplotlib,
gated behind the optional ``[pdf]`` extra.

The report is a formal black-and-white document: serif (Times New Roman) text,
black throughout, clear section headings, and tables where the content is
tabular. It contains no charts and no colour coding. The output is vector and
text-selectable, so it copies and OCRs cleanly (e.g. AWS Textract). The
machine-readable companion is ``GuardReport.to_json``.

Layout
------
Scorecard (health score, dataset overview, before/after, leakage callout,
executive summary) and the Detected Issues table share the first page when the
issue list is short; long lists spill onto continuation pages.
"""

from __future__ import annotations

import textwrap
from typing import List, Optional

import pandas as pd

from tsauditor.remediate import health_score

_A4 = (8.27, 11.69)
_ROW_H = 0.05  # page-fraction height of one issues-table row
_BOTTOM = 0.05  # bottom margin

_RC = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "text.color": "black",
    "axes.edgecolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
}


def _require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        return plt, PdfPages
    except ImportError as exc:  # pragma: no cover - exercised only without mpl
        raise ImportError(
            "PDF export requires matplotlib, which is an optional dependency.\n"
            "Install it with:  pip install 'tsauditor[pdf]'"
        ) from exc


def _status(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 70:
        return "Needs Review"
    return "At Risk"


def _executive_summary(report, df) -> List[str]:
    codes = [i.code for i in report.all_issues]
    miss_cols = sorted(
        {
            i.column
            for i in report.all_issues
            if i.code in ("PRF002", "PRF006") and i.column
        }
    )
    miss_cells = (
        int(df[miss_cols].isna().sum().sum()) if (df is not None and miss_cols) else 0
    )
    n_stuck = codes.count("ANO001")
    n_outlier = codes.count("ANO002")
    n_spike = codes.count("ANO003")
    n_leak = len(report.leaky_columns())

    lines: List[str] = []
    if miss_cells:
        lines.append(
            f"{miss_cells} missing data cells across {len(miss_cols)} column(s)."
        )
    if n_stuck:
        lines.append(f"{n_stuck} stuck-value segment(s) detected.")
    if n_outlier or n_spike:
        lines.append(
            f"{n_outlier} column(s) with point outliers; "
            f"{n_spike} with contextual spikes."
        )
    if n_leak:
        lines.append(f"{n_leak} target-leakage column(s) - exclude before modeling.")
    if not lines:
        lines.append("No data-quality or leakage issues detected. Data is model-ready.")
    return lines


def _style(table, fontsize, header_rows=1):
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    for (r, _c), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.5)
        txt = cell.get_text()
        txt.set_color("black")
        txt.set_fontfamily("serif")
        txt.set_verticalalignment("center")
        if r < header_rows:
            txt.set_fontweight("bold")


def _kv_table(fig, rect, col_labels, rows, col_widths, fontsize=8.5):
    ax = fig.add_axes(rect)
    ax.axis("off")
    if not rows:
        rows = [["(none)"] + [""] * (len(col_labels) - 1)]
    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="left",
        colWidths=col_widths,
        loc="upper left",
    )
    table.scale(1, 1.4)
    _style(table, fontsize)


def _wrap_desc(text: str, width: int = 50, max_lines: int = 2) -> str:
    lines = textwrap.wrap(text, width=width) or ["-"]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + " ..."
    return "\n".join(lines)


def _issues_table(fig, left, top, width, issues, fontsize=8) -> None:
    """Draw the issues table with a fixed bbox so row heights are deterministic."""
    rows = [
        [i.code, i.severity.upper(), i.column or "-", _wrap_desc(i.description)]
        for i in issues
    ] or [["-", "-", "-", "-"]]
    n = len(rows) + 1  # + header
    height = n * _ROW_H
    ax = fig.add_axes([left, top - height, width, height])
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=["Code", "Severity", "Column", "Description"],
        colWidths=[0.12, 0.15, 0.20, 0.53],
        cellLoc="left",
        bbox=[0, 0, 1, 1],
    )
    _style(table, fontsize)


def _capacity(top: float) -> int:
    """How many issue rows fit between ``top`` and the bottom margin."""
    return max(1, int((top - _BOTTOM) / _ROW_H) - 1)  # -1 for the header row


def export_pdf(
    report,
    path: str,
    df: Optional[pd.DataFrame] = None,
    fixed_df: Optional[pd.DataFrame] = None,
    title: Optional[str] = None,
) -> str:
    plt, PdfPages = _require_matplotlib()
    meta = report.metadata
    title = title or "Time-Series Data Health Report"

    score = health_score(report, df) if df is not None else None
    after = None
    if fixed_df is not None:
        from tsauditor import scan

        after_report = scan(
            fixed_df, target=meta.get("target"), domain=meta.get("domain")
        )
        after = health_score(after_report, fixed_df)
    leak_cols = report.leaky_columns()

    with plt.rc_context(_RC), PdfPages(path) as pdf:
        fig = plt.figure(figsize=_A4)
        fig.text(0.08, 0.955, title, fontsize=17, weight="bold")
        fig.text(0.08, 0.935, "Generated by tsauditor", fontsize=8.5)
        fig.lines.append(
            plt.Line2D(
                [0.08, 0.92],
                [0.928, 0.928],
                transform=fig.transFigure,
                color="black",
                lw=0.8,
            )
        )

        # Top band: dataset overview (left) and health score (right)
        fig.text(0.08, 0.90, "Dataset Overview", fontsize=12, weight="bold")
        meta_rows = [
            [k.replace("_", " ").title(), str(meta[k])]
            for k in (
                "rows",
                "columns",
                "time_start",
                "time_end",
                "frequency",
                "domain",
                "target",
            )
            if meta.get(k) is not None
        ]
        _kv_table(
            fig,
            [0.08, 0.74, 0.46, 0.14],
            ["Field", "Value"],
            meta_rows,
            col_widths=[0.45, 0.55],
        )

        if score is not None:
            fig.text(0.60, 0.90, "Data Health Score", fontsize=12, weight="bold")
            fig.text(0.60, 0.855, f"{score:.0f}% Clean", fontsize=22, weight="bold")
            fig.text(0.60, 0.832, f"Status: {_status(score)}", fontsize=10)
            if after is not None:
                delta = after - score
                sign = "+" if delta >= 0 else ""
                _kv_table(
                    fig,
                    [0.60, 0.745, 0.32, 0.06],
                    ["Metric", "Value"],
                    [
                        ["Before", f"{score:.0f}%"],
                        ["After fixes", f"{after:.0f}%"],
                        ["Change", f"{sign}{delta:.1f} pts"],
                    ],
                    col_widths=[0.6, 0.4],
                )

        # Flowing sections
        y = 0.70
        if leak_cols:
            fig.text(0.08, y, "Critical: Target Leakage", fontsize=12, weight="bold")
            y -= 0.026
            fig.text(
                0.08,
                y,
                "Exclude these columns before modeling: " + ", ".join(leak_cols),
                fontsize=9.5,
            )
            y -= 0.038

        fig.text(0.08, y, "Executive Summary", fontsize=12, weight="bold")
        y -= 0.026
        for line in _executive_summary(report, df):
            fig.text(0.10, y, f"- {line}", fontsize=9.5)
            y -= 0.022

        fig.text(
            0.08,
            y,
            f"Critical: {len(report.critical)}    "
            f"Warnings: {len(report.warnings)}    "
            f"Info: {len(report.info)}",
            fontsize=9.5,
            weight="bold",
        )
        y -= 0.04

        # Issues table — on this page if it fits, otherwise continuation pages
        issues = report.all_issues
        fig.text(0.08, y, "Detected Issues", fontsize=14, weight="bold")
        y -= 0.022
        cap = _capacity(y)
        _issues_table(fig, 0.08, y, 0.84, issues[:cap])
        pdf.savefig(fig)
        plt.close(fig)

        rest = issues[cap:]
        per_page = _capacity(0.92)
        for start in range(0, len(rest), per_page):
            chunk = rest[start : start + per_page]
            fig = plt.figure(figsize=_A4)
            fig.text(
                0.08, 0.95, "Detected Issues (continued)", fontsize=15, weight="bold"
            )
            _issues_table(fig, 0.08, 0.92, 0.84, chunk)
            pdf.savefig(fig)
            plt.close(fig)

        info = pdf.infodict()
        info["Title"] = title
        info["Author"] = "tsauditor"
        info["Subject"] = "Time-series data health and leakage audit"
        info["Keywords"] = "time-series data-quality leakage audit health-score"

    return path
