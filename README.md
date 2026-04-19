# Agent Plutus

**See all your investments in one place.** The agent automatically pulls your latest balances from Fidelity, Robinhood, your 401(k), and other accounts — then builds a single Excel report showing how your money is doing daily. 

**Privacy first:** Your financial data never leaves your machine. No cloud servers, no third-party storage, no accounts to create. Everything runs locally — your holdings, balances, and account numbers stay on your computer and nowhere else.

## What It Does

If you have investments spread across multiple apps, you probably have no idea how your total portfolio is actually performing. Each app shows you a piece, but none shows the whole picture. This tool fixes that.

1. **Connects to your accounts** — securely pulls your latest balances and holdings from each brokerage, similar to how Mint or Empower (Personal Capital) works
2. **Compares you to the market** — grabs S&P 500, Dow Jones, and NASDAQ performance so you can see if you're ahead or behind
3. **Builds your daily report** — creates one Excel file with everything organized by account
4. **Tracks changes over time** — saves daily snapshots so you can see how your portfolio moved day to day

## What You'll See

Your report is an Excel workbook with these pages:

- **Dashboard** — your total net worth across all accounts, whether you're beating the market, and where your money is concentrated
- **Account pages** (Fidelity Brokerage, Roth IRA, HSA, Robinhood, 401k) — what you own in each account, what you paid for it, and your profit or loss
- **Angel Investments** — if you have any private company investments, they're tracked here with automatic valuation lookups
- **Cash** — liquid balances across checking, savings, and brokerage cash positions

### Sample Report (redacted)

**Dashboard** — benchmark comparison, YTD gains, account overview, and sector concentration at a glance. Dollar amounts are redacted; returns and percentages are real.

![Dashboard](docs/screenshots/Dashboard.png)

**Account tab** — each brokerage account gets its own page with return metrics, gain/loss summary, and current holdings.

![Account Tab](docs/screenshots/Fidelity_Brokerage.png)

## Where Your Data Comes From

| Account | How We Connect | What We Pull |
|---------|----------------|-------------|
| Fidelity (Brokerage, Roth IRA, HSA) | SnapTrade (read-only API) | Current holdings, cost basis, cash balances |
| Robinhood | SnapTrade (read-only API) | Current holdings, transactions, margin details |
| 401(k) (Merrill Lynch, Fidelity NetBenefits, etc.) | Plaid (read-only API) | Fund holdings, balances |
| Checking & Savings (Chase, Marcus) | Plaid (read-only API) | Cash balances only |
| Market benchmarks | Yahoo Finance | S&P 500, Dow, NASDAQ performance |
| Angel investments | Manual + DuckDuckGo search | Private company valuations from funding rounds |

> **Is this safe?** Yes. All connections are **read-only** — the tool can see your balances but **cannot trade, move money, or make any changes** to your accounts. Your credentials are stored locally on your machine, never sent anywhere.

## Getting Started

**Initial setup takes about 30 minutes.** After that, the tool runs automatically every weekday and your report is waiting for you.

### What You'll Need

