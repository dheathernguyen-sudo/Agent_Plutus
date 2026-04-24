# Agent Plutus Skills

Capability map for the portfolio agent. Each skill describes what it does, which scripts implement it, and what data flows in and out. Use this to navigate the repo, route a task to the right script, or brief a new session without re-exploring the codebase.

## Orchestration

Run the full daily workflow end-to-end: extract from all sources, fetch benchmarks, build the workbook. Scheduled weekdays at 4:00 PM PT via Windows Task Scheduler (task name `WeeklyPortfolioPipeline`); weekends and US market holidays are skipped automatically.

- **Scripts:** `daily_pipeline.py`, `run_pipeline.bat`, `schedule_task.xml`
- **Inputs:** SnapTrade + Plaid credentials (`~/.portfolio_extract/config.json`), `manual_data.json`, yfinance (benchmarks)
- **Outputs:** Refreshed `data/*.json`, rebuilt `2026_Portfolio_Analysis.xlsx`, log files under `logs/`
- **Invoke:**
  - `python daily_pipeline.py` — full run
  - `python daily_pipeline.py --dry-run` — extract only, no Excel build
  - `python daily_pipeline.py --benchmarks-only` — refresh benchmark returns
  - `python daily_pipeline.py --skip-extract` — rebuild Excel from last extraction

## Brokerage Extraction

Pulls holdings, balances, transactions, and monthly history from each brokerage. SnapTrade covers Robinhood + Fidelity; Plaid covers Merrill 401k and cash accounts (Chase, Marcus). OFX and Playwright paths exist as fallbacks.

- **Scripts:** `fidelity_extract.py`, `fidelity_ofx.py`, `robinhood_history.py`, `plaid_link_oauth.py`
- **Inputs:** Broker APIs (SnapTrade, Plaid, robin_stocks, ofxtools); credentials in `~/.portfolio_extract/config.json` and `~/.portfolio_extract/tokens/`
- **Outputs:** JSON dumps in `extract_output/` (canonical) and project root (`fidelity_latest.json`, `rh_monthly_returns.json`); per-account files rolled into `data/*.json`
- **Invoke:**
  - `python fidelity_extract.py [--headless]` — browser-based (SMS 2FA first run)
  - `python fidelity_ofx.py [--account roth_ira | --setup]` — OFX direct connect
  - `python robinhood_history.py [--login | --year 2026]`
  - `python plaid_link_oauth.py <fidelity|schwab|merrill>` — OAuth relink with ngrok tunnel

## Angel / Manual Data

Tracks private-market investments (small portfolio via GSBacker) and any other manually-maintained values. Interactive valuation check searches for new funding rounds and prompts for approval before writing.

- **Scripts:** `run_angel_check.py`, `manual_data.json`
- **Inputs:** Current `manual_data.json`, user approval at prompt
- **Outputs:** Updated valuations written back to `manual_data.json` (picked up on next pipeline run)
- **Invoke:** `python run_angel_check.py` — interactive; run on your own cadence, not automated

## Portfolio Modeling

Pure computation layer: merges per-account data, calculates TWR (Modified Dietz), MWRR, and cost-basis returns. The registry maps every named range in the workbook to a stable cell address so formulas never hardcode row numbers.

- **Scripts:** `portfolio_model.py`, `registry.py`, `registry_data.json`
- **Inputs:** `data/*.json` (one file per account: `fidelity_brokerage`, `fidelity_roth_ira`, `fidelity_hsa`, `robinhood`, `k401`, `cash`, `angel`), live extraction results
- **Outputs:** In-memory portfolio model dict consumed by workbook builders; `registry_data.json` kept in sync as rebuilds run
- **Invoke:** imported by pipeline and rebuild scripts; not typically run standalone

## Workbook Building

Declarative Excel builder and per-tab rebuilders that write `2026_Portfolio_Analysis.xlsx`. `build_workbook.py` owns shared styles and layout primitives; each `rebuild_*.py` script owns one tab and updates the registry as it runs.

- **Scripts:** `build_workbook.py`, `rebuild_dashboard.py`, `rebuild_brok_tab.py`, `rebuild_cash_tab.py`, `rebuild_hsa_tab.py`, `rebuild_rh_tab.py`, `rebuild_roth_tab.py`
- **Inputs:** Portfolio model dict, `registry.py` cell map, daily snapshot (for Dashboard day-over-day), cached benchmark returns
- **Outputs:** `2026_Portfolio_Analysis.xlsx` with all tabs, named ranges, and formulas wired up
- **Invoke:** normally run via `daily_pipeline.py`; individual `rebuild_*.py` scripts can be run directly for targeted fixes

## Daily Snapshots

Saves a compact snapshot of account market values and holdings each run, used by the Dashboard to show day-over-day changes. Liquid vs. illiquid split excludes Merrill 401k from liquid totals.

- **Scripts:** `daily_snapshot.py`
- **Inputs:** Current extraction results (per-account MV, holdings, prices/qty)
- **Outputs:** Dated snapshot JSON under `extract_output/snapshots/`; summary consumed by `rebuild_dashboard.py`
- **Invoke:** imported by the pipeline; not run standalone

## Validation

Structural and numerical checks against the built workbook. Runs without opening Excel (openpyxl only). Exits non-zero if any ERROR-severity finding is raised, so it can gate a scheduled run.

- **Scripts:** `validate_workbook.py`
- **Inputs:** `2026_Portfolio_Analysis.xlsx`, `registry.REGISTRY`, `registry.MONTHLY_COLUMNS`, `registry.HOLDINGS_ROWS`
- **Outputs:** `PASS` / `WARN` / `ERROR` findings to stdout; non-zero exit on any ERROR
- **Invoke:** `python validate_workbook.py`

---

## Conventions

**Key paths**
- Project root (scripts, workbook, `data/`, `logs/`): `<project root>`
- Shared extraction pipeline (source modules, `extract_output/`, snapshots): `<pipeline dir>` (sibling OneDrive folder)
- Credentials and cached tokens: `~/.portfolio_extract/` (`config.json`, `tokens/`, `tokens/robinhood.pickle`)

**Provider split**
- SnapTrade — Robinhood, Fidelity
- Plaid — Merrill 401k, Chase, Marcus
- Manual — angel investments, benchmarks override

**Schedule**
- Runs Mon–Fri at 4:00 PM PT
- Skips US market holidays (hardcoded set in `daily_pipeline.py`)
- Logs land in `logs/` with a timestamped filename per run

**Repo**
- GitHub: https://github.com/dheathernguyen-sudo/Agent_Plutus
