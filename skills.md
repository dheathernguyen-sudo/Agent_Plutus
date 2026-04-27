# Agent Plutus Skills

Capability map: which scripts implement what, and how data flows. Use to route a task or brief a new session.

## Orchestration

Daily end-to-end run: extract → benchmarks → workbook. Scheduled Mon–Fri 4:00 PM PT (Task Scheduler: `Portfolio Pipeline`); weekends/US market holidays skipped.

- **Scripts:** `daily_pipeline.py`, `run_pipeline.bat`, `schedule_task.xml`
- **Inputs:** `~/.portfolio_extract/config.json`, `manual_data.json`, yfinance
- **Outputs:** `data/*.json`, `2026_Portfolio_Analysis.xlsx`, `logs/pipeline_*.log`
- **Invoke:** `python daily_pipeline.py [--dry-run | --benchmarks-only | --skip-extract | --check-angels]`

## Brokerage Extraction

Pulls holdings, balances, transactions, monthly history. SnapTrade is primary for Fidelity + Robinhood. Fidelity fallbacks if SnapTrade breaks: `fidelity_ofx.py` (OFX direct connect, project root) and `repo/extractors/fidelity_extract.py` (Playwright browser automation, canonical-but-not-scheduled).

- **Scripts:** `fidelity_ofx.py`, `robinhood_history.py`, `plaid_link_oauth.py`
- **Inputs:** SnapTrade, Plaid, robin_stocks, ofxtools; `~/.portfolio_extract/config.json` and `~/.portfolio_extract/tokens/`
- **Outputs:** JSON in `extract_output/` and project root (`rh_monthly_returns.json`); rolled into `data/*.json`
- **Invoke:**
  - `python fidelity_ofx.py [--account roth_ira | --setup]` (fallback)
  - `python robinhood_history.py [--login | --year 2026]`
  - `python plaid_link_oauth.py <fidelity|schwab|merrill>` (OAuth relink via ngrok)

## Angel / Manual Data

Tracks GSBacker private investments and any manually-maintained values. Interactive search for funding rounds; user approves before write.

- **Scripts:** `run_angel_check.py`, `manual_data.json`
- **Inputs:** `manual_data.json`, user approval at prompt
- **Outputs:** updated `manual_data.json` (picked up next run)
- **Invoke:** `python run_angel_check.py` — interactive, manual cadence

## Portfolio Modeling

Pure computation: merges per-account data, calculates TWR (Modified Dietz), MWRR, cost-basis returns. Registry maps every named range to a stable cell address so formulas don't hardcode rows.

- **Scripts:** `portfolio_model.py`, `registry.py`, `registry_data.json`
- **Inputs:** `data/*.json` (`fidelity_brokerage`, `fidelity_roth_ira`, `fidelity_hsa`, `robinhood`, `k401`, `cash`, `angel`), live extraction
- **Outputs:** in-memory model dict; `registry_data.json` synced as rebuilds run
- **Invoke:** library — imported by pipeline/rebuild scripts

## Workbook Building

Declarative Excel builder + per-tab rebuilders. `build_workbook.py` owns shared styles/layout; each `rebuild_*.py` owns one tab and updates the registry.

- **Scripts:** `build_workbook.py`, `rebuild_dashboard.py`, `rebuild_brok_tab.py`, `rebuild_cash_tab.py`, `rebuild_hsa_tab.py`, `rebuild_rh_tab.py`, `rebuild_roth_tab.py`
- **Inputs:** model dict, `registry.py`, daily snapshot, cached benchmarks
- **Outputs:** `2026_Portfolio_Analysis.xlsx` with all tabs, named ranges, formulas
- **Invoke:** via pipeline; or per-tab directly for targeted fixes

## Daily Snapshots

Compact per-run snapshot of MV/holdings; powers Dashboard day-over-day. Liquid total excludes Merrill 401k.

- **Scripts:** `daily_snapshot.py`
- **Inputs:** current extraction (per-account MV, holdings, prices/qty)
- **Outputs:** dated JSON in `extract_output/snapshots/`; consumed by `rebuild_dashboard.py`
- **Invoke:** library — imported by pipeline

## Validation

Structural + numerical checks against the built workbook (openpyxl only, no Excel). Non-zero exit on any ERROR — gates scheduled runs.

- **Scripts:** `validate_workbook.py`
- **Inputs:** `2026_Portfolio_Analysis.xlsx`, `registry.REGISTRY`, `registry.MONTHLY_COLUMNS`, `registry.HOLDINGS_ROWS`
- **Outputs:** `PASS`/`WARN`/`ERROR` findings to stdout; non-zero exit on ERROR
- **Invoke:** `python validate_workbook.py`

---

## Paths

- Project root (scripts, workbook, `data/`, `logs/`): this directory
- Shared extraction modules + `extract_output/`: resolved by `paths.py` (set `PORTFOLIO_PIPELINE_DIR` env var, or `pipeline_dir` key in `~/.portfolio_extract/config.json`; defaults to `<project>/pipeline/`)
- Credentials/tokens: `~/.portfolio_extract/` (`config.json`, `tokens/`, `tokens/robinhood.pickle`)
- GitHub: https://github.com/dheathernguyen-sudo/Agent_Plutus