- **A computer** — Windows 10+ or macOS 12+
- **Python 3.12 or newer** — [download here](https://www.python.org/downloads/)
- **Your brokerage login credentials** — stored locally on your machine
- **Free API keys** from two services (instructions below)

### Step 1: Install the Tool

```bash
# Download the code, then in your terminal:
pip install -r requirements.txt
```

### Step 2: Get Your API Keys

You'll need free developer accounts from two services that securely connect to your brokerages:

#### SnapTrade (for Robinhood + Fidelity)

1. Sign up at [dashboard.snaptrade.com/signup](https://dashboard.snaptrade.com/signup)
2. Verify your email
3. Generate an API key from the dashboard

You'll get a **Client ID** and **Consumer Key** — save both. Access is instant after email verification, no approval process.

The free tier includes 5 brokerage connections, which is enough for most users. Beyond that, it's $1.50/user/month with no minimums.

#### Plaid (for 401k, checking, savings)

1. Sign up at [dashboard.plaid.com/signup](https://dashboard.plaid.com/signup)
2. Go to **Developers > Keys** to find your **Client ID** and **Secret**
3. Enable the **Investments** product in your dashboard (required for 401k holdings)

Plaid has three environments:

| Environment | Access | Cost | Use for |
|-------------|--------|------|---------|
| **Sandbox** | Instant | Free | Testing with fake data |
| **Trial** | Instant | Free (10 accounts) | Testing with real brokerages |
| **Production** | Requires approval (~1 week) | Pay-as-you-go | Full daily use |

You can start with the **Trial** plan, which lets you connect up to 10 real accounts for free — enough to verify everything works before applying for full production access. Production approval typically takes about a week.

### Step 3: Connect Your Accounts

```bash
# This walks you through entering your API keys and linking accounts
python extractors/plaid_extract.py --setup

# If using Fidelity browser automation fallback:
python extractors/fidelity_extract.py
```

### Step 4: Set Up Your Account Data

Copy the example templates and fill in your account details:

```bash
# Copy each account you want to track
cp data/fidelity_brokerage.example.json data/fidelity_brokerage.json
cp data/robinhood.example.json data/robinhood.json
cp data/k401.example.json data/k401.json
# ... etc.

# Copy the manual data template for 401(k) quarterly data and angel investments
cp manual_data.example.json manual_data.json
```

Edit each JSON file with your account numbers, monthly performance, and holdings.

### Step 5: Run It

```bash
python src/daily_pipeline.py
```

Your report will be saved as `2026_Portfolio_Analysis.xlsx` in the project folder.

### Step 6: Set It and Forget It

Schedule the tool to run automatically every weekday afternoon:

**Windows:**
```bash
schtasks /create /tn "AgentPlutus" /xml schedule_task.xml
```

**Mac/Linux:**
```bash
# Open your cron editor and add this line:
crontab -e
# Add: 0 16 * * 1-5 cd /path/to/agent-plutus && python3 src/daily_pipeline.py
```

#### Scheduling Tips

The pipeline runs locally on your machine — **your financial data never leaves your computer**. This is a deliberate design choice: unlike cloud-based tools like Mint or Empower, your holdings, balances, and account numbers are never stored on third-party servers.

The trade-off is the pipeline only runs when your computer is on or sleeping:

- **Sleep mode (lid closed):** The scheduler will wake your machine, run the pipeline, then let it sleep again. This is the recommended setup — most people close their laptop lid rather than shutting down, and this covers you automatically.
- **Fully shut down:** The pipeline can't run while the machine is off. However, the scheduler is configured with `StartWhenAvailable`, so it will run automatically the next time you turn your machine on.
- **Missed days:** The pipeline has built-in **catch-up mode**. If it detects missed trading days since its last run (e.g., your laptop was off for a few days), it will log the gap and rebuild the workbook from the most recent cached data. You won't lose coverage — the report will reflect the last available market data.

> **Tip:** For the most reliable scheduling, use **sleep** instead of shutdown. On Windows, you can also enable "Wake timers" in Power Options to ensure Task Scheduler can wake your machine.

### Command Reference

```bash
python src/daily_pipeline.py                  # Full pipeline run
python src/daily_pipeline.py --dry-run        # Extract only, no Excel build
python src/daily_pipeline.py --skip-extract   # Rebuild from last extraction
python src/daily_pipeline.py --benchmarks-only # Only fetch benchmark returns
python src/daily_pipeline.py --check-angels   # Interactive angel valuation check
python extractors/fidelity_extract.py          # Visible browser (first run, 2FA)
python extractors/fidelity_extract.py --headless # Headless mode (after session cached)
python extractors/plaid_extract.py --setup     # Interactive broker setup
python src/validate_workbook.py                # Run workbook validation checks
python tools/redact_for_screenshot.py          # Create redacted copy for sharing
```

## What If I Don't Have All These Accounts?

You don't need all of them. The tool works with whatever accounts you connect:
- Fidelity only? Works.
- Just Robinhood? Works.
- No angel investments? That page is simply skipped.

Add more accounts anytime by re-running the setup and adding the corresponding `data/*.json` file.

## Frequently Asked Questions

**Can this tool access or move my money?**
No. All connections are strictly read-only. It can see your balances and holdings, but has zero ability to trade, transfer, or modify anything.

**Do I need to know Python?**
Only for the initial setup (copy-pasting a few commands). After that, the tool runs on its own every weekday.

**What does "beating the market" mean?**
If the S&P 500 is up 10% this year and your portfolio is up 12%, you're beating the market by 2 percentage points. That 2% is your "alpha."

**How current is the data?**
Each run pulls live data from your accounts. If you run it at 4pm, you'll see that day's prices.

**What if a brokerage connection breaks?**
The tool will still run — it falls back to the most recent successful extraction for that source and warns you in the log. Reconnect when you have a chance.

**What if my computer was off for a few days?**
The pipeline will catch up automatically. When it runs again, it detects any missed trading days and rebuilds the workbook from the most recent cached extraction data. If it's a trading day, it will also pull fresh data from your brokerages.

**Is my financial data stored in the cloud?**
No. Everything runs locally on your machine. Your holdings, account numbers, and balances are never uploaded anywhere. The only network calls are to SnapTrade/Plaid (to read your brokerage data) and Yahoo Finance (for benchmark returns). The generated Excel file stays on your computer.

**Can I run this on a Mac?**
Yes. Everything works on Mac. The only difference is how you schedule the automatic run (cron instead of Task Scheduler).

## File Structure

```
agent-plutus/
├── src/                            # Core pipeline and workbook builder
│   ├── daily_pipeline.py           #   Main orchestrator
│   ├── portfolio_model.py          #   Pure computation model
│   ├── build_workbook.py           #   Declarative Excel builder
│   ├── build_portfolio.py          #   Legacy monolithic builder
│   ├── registry.py                 #   Cell reference registry
│   ├── validate_workbook.py        #   Workbook validation (7 checks)
│   ├── daily_snapshot.py           #   Daily portfolio snapshots
│   ├── rebuild_brok_tab.py         #   Fidelity Brokerage tab rebuilder
│   ├── rebuild_roth_tab.py         #   Fidelity Roth IRA tab rebuilder
│   ├── rebuild_hsa_tab.py          #   Fidelity HSA tab rebuilder
│   ├── rebuild_rh_tab.py           #   Robinhood tab rebuilder
│   ├── rebuild_cash_tab.py         #   Cash tab rebuilder
│   └── rebuild_dashboard.py        #   Dashboard tab rebuilder
├── extractors/                     # Brokerage data extraction
│   ├── plaid_extract.py            #   SnapTrade + Plaid extraction
│   ├── fidelity_extract.py         #   Fidelity browser automation
│   ├── fidelity_csv.py             #   Fidelity CSV parser (legacy)
│   ├── fidelity_ofx.py             #   Fidelity OFX parser (legacy)
│   ├── plaid_link_oauth.py         #   OAuth institution linking
│   ├── robinhood_history.py        #   Robinhood monthly history
│   ├── parse_rh_statements.py      #   Robinhood PDF statement parser
│   └── parse_rh_cost_basis.py      #   Robinhood cost basis calculator
├── tools/                          # Standalone utilities
│   ├── run_angel_check.py          #   Angel valuation web search
│   └── redact_for_screenshot.py    #   Redacted workbook generator
├── data/                           # Account data templates
│   ├── *.example.json              #   Example schemas (in repo)
│   └── *.json                      #   Your real data (gitignored)
├── tests/                          # Test suite
│   ├── conftest.py
│   ├── fixtures/                   #   Synthetic test data
│   └── test_*.py
├── manual_data.example.json        # Template for manual data
├── requirements.txt                # Python dependencies
├── run_pipeline.bat                # Windows scheduler launcher
├── run_pipeline.sh                 # Mac/Linux scheduler launcher
├── schedule_task.xml               # Windows Task Scheduler config
└── README.md
```

## Architecture

The system is built around three layers:

```
Extraction (APIs)  -->  Computation (model)  -->  Output (Excel)
```

### Data Flow

```
SnapTrade API ─────┐
Plaid API ─────────┤
Yahoo Finance ─────┤──> portfolio_model.py ──> build_workbook.py ──> .xlsx
data/*.json ───────┤       (pure math)          (formatting)
manual_data.json ──┘
```

### Extraction Layer
- **`plaid_extract.py`** — SnapTrade (Robinhood, Fidelity) + Plaid (Merrill 401k, Chase, Marcus)
- **`fidelity_extract.py`** — Browser automation fallback for Fidelity via Playwright
- **`robinhood_history.py`** — Historical monthly data via robin_stocks API
- **`parse_rh_statements.py`** / **`parse_rh_cost_basis.py`** — PDF statement parsers for Robinhood

### Computation Layer
- **`portfolio_model.py`** — Pure Python model. Reads `data/*.json` account templates, merges live API data, computes TWR, MWRR, cost basis returns, and alpha. No Excel dependency.

### Output Layer
- **`build_workbook.py`** — Declarative Excel builder. Reads the model dict and produces a formatted workbook with named ranges.
- **`rebuild_*.py`** — Individual tab rebuilders that can update a single sheet without regenerating the entire workbook:
  - `rebuild_brok_tab.py`, `rebuild_roth_tab.py`, `rebuild_hsa_tab.py` (Fidelity accounts)
  - `rebuild_rh_tab.py` (Robinhood)
  - `rebuild_cash_tab.py` (Cash)
  - `rebuild_dashboard.py` (Dashboard summary)

### Supporting Components
- **`registry.py`** — Cell reference registry defining expected row/column locations for all tabs. Used by the validator and named ranges.
- **`validate_workbook.py`** — 7 automated checks: label matching, formula errors, cross-sheet references, balance continuity, accounting identity, holdings totals, YTD gain consistency.
- **`daily_snapshot.py`** — Saves daily portfolio state as JSON for day-over-day comparison.
- **`run_angel_check.py`** — Interactive angel investment valuation updater using DuckDuckGo web search.
- **`redact_for_screenshot.py`** — Creates a redacted copy of the workbook (dollar amounts masked, returns and tickers preserved) for sharing.

### Pipeline Orchestration

**`daily_pipeline.py`** ties everything together:

1. Extract data from all connected brokerages (SnapTrade + Plaid)
2. Fetch benchmark returns (S&P 500, Dow, NASDAQ) via yfinance
3. Save daily snapshot for historical tracking
4. Build the portfolio model and generate the Excel workbook
5. Run validation checks
6. Report errors and log results

Runs automatically on weekdays at 4:00 PM via Windows Task Scheduler. Skips weekends and US market holidays.

### Account Data Templates

The `data/` directory contains per-account JSON templates that define account structure and monthly performance history. These are merged with live API data at build time. See the `*.example.json` files for the expected schema:

```
data/
├── fidelity_brokerage.example.json   # Brokerage account template
├── fidelity_roth_ira.example.json    # Roth IRA template
├── fidelity_hsa.example.json         # HSA template
├── robinhood.example.json            # Robinhood template (with margin support)
├── k401.example.json                 # 401(k) with quarterly performance
├── angel.example.json                # Angel/private investments
└── cash.example.json                 # Cash account configuration
```

To set up your own accounts, copy each relevant `.example.json` to its non-example name (e.g. `fidelity_brokerage.json`) and fill in your data.

## License

MIT
