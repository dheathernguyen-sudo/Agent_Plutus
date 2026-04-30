"""scan_logs.py — aggregate scanner for pipeline run logs.

Walks `logs/pipeline_*.log`, surfaces error/warning lines, and groups
recurring patterns. Useful for catching silent failures across runs —
e.g. an extractor that's been failing every day for weeks but printing
the error to stdout instead of the log.

Usage:
    python tools/scan_logs.py                # full report
    python tools/scan_logs.py --days 7       # last 7 days only
    python tools/scan_logs.py --errors-only  # just the ERROR lines
"""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_LOGS_DIR = Path.cwd() / "logs"

# Match the standard Python-logging prefix the pipeline writes:
#   2026-04-29 19:14:25,224 [WARNING] Workbook validation: 1 error(s) detected
LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ "
    r"\[(?P<level>ERROR|WARNING|CRITICAL)\] (?P<msg>.*)$"
)
# Match validator findings:  [WARN] Tab: Check ... -- detail
VALIDATOR_LINE = re.compile(r"^\[(?P<sev>ERROR|WARN|FAIL)\] (?P<rest>.*)$")

# Strip per-run noise so messages collapse to recurring patterns.
NOISE = [
    (re.compile(r"\d{4}-\d{2}-\d{2}"), "<DATE>"),
    (re.compile(r"\d{2}:\d{2}:\d{2}"), "<TIME>"),
    (re.compile(r"\d{8}_\d{6}"), "<TS>"),
    (re.compile(r"\$[\d,]+(?:\.\d+)?"), "<$>"),
    (re.compile(r"\d+(?:\.\d+)?"), "<N>"),
]


def normalize(msg: str) -> str:
    out = msg
    for pat, repl in NOISE:
        out = pat.sub(repl, out)
    return out.strip()


def parse_log(path: Path):
    """Yield (ts: datetime, level: str, msg: str) for each error-ish line."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in text.splitlines():
        m = LOG_LINE.match(line)
        if m and m.group("level") in ("ERROR", "WARNING", "CRITICAL"):
            ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S")
            yield ts, m.group("level"), m.group("msg")
            continue
        m = VALIDATOR_LINE.match(line)
        if m and m.group("sev") in ("ERROR", "FAIL"):
            yield None, m.group("sev"), m.group("rest")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--days", type=int, default=None,
                    help="Only scan logs from the last N days.")
    ap.add_argument("--errors-only", action="store_true",
                    help="Suppress warnings; show ERROR/FAIL only.")
    ap.add_argument("--top", type=int, default=10,
                    help="How many recurring patterns to surface (default 10).")
    ap.add_argument("--dir", type=Path, default=DEFAULT_LOGS_DIR,
                    help="Logs directory (default: ./logs relative to cwd).")
    args = ap.parse_args()

    logs = sorted(args.dir.glob("pipeline_*.log"))
    if args.days is not None:
        cutoff = date.today() - timedelta(days=args.days)
        logs = [p for p in logs if _log_date(p) and _log_date(p) >= cutoff]

    if not logs:
        print(f"No logs found under {args.dir}")
        return

    per_day = defaultdict(lambda: Counter())  # date -> Counter(level)
    errors_recent = []  # list of (datetime, level, msg, log filename)
    warning_patterns = Counter()
    error_patterns = Counter()

    for path in logs:
        log_d = _log_date(path)
        for ts, level, msg in parse_log(path):
            per_day[log_d][level] += 1
            norm = normalize(msg)
            if level in ("ERROR", "CRITICAL", "FAIL"):
                error_patterns[norm] += 1
                errors_recent.append((ts or datetime.combine(log_d, datetime.min.time()),
                                       level, msg, path.name))
            elif level in ("WARNING", "WARN") and not args.errors_only:
                warning_patterns[norm] += 1

    # ── Per-day summary ─────────────────────────────────────────────────
    print(f"Scanned {len(logs)} log files spanning "
          f"{min(per_day, default='?')} -> {max(per_day, default='?')}\n")
    print(f"{'Date':<12} {'ERR':>5} {'WARN':>6} {'CRIT':>5}")
    print("-" * 32)
    for d in sorted(per_day):
        c = per_day[d]
        err = c["ERROR"] + c["FAIL"]
        warn = c["WARNING"] + c["WARN"]
        crit = c["CRITICAL"]
        print(f"{d!s:<12} {err:>5} {warn:>6} {crit:>5}")

    # ── Top recurring error patterns ────────────────────────────────────
    if error_patterns:
        print(f"\nTop recurring ERRORs (across all scanned days):")
        for msg, n in error_patterns.most_common(args.top):
            print(f"  count={n:<4}  {msg[:120]}")
    else:
        print("\nNo ERRORs found in the scanned range.")

    # ── Top recurring warning patterns ──────────────────────────────────
    if not args.errors_only and warning_patterns:
        print(f"\nTop recurring WARNINGs (across all scanned days):")
        for msg, n in warning_patterns.most_common(args.top):
            print(f"  count={n:<4}  {msg[:120]}")

    # ── Recent ERRORs verbatim ──────────────────────────────────────────
    if errors_recent:
        print(f"\nMost recent ERRORs (top 10):")
        for ts, level, msg, fname in sorted(errors_recent, reverse=True)[:10]:
            stamp = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "      ?     "
            print(f"  {stamp}  [{level}]  {msg[:100]}  ({fname})")


def _log_date(path: Path):
    """Extract YYYY-MM-DD from pipeline_YYYYMMDD_HHMMSS.log."""
    m = re.search(r"pipeline_(\d{8})_", path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d").date()


if __name__ == "__main__":
    main()
