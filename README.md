# Agent Plutus

Personal portfolio analysis tool. Pulls daily holdings from Fidelity + Robinhood (SnapTrade), Merrill 401(k) + cash accounts (Plaid), fetches benchmark returns, and rebuilds a multi-tab Excel workbook with dashboards, performance, and an LLM-generated advisor brief.

> **Note:** This is a personal project published as a reference, not a turnkey product. It assumes specific brokerage accounts and a Windows + OneDrive setup, though paths are now config-driven (see `paths.py`). MIT licensed if you want to fork.

## What it does

Each weekday at 4:00 PM PT (Windows Task Scheduler):

1. **Extract** — SnapTrade (Robinhood, Fidelity) + Plaid (Merrill 401k, Chase, Marcus) → JSON in `extract_output/` and `data/`.
2. **Snapshot** — saves a dated copy of holdings + market values for day-over-day comparison.
3. **Build** — declarative Excel builder rebuilds the dashboard, per-account tabs, and historical columns from a registry of named ranges.
4. **Advise** — `advisor/` runs ~15 portfolio observations (concentration, glide path, tax-loss candidates, etc.), classifies them by severity, and asks Claude to write a one-page narrative brief that lands in a Recommendations tab.
5. **Validate** — structural checks against the workbook (openpyxl-only, no Excel needed); non-zero exit gates the run.

## Architecture

```
daily_pipeline.py             # orchestrator
├── paths.py                  # PIPELINE_DIR / EXTRACT_OUTPUT / SNAPSHOT_DIR resolution
├── (extract) → SnapTrade + Plaid → JSON
├── daily_snapshot.py         # dated MV/holdings snapshot
├── portfolio_model.py        # pure computation (TWR, MWRR, cost basis)
│   └── registry.py           # named-range → cell-address map
├── build_workbook.py + rebuild_*.py   # tab builders
├── advisor/                  # observations → findings → narrator → writer
└── validate_workbook.py      # structural + numerical checks

tests/                        # 108 tests; see tests/README.md for philosophy
```

`skills.md` is the canonical capability map — start there.

## Setup

This project assumes Python 3.12+ on Windows. Pipeline modules (SnapTrade/Plaid extractors) live in a sibling directory configured via `paths.py`.

### 1. Install dependencies

```
pip install -r requirements.txt
```

### 2. Configure paths

`paths.PIPELINE_DIR` resolves in this order:

1. `PORTFOLIO_PIPELINE_DIR` environment variable
2. `pipeline_dir` key in `~/.portfolio_extract/config.json`
3. `<project>/pipeline/` (default — works if you symlink/copy your pipeline modules into the project)

### 3. Configure credentials

Create `~/.portfolio_extract/config.json` (gitignored) with sections for `snaptrade`, `plaid`, etc. The exact shape mirrors what `plaid_extract.load_config()` expects.

### 4. Optional — Anthropic API key for advisor narrative

Drop your key into `<project>/.anthropic_key` (single line, gitignored). Without it, the advisor still writes a deterministic findings-only brief.

### 5. Schedule it

Edit `schedule_task.xml` (replace `<PROJECT_PATH>` and `YourUsername`), then import via Windows Task Scheduler.

## Usage

```
python daily_pipeline.py                  # full run
python daily_pipeline.py --dry-run        # extract only, no Excel build
python daily_pipeline.py --benchmarks-only
python daily_pipeline.py --skip-extract   # rebuild Excel from cached extraction
python daily_pipeline.py --check-angels   # interactive private-market valuation check
python validate_workbook.py               # structural validation
python -m pytest tests/ -v                # full test suite (~8 sec)
```

## Testing

108 tests across three layers:

- `tests/test_regressions.py` — one+ test per bug fixed (with traceability table in `tests/README.md`)
- `tests/test_integration_golden.py` — synthetic-fixture end-to-end test of `build_model` → `build`
- `tests/advisor/` — observation, narrator, writer, profile

See `tests/README.md` for the testing philosophy (TDD-style; tests + fixes commit together; no CI; no mocked network tests).

## Disclaimers

- **Not financial advice.** The advisor narrator generates educational content grounded in CFP frameworks, not personalized recommendations. Consult a licensed advisor for actual decisions.
- **Past performance does not guarantee future results.** All investments carry risk including potential loss of principal.
- **Personal repo.** I run this against my own accounts. Account-specific assumptions (e.g. tab structure, custom holding labels) may need rework for other portfolios.

## License

MIT — see [LICENSE](LICENSE).
