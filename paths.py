"""Project-wide path resolution.

`PIPELINE_DIR` is the directory holding the shared brokerage extraction modules
(plaid_extract, etc.) and their `extract_output/` cache. Resolution order:

    1. `PORTFOLIO_PIPELINE_DIR` environment variable (absolute or `~/`-style path)
    2. `pipeline_dir` key in `~/.portfolio_extract/config.json`
    3. `<project root>/pipeline/` (default, project-local)

Override via env var or config file — never edit this module to hard-code a path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = Path.home() / ".portfolio_extract" / "config.json"


def _from_config() -> Path | None:
    if not _CONFIG_FILE.exists():
        return None
    try:
        cfg = json.loads(_CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    raw = cfg.get("pipeline_dir")
    return Path(raw).expanduser() if raw else None


def get_pipeline_dir() -> Path:
    env = os.environ.get("PORTFOLIO_PIPELINE_DIR")
    if env:
        return Path(env).expanduser()
    cfg = _from_config()
    if cfg:
        return cfg
    return PROJECT_DIR / "pipeline"


PIPELINE_DIR = get_pipeline_dir()
EXTRACT_OUTPUT = PIPELINE_DIR / "extract_output"
SNAPSHOT_DIR = EXTRACT_OUTPUT / "snapshots"
