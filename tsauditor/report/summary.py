"""
tsauditor.report.summary
------------------------
Defines the GuardReport and Issue dataclasses that form the
structured output of every tsauditor scan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from rich.console import Console
from rich.table import Table
from rich import box

from tsauditor.report.remediation import suggest


def _json_default(obj: Any) -> Any:
    """
    JSON serialization fallback. Converts numpy scalars and arrays to native
    Python types so evidence values stay JSON *numbers* (not quoted strings),
    then falls back to str() for anything else.
    """
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


# ── Severity constants ────────────────────────────────────────────────────────
CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}
_SEVERITY_COLOR = {CRITICAL: "bold red", WARNING: "yellow", INFO: "cyan"}


@dataclass
class Issue:
    """
    A single quality issue detected by tsauditor.

    Attributes
    ----------
    module : str
        Which module raised the issue: "profiler", "anomaly", "leakage", or
        "validity".
    code : str
        Short issue code (e.g. "LEK001"). Use for programmatic filtering.
    severity : str
        One of "critical", "warning", "info".
    description : str
        Human-readable explanation of the issue.
    column : Optional[str]
        The affected column, or None if dataset-level.
    evidence : Dict[str, Any]
        Supporting statistics (e.g. {"lag0_corr": 0.99, "threshold": 0.95}).
    """

    module: str
    code: str
    severity: str
    description: str
    column: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def suggestion(self) -> str:
        """A suggested remediation action, derived from the issue code."""
        return suggest(self.code, self.column, self.evidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "code": self.code,
            "severity": self.severity,
            "description": self.description,
            "column": self.column,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
        }


@dataclass
class GuardReport:
    """
    The structured output of a tsauditor.scan() call.

    Attributes
    ----------
    critical : List[Issue]
        Issues that must be fixed before modeling.
    warnings : List[Issue]
        Issues worth reviewing but not necessarily blockers.
    info : List[Issue]
        Informational findings.
    metadata : Dict[str, Any]
        Dataset-level metadata: rows, columns, time range, inferred frequency.
    """

    critical: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    info: List[Issue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_fixes: List[Dict[str, Any]] = field(default_factory=list)

    # ── Convenience accessors ─────────────────────────────────────────────────

    @property
    def all_issues(self) -> List[Issue]:
        """All issues sorted by severity then module."""
        return sorted(
            self.critical + self.warnings + self.info,
            key=lambda i: (_SEVERITY_ORDER.get(i.severity, 9), i.module),
        )

    def filter(
        self,
        code: Optional[str] = None,
        module: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Issue]:
        """
        Return issues matching all supplied filters.

        Examples
        --------
        >>> report.filter(code="LEK001")
        >>> report.filter(module="leakage", severity="critical")
        """
        issues = self.all_issues
        if code is not None:
            issues = [i for i in issues if i.code == code]
        if module is not None:
            issues = [i for i in issues if i.module == module]
        if severity is not None:
            issues = [i for i in issues if i.severity == severity]
        return issues

    def leaky_columns(self) -> List[str]:
        """
        Columns flagged by the leakage module — the features to review/remove
        first. The library never drops them for you; this is the shortlist.
        """
        cols = [i.column for i in self.filter(module="leakage") if i.column]
        return sorted(set(cols))

    def suggestions(self) -> List[Dict[str, Any]]:
        """
        Per-issue suggested actions, ordered by severity. Advisory only —
        tsauditor reports and recommends but never edits your data.
        """
        return [
            {
                "code": i.code,
                "column": i.column,
                "severity": i.severity,
                "suggestion": i.suggestion,
            }
            for i in self.all_issues
        ]

    def apply_fixes(
        self,
        df,
        missing="interpolate",
        outliers="clip",
        stuck="nan",
        leakage=None,
        verbose=False,
    ):
        """
        Return a repaired *copy* of ``df``, fixing only the columns this report
        flagged. The original DataFrame is never modified. A change log is
        recorded on ``self.last_fixes``.

        See ``tsauditor.remediate.apply_fixes`` for the full parameter docs.

        Examples
        --------
        >>> report = tsa.scan(df, target="Direction", domain="finance")
        >>> clean = report.apply_fixes(df, missing="interpolate", outliers="clip")
        """
        from tsauditor.remediate import apply_fixes as _apply_fixes

        return _apply_fixes(
            self,
            df,
            missing=missing,
            outliers=outliers,
            stuck=stuck,
            leakage=leakage,
            verbose=verbose,
        )

    def health_score(self, df) -> float:
        """
        Data Health Score for ``df``: percent of numeric cells not implicated by
        any quality issue (missing/outlier/spike/stuck). Leakage is excluded — it
        is a modeling risk, not corrupt data.

        This re-scans ``df`` so the score always reflects the frame you pass —
        e.g. call it on an ``apply_fixes`` output to get the true "after" score.
        (Reusing this report's issues would be stale for a repaired frame.) The
        re-scan skips the leakage and ADF checks, which don't affect the score.
        """
        from tsauditor import scan
        from tsauditor.remediate import health_score as _health_score

        fresh = scan(
            df,
            target=self.metadata.get("target"),
            domain=self.metadata.get("domain"),
            run_leakage=False,
            run_stationarity=False,
        )
        return _health_score(fresh, df)

    def to_pdf(self, path, df=None, fixed_df=None, title=None):
        """
        Export a formal, text-selectable PDF report (Times New Roman, black,
        tables, no charts). Requires the optional ``[pdf]`` extra
        (``pip install 'tsauditor[pdf]'``).

        Pass ``df`` for the Data Health Score, and ``fixed_df`` (e.g. the output
        of ``apply_fixes``) for a before/after comparison.
        """
        from tsauditor.report.pdf import export_pdf

        return export_pdf(self, path, df=df, fixed_df=fixed_df, title=title)

    # ── Output methods ────────────────────────────────────────────────────────

    def summary(self) -> None:
        """Print a formatted CLI summary using rich."""
        console = Console()

        # Header
        console.rule("[bold]tsauditor Report[/bold]")

        # Metadata block
        meta = self.metadata
        console.print("\n[bold]Dataset[/bold]")
        console.print(f"  Rows       : {meta.get('rows', 'N/A')}")
        console.print(f"  Columns    : {meta.get('columns', 'N/A')}")
        console.print(
            f"  Time range : {meta.get('time_start', '?')} → {meta.get('time_end', '?')}"
        )
        console.print(f"  Frequency  : {meta.get('frequency', 'unknown')}")

        # Issue counts
        console.print(
            f"\n[bold red]Critical[/bold red]: {len(self.critical)}  "
            f"[yellow]Warnings[/yellow]: {len(self.warnings)}  "
            f"[cyan]Info[/cyan]: {len(self.info)}\n"
        )

        if not self.all_issues:
            console.print("[green]No issues detected.[/green]\n")
            return

        # Issues table
        table = Table(box=box.SIMPLE_HEAVY, show_lines=False, expand=True)
        table.add_column("Severity", style="bold", width=10)
        table.add_column("Code", width=8)
        table.add_column("Module", width=10)
        table.add_column("Column", width=16)
        table.add_column("Description")

        for issue in self.all_issues:
            color = _SEVERITY_COLOR.get(issue.severity, "white")
            table.add_row(
                f"[{color}]{issue.severity.upper()}[/{color}]",
                issue.code,
                issue.module,
                issue.column or "—",
                issue.description,
            )

        console.print(table)

        # Suggested actions (advisory — no data is modified)
        console.print("\n[bold]Suggested actions[/bold]")
        for issue in self.all_issues:
            where = f" [dim]({issue.column})[/dim]" if issue.column else ""
            console.print(f"  • [bold]{issue.code}[/bold]{where}: {issue.suggestion}")
        console.print()

    def to_json(self, path: str, df=None, fixed_df=None) -> None:
        """
        Export the full report to a JSON file — the machine-readable companion
        to ``to_pdf``.

        Parameters
        ----------
        path : str
            Destination file path (e.g. "report.json").
        df : optional
            If given, include the Data Health Score and affected-cell count.
        fixed_df : optional
            If given (e.g. the ``apply_fixes`` output), include the post-fix
            health score and the before/after delta.
        """
        payload = {
            "metadata": self.metadata,
            "issues": [i.to_dict() for i in self.all_issues],
            "counts": {
                "critical": len(self.critical),
                "warnings": len(self.warnings),
                "info": len(self.info),
            },
            "leaky_columns": self.leaky_columns(),
        }
        if df is not None:
            from tsauditor.remediate import affected_cells, health_score

            health = {
                "score": health_score(self, df),
                "affected_cells": affected_cells(self, df),
                "total_cells": int(
                    len(df) * df.select_dtypes(include="number").shape[1]
                ),
            }
            if fixed_df is not None:
                from tsauditor import scan

                after_report = scan(
                    fixed_df,
                    target=self.metadata.get("target"),
                    domain=self.metadata.get("domain"),
                )
                health["score_after"] = health_score(after_report, fixed_df)
            payload["health"] = health

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=_json_default)

    def to_dict(self) -> Dict[str, Any]:
        """Return the full report as a plain Python dict."""
        return {
            "metadata": self.metadata,
            "issues": [i.to_dict() for i in self.all_issues],
            "counts": {
                "critical": len(self.critical),
                "warnings": len(self.warnings),
            },
        }
