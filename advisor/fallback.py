"""Deterministic markdown rendering of findings.

Used when the LLM narrator is unavailable (no API key, network failure,
malformed response). Produces a usable, non-narrative brief so the
Recommendations tab always renders.
"""
from __future__ import annotations

from typing import Dict, List

from .observations import Finding

_SEVERITY_ORDER = {"urgent": 0, "attention": 1, "context": 2, "positive": 3}


def _sort_by_severity(findings: List[Finding]) -> List[Finding]:
    return sorted(findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))


def render_findings_only(classified: Dict[str, List[Finding]]) -> str:
    new = _sort_by_severity(classified.get("new", []))
    changed = _sort_by_severity(classified.get("changed", []))
    standing = _sort_by_severity(classified.get("standing", []))

    lines: List[str] = []
    lines.append("# Recommendations (LLM narrator unavailable — findings only)\n")
    lines.append(
        "_Past performance does not guarantee future results. "
        "All investments carry risk, including potential loss of principal. "
        "This is general educational information, not personalized financial advice._\n"
    )

    if not (new or changed or standing):
        lines.append("\n**All clear.** No findings to report from today's run.\n")
        return "\n".join(lines)

    if new or changed:
        lines.append("\n## New / Changed observations\n")
        for f in new + changed:
            lines.append(f"- **[{f.severity.upper()}] {f.headline}**")
        lines.append("")

    if standing:
        lines.append("\n## Standing concerns\n")
        for f in standing:
            lines.append(f"- [{f.severity}] {f.headline}")
        lines.append("")

    return "\n".join(lines)
