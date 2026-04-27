"""Persist findings to disk and classify against the previous day's set."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Dict, List

from .observations import Finding

logger = logging.getLogger(__name__)


def _findings_path(d: date, state_dir: Path) -> Path:
    return state_dir / f"findings_{d.isoformat()}.json"


def _brief_path(d: date, state_dir: Path) -> Path:
    return state_dir / f"brief_{d.isoformat()}.md"


def save_findings(findings: List[Finding], brief_md: str, d: date, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {"date": d.isoformat(), "findings": [asdict(f) for f in findings]}
    _findings_path(d, state_dir).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if brief_md:
        _brief_path(d, state_dir).write_text(brief_md, encoding="utf-8")


def load_findings_for_date(d: date, state_dir: Path) -> List[Finding]:
    p = _findings_path(d, state_dir)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [Finding(**f) for f in raw.get("findings", [])]


def load_most_recent_before(d: date, state_dir: Path) -> List[Finding]:
    if not state_dir.exists():
        return []
    candidates = sorted(state_dir.glob("findings_*.json"))
    target = f"findings_{d.isoformat()}.json"
    older = [c for c in candidates if c.name < target]
    if not older:
        return []
    raw = json.loads(older[-1].read_text(encoding="utf-8"))
    return [Finding(**f) for f in raw.get("findings", [])]


def diff_findings(today: List[Finding], yesterday: List[Finding]) -> Dict[str, List[Finding]]:
    """Classify today's findings vs yesterday's by (category, key)."""
    yest_map = {(f.category, f.key): f for f in yesterday}
    new, standing, changed = [], [], []
    for f in today:
        prev = yest_map.get((f.category, f.key))
        if prev is None:
            new.append(f)
        elif prev.severity != f.severity:
            changed.append(f)
        else:
            standing.append(f)
    return {"new": new, "standing": standing, "changed": changed}
