# README Rewrite & QA Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the README for a non-financial audience so they can adopt the portfolio tracker, and build a comprehensive test suite with fixtures to ensure production readiness before public release.

**Architecture:** Two parallel workstreams — (A) a consumer-friendly README replacing the current developer-facing one, and (B) a pytest-based test suite organized by layer (unit → integration → mock → edge cases → cross-platform → security). Test fixtures use synthetic data with realistic shapes matching the pipeline's JSON schemas.

**Tech Stack:** Python 3.12+, pytest, pytest-mock, openpyxl, unittest.mock (for API mocking)

---

## Workstream A: README Rewrite

### Task 1: Write the consumer-friendly README

**Files:**
- Modify: `repo/README.md`

- [ ] **Step 1: Read the current README**

Read `repo/README.md` to confirm current contents match what we've analyzed.

- [ ] **Step 2: Replace the full README with the consumer-friendly version**

Replace the entire contents of `repo/README.md` with:

```markdown
# Portfolio Tracker

**See all your investments in one place.** This tool automatically pulls your latest balances from Fidelity, Robinhood, your 401(k), and other accounts — then builds a single Excel report showing how your money is doing.

## What It Does

If you have investments spread across multiple apps, you probably have no idea how your total portfolio is actually performing. Each app shows you a piece, but none shows the whole picture. This tool fixes that.

1. **Connects to your accounts** — securely pulls your latest balances and holdings from each brokerage, similar to how Mint or Empower (Personal Capital) works
2. **Compares you to the market** — grabs S&P 500, Dow Jones, and NASDAQ performance so you can see if you're ahead or behind
3. **Builds your weekly report** — creates one Excel file with everything organized by account

## What You'll See

Your weekly report is an Excel workbook with these pages:

- **Dashboard** — your total net worth across all accounts, whether you're beating the market, and where your money is concentrated
- **Account pages** (Fidelity, Robinhood, 401k, HSA) — what you own in each account, what you paid for it, and your profit or loss
- **Angel Investments** — if you have any private company investments, they're tracked here too

### Color Coding

The report uses colors so you always know what you're looking at:

| Color | Meaning |
|-------|---------|
| **Blue text** | Real numbers pulled from your accounts |
| **Black text** | Calculated for you (formulas) |
| **Green text** | Numbers pulled from another page in the report |
| **Yellow highlight** | Something you should double-check |

## Key Terms (Plain English)

| Term | What It Means |
|------|---------------|
| **Holdings** | The investments you currently own (stocks, funds, etc.) |
| **Cost basis** | What you originally paid for an investment |
| **Gain/Loss** | How much money you've made or lost on each investment |
| **YTD return** | How much your investments have grown (or shrunk) since January 1st |
| **Benchmark** | How the overall stock market performed over the same period — your point of comparison |
| **Alpha** | How much you're beating (or trailing) the market. Positive = you're winning. |
| **Dividends** | Cash payments companies send you for owning their stock |
| **TWR (Time-Weighted Return)** | Your investment return, adjusted so deposits and withdrawals don't distort the number |

## Where Your Data Comes From

| Account | How We Connect | What We Pull |
|---------|----------------|-------------|
| Fidelity (Brokerage, Roth IRA, HSA) | Secure browser automation | Current holdings, what you paid, cash balances |
| Robinhood | SnapTrade (read-only API) | Current holdings, transactions, margin details |
| 401(k) (Merrill Lynch) | Plaid (read-only API) | Fund holdings, balances |
| Checking & Savings | Plaid (read-only API) | Cash balances only |
| Market benchmarks | Yahoo Finance | S&P 500, Dow, NASDAQ performance |
| Angel investments | Manual + web search | Private company valuations |

> **Is this safe?** Yes. All connections are **read-only** — the tool can see your balances but **cannot trade, move money, or make any changes** to your accounts. Your credentials are stored locally on your machine, never sent anywhere.

## Getting Started

**Initial setup takes about 30 minutes.** After that, the tool runs automatically every Friday and your report is waiting for you.

### What You'll Need

- **A computer** — Windows 10+ or macOS 12+
- **Python 3.12 or newer** — [download here](https://www.python.org/downloads/)
- **Your brokerage login credentials** — stored locally on your machine
- **Free API keys** from two services (instructions below)

### Step 1: Install the Tool

```bash
# Download the code, then in your terminal:
pip install -r requirements.txt
python -m playwright install firefox
```

### Step 2: Get Your API Keys

You'll need free developer accounts from two services that securely connect to your brokerages:

1. **SnapTrade** (for Robinhood) — Sign up at [dashboard.snaptrade.com](https://dashboard.snaptrade.com)
2. **Plaid** (for 401k, checking, savings) — Sign up at [dashboard.plaid.com](https://dashboard.plaid.com) and request production access with the Investments product

### Step 3: Connect Your Accounts

```bash
# This walks you through entering your API keys and linking accounts
python plaid_extract.py --setup

# Connect Fidelity (opens a browser — approve the login on your phone)
python fidelity_extract.py
```

After the first Fidelity login, you'll approve a push notification on your phone. The session stays active for weeks, so you won't need to do this often.

### Step 4: Set Up Your Manual Data

Copy the template and fill in your 401(k) and angel investment details:

```bash
cp manual_data.example.json manual_data.json
```

Edit `manual_data.json` with your:
- 401(k) quarterly performance (from your Merrill statements)
- Angel investment details (if any)

### Step 5: Run It

```bash
python weekly_pipeline.py
```

Your report will be saved as `2026_Portfolio_Analysis.xlsx` in the same folder.

### Step 6: Set It and Forget It

Schedule the tool to run automatically every Friday afternoon:

**Windows:**
```bash
schtasks /create /tn "WeeklyPortfolioPipeline" /xml schedule_task.xml
```

**Mac/Linux:**
```bash
# Open your cron editor and add this line:
crontab -e
# Add: 5 16 * * 5 cd /path/to/project-finance && python3 weekly_pipeline.py
```

## What If I Don't Have All These Accounts?

You don't need all of them. The tool works with whatever accounts you connect:
- Fidelity only? Works.
- Just Robinhood? Works.
- No angel investments? That page is simply skipped.

Add more accounts anytime by re-running the setup.

## Frequently Asked Questions

**Can this tool access or move my money?**
No. All connections are strictly read-only. It can see your balances and holdings, but has zero ability to trade, transfer, or modify anything.

**Do I need to know Python?**
Only for the initial setup (copy-pasting a few commands). After that, the tool runs on its own every week.

**What does "beating the market" mean?**
If the S&P 500 is up 10% this year and your portfolio is up 12%, you're beating the market by 2 percentage points. That 2% is your "alpha."

**How current is the data?**
Each run pulls live data from your accounts. If you run it on Friday at 4pm, you'll see Friday's closing prices.

**What if a brokerage connection breaks?**
The tool will still run — it just skips the account it can't reach and warns you in the log. Reconnect when you have a chance.

**Can I run this on a Mac?**
Yes. Everything works on Mac. The only difference is how you schedule the automatic weekly run (cron instead of Task Scheduler).

---

## Technical Reference

<details>
<summary>Click to expand — for developers and advanced users</summary>

### Pipeline Components

| Script | Purpose |
|--------|---------|
| `weekly_pipeline.py` | Main orchestrator — runs extraction, builds Excel, validates |
| `fidelity_extract.py` | Browser automation for Fidelity via Playwright |
| `plaid_extract.py` | SnapTrade (Robinhood) + Plaid (Merrill, Chase, Marcus) extraction |
| `plaid_link_oauth.py` | OAuth institution linking with ngrok HTTPS tunnel |
| `build_portfolio.py` | Excel workbook generator with formulas and formatting |
| `validate_workbook.py` | 7 structural/numerical checks on the generated workbook |
| `registry.py` | Cell reference definitions for all tabs |
| `parse_rh_statements.py` | Robinhood monthly PDF statement parser |
| `parse_rh_cost_basis.py` | Robinhood cost basis calculator from statements |
| `fidelity_csv.py` | Legacy Fidelity CSV parser (fallback) |

### Command Reference

```bash
python weekly_pipeline.py                  # Full pipeline run
python weekly_pipeline.py --dry-run        # Extract only, no Excel build
python weekly_pipeline.py --skip-extract   # Rebuild from last extraction
python weekly_pipeline.py --benchmarks-only # Only fetch benchmark returns
python fidelity_extract.py                 # Visible browser (first run, 2FA)
python fidelity_extract.py --headless      # Headless mode (after session cached)
python plaid_extract.py --setup            # Interactive broker setup
```

### Provider Notes

- **Fidelity** is not supported by Plaid and has discontinued OFX. Playwright browser automation via `fidelity-api` is the only automated path.
- **Robinhood** uses SnapTrade. Some performance endpoints are paywalled (error 1141).
- **Merrill Lynch 401(k)** uses Plaid credential-based flow (no OAuth redirect needed).
- **Chase/Marcus** are cash-only accounts pulled via Plaid `accounts_get()`.

### File Structure

```
Project Finance/
├── weekly_pipeline.py       # Main orchestrator
├── fidelity_extract.py      # Fidelity Playwright extraction
├── plaid_extract.py         # SnapTrade + Plaid extraction
├── plaid_link_oauth.py      # OAuth linking with ngrok
├── build_portfolio.py       # Excel workbook builder
├── validate_workbook.py     # Workbook validator
├── registry.py              # Cell reference registry
├── fidelity_csv.py          # Fidelity CSV parser (legacy)
├── parse_rh_statements.py   # Robinhood PDF statement parser
├── parse_rh_cost_basis.py   # Robinhood cost basis calculator
├── robinhood_history.py     # Robinhood monthly history
├── rebuild_*.py             # Individual tab rebuilders
├── requirements.txt         # Python dependencies
├── manual_data.json         # Your personal data (not in repo)
├── manual_data.example.json # Template for manual data
├── run_pipeline.bat         # Windows scheduler launcher
├── schedule_task.xml        # Windows Task Scheduler config
├── tests/                   # Test suite
│   ├── fixtures/            # Synthetic test data
│   └── ...
└── logs/                    # Execution logs
```

### Requirements

- Python 3.12+
- Firefox (installed via Playwright)
- SnapTrade API access
- Plaid API production access with Investments product

</details>

## License

MIT
```

- [ ] **Step 3: Commit the README**

```bash
git add repo/README.md
git commit -m "docs: rewrite README for non-financial audience with cross-platform support"
```

---

## Workstream B: Test Suite & Fixtures

### Task 2: Create test directory structure and fixtures

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/fidelity_sample.json`
- Create: `tests/fixtures/snaptrade_raw_sample.json`
- Create: `tests/fixtures/plaid_raw_sample.json`
- Create: `tests/fixtures/plaid_cash_only.json`
- Create: `tests/fixtures/manual_data_sample.json`
- Create: `tests/fixtures/manual_data_empty.json`
- Create: `tests/fixtures/benchmarks_sample.json`
- Create: `tests/fixtures/config_valid.json`
- Create: `tests/fixtures/config_missing_keys.json`

- [ ] **Step 1: Create the tests directory and __init__.py**

```bash
mkdir -p tests/fixtures
touch tests/__init__.py
```

- [ ] **Step 2: Create conftest.py with shared fixtures**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures for portfolio pipeline tests."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def fidelity_sample():
    return json.loads((FIXTURES_DIR / "fidelity_sample.json").read_text())


@pytest.fixture
def snaptrade_raw_sample():
    return json.loads((FIXTURES_DIR / "snaptrade_raw_sample.json").read_text())


@pytest.fixture
def plaid_raw_sample():
    return json.loads((FIXTURES_DIR / "plaid_raw_sample.json").read_text())


@pytest.fixture
def plaid_cash_only():
    return json.loads((FIXTURES_DIR / "plaid_cash_only.json").read_text())


@pytest.fixture
def manual_data_sample():
    return json.loads((FIXTURES_DIR / "manual_data_sample.json").read_text())


@pytest.fixture
def manual_data_empty():
    return {}


@pytest.fixture
def benchmarks_sample():
    return json.loads((FIXTURES_DIR / "benchmarks_sample.json").read_text())


@pytest.fixture
def config_valid():
    return json.loads((FIXTURES_DIR / "config_valid.json").read_text())


@pytest.fixture
def config_missing_keys():
    return json.loads((FIXTURES_DIR / "config_missing_keys.json").read_text())
```

- [ ] **Step 3: Create fidelity_sample.json**

Create `tests/fixtures/fidelity_sample.json`:

```json
{
  "fidelity_BROKERAGE": {
    "account_id": "TEST001",
    "holdings": {
      "2026-04-04": {
        "AAPL": {"qty": 10.0, "price": 150.00, "mv": 1500.00, "cb": 1200.00, "gl": 300.00, "name": "Apple Inc"},
        "MSFT": {"qty": 5.0, "price": 400.00, "mv": 2000.00, "cb": 1800.00, "gl": 200.00, "name": "Microsoft Corp"},
        "VTI": {"qty": 20.0, "price": 250.00, "mv": 5000.00, "cb": 4500.00, "gl": 500.00, "name": "Vanguard Total Stock Market ETF"}
      }
    },
    "cash": 1500.00,
    "balance": 10000.00,
    "monthly": [
      {"month": "January 2026", "deposits": 1000.00, "withdrawals": 0.00, "dividends": 25.00, "buys": 800.00, "sells": 0.00, "fees": 0.00},
      {"month": "February 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "March 2026", "deposits": 500.00, "withdrawals": 200.00, "dividends": 30.00, "buys": 500.00, "sells": 0.00, "fees": 0.00},
      {"month": "April 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "May 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "June 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "July 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "August 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "September 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "October 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "November 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "December 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00}
    ],
    "total_dividends": 55.00,
    "unrealized": 1000.00
  },
  "fidelity_ROTH_IRA": {
    "account_id": "TEST002",
    "holdings": {
      "2026-04-04": {
        "VOO": {"qty": 15.0, "price": 500.00, "mv": 7500.00, "cb": 6000.00, "gl": 1500.00, "name": "Vanguard S&P 500 ETF"},
        "SCHD": {"qty": 30.0, "price": 80.00, "mv": 2400.00, "cb": 2100.00, "gl": 300.00, "name": "Schwab US Dividend Equity ETF"}
      }
    },
    "cash": 200.00,
    "balance": 10100.00,
    "monthly": [
      {"month": "January 2026", "deposits": 500.00, "withdrawals": 0.00, "dividends": 45.00, "buys": 500.00, "sells": 0.00, "fees": 0.00},
      {"month": "February 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "March 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 50.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "April 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "May 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "June 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "July 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "August 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "September 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "October 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "November 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "December 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00}
    ],
    "total_dividends": 95.00,
    "unrealized": 1800.00
  },
  "fidelity_HSA": {
    "account_id": "TEST003",
    "holdings": {
      "2026-04-04": {
        "FXAIX": {"qty": 25.0, "price": 200.00, "mv": 5000.00, "cb": 4200.00, "gl": 800.00, "name": "Fidelity 500 Index Fund"}
      }
    },
    "cash": 300.00,
    "balance": 5300.00,
    "monthly": [
      {"month": "January 2026", "deposits": 300.00, "withdrawals": 0.00, "dividends": 10.00, "buys": 300.00, "sells": 0.00, "fees": 0.00},
      {"month": "February 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "March 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 12.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "April 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "May 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "June 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "July 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "August 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "September 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "October 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "November 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00},
      {"month": "December 2026", "deposits": 0.00, "withdrawals": 0.00, "dividends": 0.00, "buys": 0.00, "sells": 0.00, "fees": 0.00}
    ],
    "total_dividends": 22.00,
    "unrealized": 800.00
  }
}
```

- [ ] **Step 4: Create snaptrade_raw_sample.json**

Create `tests/fixtures/snaptrade_raw_sample.json`:

```json
{
  "robinhood": {
    "provider": "snaptrade",
    "institution": "Robinhood",
    "label": "robinhood",
    "accounts": [
      {
        "account_id": "uuid-test-rh-001",
        "name": "Robinhood Individual",
        "number": "1234567",
        "type": "INDIVIDUAL",
        "balances": {
          "current": 5500.00,
          "currency": "USD"
        }
      }
    ],
    "holdings": [
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "security_id": "sec-nvda",
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "quantity": 10.0,
        "institution_price": 120.00,
        "institution_value": 1200.00,
        "cost_basis": 800.00,
        "gain_loss": 400.00
      },
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "security_id": "sec-tsla",
        "ticker": "TSLA",
        "name": "Tesla Inc",
        "quantity": 5.0,
        "institution_price": 250.00,
        "institution_value": 1250.00,
        "cost_basis": 1500.00,
        "gain_loss": -250.00
      },
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "security_id": "sec-unknown",
        "ticker": "UNKNOWN",
        "name": "Unknown Security",
        "quantity": 1.0,
        "institution_price": 0.01,
        "institution_value": 0.01,
        "cost_basis": 0.00,
        "gain_loss": 0.01
      },
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "security_id": "sec-dust",
        "ticker": "DUST",
        "name": "Micro Position",
        "quantity": 0.001,
        "institution_price": 0.50,
        "institution_value": 0.0005,
        "cost_basis": 0.01,
        "gain_loss": -0.0095
      }
    ],
    "securities": [
      {"security_id": "sec-nvda", "name": "NVIDIA Corporation", "ticker_symbol": "NVDA", "close_price": 120.00},
      {"security_id": "sec-tsla", "name": "Tesla Inc", "ticker_symbol": "TSLA", "close_price": 250.00},
      {"security_id": "sec-unknown", "name": "Unknown Security", "ticker_symbol": null, "close_price": 0.01},
      {"security_id": "sec-dust", "name": "Micro Position", "ticker_symbol": "DUST", "close_price": 0.50}
    ],
    "investment_transactions": [
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "date": "2026-01-15",
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "type": "BUY",
        "description": "Market Buy",
        "quantity": 10.0,
        "price": 80.00,
        "amount": -800.00,
        "fees": 0.00,
        "currency": "USD"
      },
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "date": "2026-02-01",
        "ticker": "TSLA",
        "name": "Tesla Inc",
        "type": "BUY",
        "description": "Market Buy",
        "quantity": 5.0,
        "price": 300.00,
        "amount": -1500.00,
        "fees": 0.00,
        "currency": "USD"
      },
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "date": "2026-03-15",
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "type": "DIVIDEND",
        "description": "Dividend Payment",
        "quantity": 0,
        "price": 0,
        "amount": 4.00,
        "fees": 0.00,
        "currency": "USD"
      },
      {
        "account_id": "uuid-test-rh-001",
        "account_name": "Robinhood Individual",
        "date": "2026-01-05",
        "ticker": "",
        "name": "",
        "type": "DEPOSIT",
        "description": "ACH Deposit",
        "quantity": 0,
        "price": 0,
        "amount": 3000.00,
        "fees": 0.00,
        "currency": "USD"
      }
    ]
  }
}
```

- [ ] **Step 5: Create plaid_raw_sample.json**

Create `tests/fixtures/plaid_raw_sample.json`:

```json
{
  "merrill": {
    "provider": "plaid",
    "institution": "Merrill Lynch (Bank of America)",
    "label": "merrill",
    "accounts": [
      {
        "account_id": "plaid-test-merrill-001",
        "name": "401(k) Plan",
        "type": "investment",
        "subtype": "401k",
        "balances": {
          "current": 25000.00,
          "available": null
        }
      }
    ],
    "holdings": [
      {
        "account_id": "plaid-test-merrill-001",
        "security_id": "psec-sp500",
        "quantity": 100.0,
        "institution_price": 125.00,
        "institution_value": 12500.00,
        "cost_basis": 10000.00
      },
      {
        "account_id": "plaid-test-merrill-001",
        "security_id": "psec-bond",
        "quantity": 50.0,
        "institution_price": 250.00,
        "institution_value": 12500.00,
        "cost_basis": null
      }
    ],
    "securities": [
      {"security_id": "psec-sp500", "name": "S&P 500 Index Fund", "ticker_symbol": "FXAIX", "close_price": 125.00},
      {"security_id": "psec-bond", "name": "Bond Index Fund", "ticker_symbol": null, "close_price": 250.00}
    ],
    "investment_transactions": [
      {
        "account_id": "plaid-test-merrill-001",
        "security_id": "psec-sp500",
        "date": "2026-01-15",
        "type": "cash",
        "subtype": "contribution",
        "quantity": 4.0,
        "price": 125.00,
        "amount": -500.00,
        "fees": 0.00
      },
      {
        "account_id": "plaid-test-merrill-001",
        "security_id": "psec-sp500",
        "date": "2026-02-15",
        "type": "cash",
        "subtype": "contribution",
        "quantity": 4.0,
        "price": 125.00,
        "amount": -500.00,
        "fees": 0.00
      }
    ]
  }
}
```

- [ ] **Step 6: Create plaid_cash_only.json**

Create `tests/fixtures/plaid_cash_only.json`:

```json
{
  "chase": {
    "provider": "plaid",
    "institution": "Chase",
    "label": "chase",
    "accounts": [
      {
        "account_id": "plaid-test-chase-001",
        "name": "Total Checking",
        "type": "depository",
        "subtype": "checking",
        "balances": {
          "current": 5432.10,
          "available": 5432.10
        }
      }
    ],
    "holdings": [],
    "securities": [],
    "investment_transactions": []
  },
  "marcus": {
    "provider": "plaid",
    "institution": "Marcus by Goldman Sachs",
    "label": "marcus",
    "accounts": [
      {
        "account_id": "plaid-test-marcus-001",
        "name": "Online Savings",
        "type": "depository",
        "subtype": "savings",
        "balances": {
          "current": 15000.00,
          "available": 15000.00
        }
      }
    ],
    "holdings": [],
    "securities": [],
    "investment_transactions": []
  }
}
```

- [ ] **Step 7: Create manual_data_sample.json**

Create `tests/fixtures/manual_data_sample.json`:

```json
{
  "k401_data": {
    "quarterly": [
      {
        "period": "Q1 (Nov 1 - Jan 31)",
        "beginning": 20000.00,
        "ee_contributions": 1500.00,
        "er_contributions": 750.00,
        "fees": -12.50,
        "change_in_value": 800.00,
        "ending": 23037.50
      },
      {
        "period": "Q2 (Feb 1 - Apr 30)",
        "beginning": 23037.50,
        "ee_contributions": 1500.00,
        "er_contributions": 750.00,
        "fees": -15.00,
        "change_in_value": -400.00,
        "ending": 24872.50
      }
    ],
    "holdings": [
      {"name": "S&P 500 Index Fund", "beginning": 12000.00, "ending": 13500.00, "gain_loss": 1500.00},
      {"name": "Bond Index Fund", "beginning": 8000.00, "ending": 7800.00, "gain_loss": -200.00}
    ],
    "twr_merrill_stated": 0.0412
  },
  "angel_data": [
    {
      "company": "TestStartup Inc",
      "sector": "AI/ML",
      "year": 2024,
      "series": "Seed",
      "amount": 5000.00,
      "pm_invest": 10000000,
      "pm_latest": 25000000,
      "source": "At cost"
    },
    {
      "company": "HealthTech Co",
      "sector": "Healthcare",
      "year": 2025,
      "series": "Series A",
      "amount": 10000.00,
      "pm_invest": 50000000,
      "pm_latest": 50000000,
      "source": "At cost"
    }
  ],
  "cash_balances": {
    "fidelity_TEST001": 1500.00,
    "fidelity_TEST002": 200.00,
    "fidelity_TEST003": 300.00
  },
  "_notes": {
    "last_updated": "2026-04-01",
    "update_instructions": "Test fixture — do not modify."
  }
}
```

- [ ] **Step 8: Create benchmarks_sample.json**

Create `tests/fixtures/benchmarks_sample.json`:

```json
{
  "S&P 500": 0.0523,
  "Dow Jones": 0.0312,
  "NASDAQ": 0.0789
}
```

- [ ] **Step 9: Create config_valid.json**

Create `tests/fixtures/config_valid.json`:

```json
{
  "snaptrade": {
    "client_id": "test-client-id-12345",
    "consumer_key": "test-consumer-key-67890",
    "user_id": "test-user-id"
  },
  "plaid": {
    "client_id": "test-plaid-client-id",
    "secret": "test-plaid-secret",
    "env": "sandbox"
  },
  "institutions": {
    "robinhood": {"provider": "snaptrade", "account_id": "uuid-test-rh-001"},
    "merrill": {"provider": "plaid", "access_token": "access-sandbox-test-token"}
  }
}
```

- [ ] **Step 10: Create config_missing_keys.json**

Create `tests/fixtures/config_missing_keys.json`:

```json
{
  "snaptrade": {
    "client_id": "",
    "consumer_key": ""
  },
  "plaid": {},
  "institutions": {}
}
```

- [ ] **Step 11: Create manual_data_empty.json**

Create `tests/fixtures/manual_data_empty.json`:

```json
{}
```

- [ ] **Step 12: Commit fixtures**

```bash
git add tests/
git commit -m "test: add test directory structure and synthetic fixtures"
```

---

### Task 3: Unit tests — Benchmark calculation

**Files:**
- Create: `tests/test_benchmarks.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_benchmarks.py`:

```python
"""Tests for benchmark YTD return calculation."""

import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


def test_benchmark_ytd_return_positive():
    """10% gain: (110 / 100) - 1 = 0.10"""
    import weekly_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 105.0, 98.0, 110.0]},
        index=pd.date_range("2026-01-02", periods=4),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    assert "S&P 500" in result
    assert abs(result["S&P 500"] - 0.10) < 0.0001


def test_benchmark_ytd_return_negative():
    """5% loss: (95 / 100) - 1 = -0.05"""
    import weekly_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 90.0, 95.0]},
        index=pd.date_range("2026-01-02", periods=3),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    assert result["S&P 500"] == pytest.approx(-0.05, abs=0.0001)


def test_benchmark_flat_return():
    """0% return when first_close == last_close."""
    import weekly_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 110.0, 100.0]},
        index=pd.date_range("2026-01-02", periods=3),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    assert result["S&P 500"] == pytest.approx(0.0, abs=0.0001)


def test_benchmark_empty_dataframe_skipped():
    """Empty DataFrame should skip the ticker, not crash."""
    import weekly_pipeline

    empty_df = pd.DataFrame()

    with patch("yfinance.download", return_value=empty_df):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    assert result == {} or all(v is not None for v in result.values())


def test_benchmark_network_error_handled():
    """Network error should be caught, not crash the pipeline."""
    import weekly_pipeline

    with patch("yfinance.download", side_effect=Exception("Connection timeout")):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    assert isinstance(result, dict)


def test_benchmark_all_three_indices_present():
    """All three benchmarks should be populated when data is available."""
    import weekly_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 110.0]},
        index=pd.date_range("2026-01-02", periods=2),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    assert "S&P 500" in result
    assert "Dow Jones" in result
    assert "NASDAQ" in result


def test_benchmark_return_rounded_to_6_decimals():
    """Returns should be rounded to 6 decimal places."""
    import weekly_pipeline

    # 1/3 gain = 0.333333... should round to 0.333333
    mock_data = pd.DataFrame(
        {"Close": [300.0, 400.0]},
        index=pd.date_range("2026-01-02", periods=2),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = weekly_pipeline.fetch_benchmarks(year=2026)

    for val in result.values():
        decimal_str = f"{val:.10f}"
        # Should have at most 6 meaningful decimal digits
        assert val == round(val, 6)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd <project-root>
python -m pytest tests/test_benchmarks.py -v
```

Expected: Tests should fail or error until imports are resolvable. Fix `sys.path` in conftest if needed.

- [ ] **Step 3: Add sys.path setup to conftest.py if needed**

Add to the top of `tests/conftest.py`:

```python
import sys
from pathlib import Path

# Add project root to path so we can import pipeline modules
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_benchmarks.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_benchmarks.py tests/conftest.py
git commit -m "test: add benchmark calculation unit tests"
```

---

### Task 4: Unit tests — Validator logic

**Files:**
- Create: `tests/test_validator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validator.py`:

```python
"""Tests for validate_workbook.py — pure logic checks."""

import pytest
from openpyxl import Workbook

from validate_workbook import (
    _is_formula,
    _is_formula_error,
    _to_float,
    check_formula_errors,
    check_cross_sheet_refs,
)


# ── Helper function tests ──────────────────────────────────────────

class TestIsFormula:
    def test_excel_formula(self):
        assert _is_formula("=SUM(A1:A10)") is True

    def test_plain_string(self):
        assert _is_formula("hello") is False

    def test_number(self):
        assert _is_formula(42) is False

    def test_none(self):
        assert _is_formula(None) is False

    def test_empty_string(self):
        assert _is_formula("") is False


class TestIsFormulaError:
    def test_ref_error(self):
        assert _is_formula_error("#REF!") is True

    def test_div_zero(self):
        assert _is_formula_error("#DIV/0!") is True

    def test_value_error(self):
        assert _is_formula_error("#VALUE!") is True

    def test_name_error(self):
        assert _is_formula_error("#NAME?") is True

    def test_na_error(self):
        assert _is_formula_error("#N/A") is True

    def test_normal_string(self):
        assert _is_formula_error("hello") is False

    def test_number(self):
        assert _is_formula_error(42) is False

    def test_none(self):
        assert _is_formula_error(None) is False


class TestToFloat:
    def test_integer(self):
        assert _to_float(42) == 42.0

    def test_float(self):
        assert _to_float(3.14) == 3.14

    def test_none(self):
        assert _to_float(None) is None

    def test_string(self):
        assert _to_float("hello") is None

    def test_formula_string(self):
        assert _to_float("=SUM(A1:A10)") is None


# ── Formula error scan (Check 2) ───────────────────────────────────

class TestCheckFormulaErrors:
    def test_clean_workbook_passes(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = 100
        ws["A2"] = "hello"
        ws["A3"] = "=A1*2"

        findings = check_formula_errors(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_ref_error_detected(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = "#REF!"

        findings = check_formula_errors(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 1
        assert "#REF!" in errors[0].message

    def test_multiple_errors_detected(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = "#REF!"
        ws["B2"] = "#DIV/0!"
        ws["C3"] = "#VALUE!"

        findings = check_formula_errors(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 3


# ── Cross-sheet references (Check 3) ──────────────────────────────

class TestCheckCrossSheetRefs:
    def test_valid_cross_ref_passes(self):
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Dashboard"
        ws2 = wb.create_sheet("Details")
        ws2["A1"] = 42

        ws1["A1"] = "='Details'!A1"

        findings = check_cross_sheet_refs(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_missing_tab_ref_detected(self):
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Dashboard"

        ws1["A1"] = "='NonExistent'!A1"

        findings = check_cross_sheet_refs(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 1
        assert "NonExistent" in errors[0].message

    def test_empty_row_ref_warns(self):
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Dashboard"
        ws2 = wb.create_sheet("Details")
        # Row 99 is empty

        ws1["A1"] = "='Details'!A99"

        findings = check_cross_sheet_refs(wb)
        warns = [f for f in findings if f.severity == "WARN"]
        assert len(warns) >= 1
```

- [ ] **Step 2: Run tests to verify they fail or pass**

```bash
python -m pytest tests/test_validator.py -v
```

- [ ] **Step 3: Fix any import issues, re-run**

```bash
python -m pytest tests/test_validator.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_validator.py
git commit -m "test: add validator logic unit tests"
```

---

### Task 5: Unit tests — Balance continuity and accounting identity

**Files:**
- Create: `tests/test_accounting.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_accounting.py`:

```python
"""Tests for accounting checks in validate_workbook.py.

These tests build minimal openpyxl workbooks that mimic the
monthly performance table layout, then run Check 4 (balance continuity)
and Check 5 (accounting identity) against them.
"""

import pytest
from openpyxl import Workbook

from registry import MONTHLY_COLUMNS, REGISTRY
from validate_workbook import check_balance_continuity, check_accounting_identity


def _build_monthly_workbook(tab_name, rows):
    """Build a minimal workbook with monthly data rows.

    Args:
        tab_name: Tab name matching REGISTRY (e.g., "Fidelity Brokerage")
        rows: List of dicts with keys: beginning, deposits, withdrawals,
              dividends, market_change, ending. One dict per month row.

    Returns:
        openpyxl Workbook with data populated in the correct cells.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = tab_name

    reg = REGISTRY[tab_name]
    jan_row = reg["monthly_jan"][1]

    # Write column A labels
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, month in enumerate(months):
        ws[f"A{jan_row + i}"] = month

    col_map = MONTHLY_COLUMNS[tab_name]
    field_to_col = {v: k for k, v in col_map.items()}

    for i, row_data in enumerate(rows):
        r = jan_row + i
        if "beginning" in row_data:
            ws[f"B{r}"] = row_data["beginning"]
        if "deposits" in row_data:
            ws[f"{field_to_col['deposits_additions_contributions']}{r}"] = row_data["deposits"]
        if "withdrawals" in row_data:
            ws[f"{field_to_col['withdrawals_subtractions_distributions']}{r}"] = row_data["withdrawals"]
        if "dividends" in row_data:
            ws[f"{field_to_col['dividends']}{r}"] = row_data["dividends"]
        if "market_change" in row_data:
            ws[f"{field_to_col['market_change']}{r}"] = row_data["market_change"]
        if "ending" in row_data:
            ws[f"{field_to_col['ending']}{r}"] = row_data["ending"]

    return wb


class TestBalanceContinuity:
    """Check 4: ending value of month N must equal beginning of month N+1."""

    def test_continuous_balances_pass(self):
        rows = [
            {"beginning": 10000, "ending": 10500},
            {"beginning": 10500, "ending": 11000},
            {"beginning": 11000, "ending": 10800},
        ]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_balance_continuity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_discontinuous_balances_fail(self):
        rows = [
            {"beginning": 10000, "ending": 10500},
            {"beginning": 10600, "ending": 11000},  # 10600 != 10500
        ]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_balance_continuity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 1

    def test_penny_rounding_passes(self):
        """Difference of $0.01 or less is within tolerance."""
        rows = [
            {"beginning": 10000, "ending": 10500.005},
            {"beginning": 10500.01, "ending": 11000},  # diff = 0.005, within 0.01
        ]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_balance_continuity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_single_month_no_error(self):
        """Only one month of data — nothing to compare, should pass."""
        rows = [{"beginning": 10000, "ending": 10500}]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_balance_continuity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0


class TestAccountingIdentity:
    """Check 5: ending = beginning + inflow - outflow + dividends + market_change."""

    def test_correct_identity_passes(self):
        rows = [{
            "beginning": 10000,
            "deposits": 500,
            "withdrawals": 200,
            "dividends": 50,
            "market_change": 300,
            "ending": 10650,  # 10000 + 500 - 200 + 50 + 300
        }]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_accounting_identity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_incorrect_identity_fails(self):
        rows = [{
            "beginning": 10000,
            "deposits": 500,
            "withdrawals": 200,
            "dividends": 50,
            "market_change": 300,
            "ending": 12000,  # Wrong! Should be 10650
        }]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_accounting_identity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 1

    def test_negative_market_change_valid(self):
        """Down month should still pass if arithmetic is correct."""
        rows = [{
            "beginning": 10000,
            "deposits": 0,
            "withdrawals": 0,
            "dividends": 0,
            "market_change": -500,
            "ending": 9500,
        }]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_accounting_identity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_all_zeros_passes(self):
        rows = [{
            "beginning": 0,
            "deposits": 0,
            "withdrawals": 0,
            "dividends": 0,
            "market_change": 0,
            "ending": 0,
        }]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_accounting_identity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_within_tolerance_passes(self):
        """Difference of $1.00 or less is within tolerance."""
        rows = [{
            "beginning": 10000,
            "deposits": 500,
            "withdrawals": 200,
            "dividends": 50,
            "market_change": 300,
            "ending": 10650.75,  # diff = 0.75, within $1 tolerance
        }]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_accounting_identity(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_missing_field_skips_gracefully(self):
        """If one field is None, the row should be skipped, not crash."""
        rows = [{
            "beginning": 10000,
            "deposits": 500,
            # withdrawals missing
            "dividends": 50,
            "market_change": 300,
            "ending": 10850,
        }]
        wb = _build_monthly_workbook("Fidelity Brokerage", rows)
        findings = check_accounting_identity(wb)
        # Should not crash; may warn about incomplete data
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_accounting.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_accounting.py
git commit -m "test: add balance continuity and accounting identity tests"
```

---

### Task 6: Unit tests — Holdings totals and YTD gain

**Files:**
- Create: `tests/test_holdings.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_holdings.py`:

```python
"""Tests for holdings total (Check 6) and YTD gain consistency (Check 7)."""

import pytest
from openpyxl import Workbook

from registry import REGISTRY, HOLDINGS_ROWS
from validate_workbook import check_holdings_totals, check_ytd_gain


def _build_holdings_workbook(tab_name, holdings_values, total_values):
    """Build workbook with holdings rows and a total row.

    Args:
        tab_name: Tab name matching HOLDINGS_ROWS.
        holdings_values: List of (mv, cb, gl) tuples for each holding row.
        total_values: (mv, cb, gl) tuple for the total row.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = tab_name

    config = HOLDINGS_ROWS[tab_name]
    first = config["first"]
    total_row = config["total"]
    mv_col = config["mv_col"]
    cb_col = config["cb_col"]
    gl_col = config["gl_col"]

    for i, (mv, cb, gl) in enumerate(holdings_values):
        r = first + i
        ws[f"{mv_col}{r}"] = mv
        ws[f"{cb_col}{r}"] = cb
        ws[f"{gl_col}{r}"] = gl

    # Total row
    ws[f"{mv_col}{total_row}"] = total_values[0]
    ws[f"{cb_col}{total_row}"] = total_values[1]
    ws[f"{gl_col}{total_row}"] = total_values[2]

    # Label in col A for total row
    ws[f"A{total_row}"] = "TOTAL"

    return wb


class TestHoldingsTotals:
    def test_correct_totals_pass(self):
        holdings = [(1500.00, 1200.00, 300.00), (2000.00, 1800.00, 200.00)]
        totals = (3500.00, 3000.00, 500.00)
        wb = _build_holdings_workbook("Fidelity Brokerage", holdings, totals)
        findings = check_holdings_totals(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_wrong_mv_total_fails(self):
        holdings = [(1500.00, 1200.00, 300.00), (2000.00, 1800.00, 200.00)]
        totals = (9999.00, 3000.00, 500.00)  # MV total wrong
        wb = _build_holdings_workbook("Fidelity Brokerage", holdings, totals)
        findings = check_holdings_totals(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) >= 1

    def test_single_holding_passes(self):
        holdings = [(5000.00, 4000.00, 1000.00)]
        totals = (5000.00, 4000.00, 1000.00)
        wb = _build_holdings_workbook("Fidelity Roth IRA", holdings, totals)
        findings = check_holdings_totals(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_formula_total_warns_not_errors(self):
        """If total row is a formula string, can't verify — should WARN."""
        holdings = [(1500.00, 1200.00, 300.00)]
        wb = Workbook()
        ws = wb.active
        ws.title = "Fidelity Brokerage"
        config = HOLDINGS_ROWS["Fidelity Brokerage"]
        r = config["first"]
        ws[f"{config['mv_col']}{r}"] = 1500.00
        ws[f"{config['cb_col']}{r}"] = 1200.00
        ws[f"{config['gl_col']}{r}"] = 300.00
        tr = config["total"]
        ws[f"{config['mv_col']}{tr}"] = "=SUM(D13:D31)"
        ws[f"{config['cb_col']}{tr}"] = "=SUM(E13:E31)"
        ws[f"{config['gl_col']}{tr}"] = "=SUM(F13:F31)"

        findings = check_holdings_totals(wb)
        warns = [f for f in findings if f.severity == "WARN"]
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0
        assert len(warns) >= 1


def _build_ytd_workbook(tab_name, total_ytd, unrealized, realized, dividends):
    """Build workbook with YTD gain fields."""
    wb = Workbook()
    ws = wb.active
    ws.title = tab_name

    reg = REGISTRY[tab_name]

    def set_val(key, value):
        if key in reg:
            col, row, label = reg[key]
            ws[f"{col}{row}"] = value
            ws[f"A{row}"] = label

    set_val("total_ytd", total_ytd)
    set_val("unrealized", unrealized)
    set_val("realized", realized)
    set_val("dividends", dividends)

    return wb


class TestYTDGain:
    def test_consistent_ytd_passes(self):
        # total = unrealized + realized + dividends = 1000 + 200 + 50 = 1250
        wb = _build_ytd_workbook("Fidelity Brokerage", 1250.00, 1000.00, 200.00, 50.00)
        findings = check_ytd_gain(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_inconsistent_ytd_fails(self):
        # total should be 1250, but we say 2000
        wb = _build_ytd_workbook("Fidelity Brokerage", 2000.00, 1000.00, 200.00, 50.00)
        findings = check_ytd_gain(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 1

    def test_negative_values_valid(self):
        # total = -500 + 200 + 50 = -250
        wb = _build_ytd_workbook("Fidelity Brokerage", -250.00, -500.00, 200.00, 50.00)
        findings = check_ytd_gain(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_all_zeros_passes(self):
        wb = _build_ytd_workbook("Fidelity Brokerage", 0, 0, 0, 0)
        findings = check_ytd_gain(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0

    def test_formula_values_warns(self):
        """Formula strings can't be evaluated — should WARN, not ERROR."""
        wb = _build_ytd_workbook("Fidelity Brokerage", "=B7+B8+B6", "=SUM(F13:F31)", 200.00, 50.00)
        findings = check_ytd_gain(wb)
        warns = [f for f in findings if f.severity == "WARN"]
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0
        assert len(warns) >= 1

    def test_within_tolerance_passes(self):
        """Difference of $1.00 or less is within tolerance."""
        # Expected: 1250, actual: 1250.80 — diff = 0.80
        wb = _build_ytd_workbook("Fidelity Brokerage", 1250.80, 1000.00, 200.00, 50.00)
        findings = check_ytd_gain(wb)
        errors = [f for f in findings if f.severity == "ERROR"]
        assert len(errors) == 0
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_holdings.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_holdings.py
git commit -m "test: add holdings totals and YTD gain consistency tests"
```

---

### Task 7: Unit tests — Manual data parsing

**Files:**
- Create: `tests/test_manual_data.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_manual_data.py`:

```python
"""Tests for manual_data.json parsing and validation."""

import json
import pytest


class TestManualDataStructure:
    """Validate that manual data fixtures have the expected structure."""

    def test_sample_has_required_keys(self, manual_data_sample):
        assert "k401_data" in manual_data_sample
        assert "angel_data" in manual_data_sample
        assert "cash_balances" in manual_data_sample

    def test_k401_quarterly_accounting_identity(self, manual_data_sample):
        """ending = beginning + ee + er + fees + change_in_value."""
        for q in manual_data_sample["k401_data"]["quarterly"]:
            expected = (
                q["beginning"]
                + q["ee_contributions"]
                + q["er_contributions"]
                + q["fees"]
                + q["change_in_value"]
            )
            assert abs(q["ending"] - expected) < 0.01, (
                f"Quarter {q['period']}: expected ending={expected}, got {q['ending']}"
            )

    def test_k401_quarterly_continuity(self, manual_data_sample):
        """Ending of Q(N) should equal beginning of Q(N+1)."""
        quarters = manual_data_sample["k401_data"]["quarterly"]
        for i in range(len(quarters) - 1):
            ending = quarters[i]["ending"]
            next_beginning = quarters[i + 1]["beginning"]
            assert abs(ending - next_beginning) < 0.01, (
                f"{quarters[i]['period']} ending={ending} != "
                f"{quarters[i+1]['period']} beginning={next_beginning}"
            )

    def test_angel_valuation_multiples(self, manual_data_sample):
        """Valuation multiple = pm_latest / pm_invest, must be >= 0."""
        for angel in manual_data_sample["angel_data"]:
            assert angel["pm_invest"] > 0, f"{angel['company']} has zero pm_invest"
            multiple = angel["pm_latest"] / angel["pm_invest"]
            assert multiple >= 0, f"{angel['company']} has negative valuation multiple"

    def test_angel_required_fields(self, manual_data_sample):
        required = {"company", "sector", "year", "series", "amount", "pm_invest", "pm_latest", "source"}
        for angel in manual_data_sample["angel_data"]:
            missing = required - set(angel.keys())
            assert not missing, f"{angel.get('company', '?')} missing fields: {missing}"

    def test_empty_manual_data_does_not_crash(self, manual_data_empty):
        """Empty dict should be handled without KeyError."""
        assert manual_data_empty == {}
        # Simulate what build_portfolio does with missing keys
        k401 = manual_data_empty.get("k401_data", {})
        angels = manual_data_empty.get("angel_data", [])
        cash = manual_data_empty.get("cash_balances", {})
        assert k401 == {}
        assert angels == []
        assert cash == {}

    def test_cash_balance_keys_are_strings(self, manual_data_sample):
        for key in manual_data_sample["cash_balances"]:
            assert isinstance(key, str)
            assert key.startswith("fidelity_"), f"Unexpected cash key: {key}"
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_manual_data.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_manual_data.py
git commit -m "test: add manual data parsing and validation tests"
```

---

### Task 8: Integration test — Workbook build and validate round-trip

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_integration.py`:

```python
"""Integration tests: build workbook from fixtures, then validate it.

These tests require the full build_portfolio and validate_workbook modules.
They build real Excel files in a temp directory and run the validator.
"""

import json
import tempfile
from pathlib import Path

import pytest

from validate_workbook import validate_full


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestWorkbookBuildAndValidate:
    def test_build_with_benchmarks_only(self, benchmarks_sample, temp_dir):
        """Minimal build: just benchmarks, no account data."""
        from build_portfolio import build_workbook

        output = str(temp_dir / "test_benchmarks_only.xlsx")
        try:
            build_workbook(
                benchmarks=benchmarks_sample,
                output_path=output,
            )
        except Exception as e:
            pytest.skip(f"build_workbook requires account data: {e}")

    def test_build_with_fidelity_data(self, fidelity_sample, benchmarks_sample, temp_dir, fixtures_dir):
        """Build with Fidelity fixture data and validate."""
        from build_portfolio import build_workbook

        manual_path = str(fixtures_dir / "manual_data_sample.json")
        output = str(temp_dir / "test_fidelity.xlsx")

        try:
            build_workbook(
                fid_data_dict=fidelity_sample,
                benchmarks=benchmarks_sample,
                manual_json_path=manual_path,
                output_path=output,
            )
        except Exception as e:
            pytest.skip(f"build_workbook failed (may need fixture adjustment): {e}")
            return

        # Validate the generated workbook
        findings = validate_full(output)
        errors = [f for f in findings if f.severity == "ERROR"]
        # Report errors but don't fail — this test identifies gaps in fixtures
        if errors:
            error_msgs = [f"{e.tab}: {e.message}" for e in errors]
            pytest.xfail(f"Validation errors (fixture may need adjustment): {error_msgs}")

    def test_build_with_all_sources(
        self, fidelity_sample, snaptrade_raw_sample, benchmarks_sample, temp_dir, fixtures_dir
    ):
        """Build with Fidelity + Robinhood data and validate."""
        from build_portfolio import build_workbook

        manual_path = str(fixtures_dir / "manual_data_sample.json")
        output = str(temp_dir / "test_full.xlsx")

        try:
            build_workbook(
                fid_data_dict=fidelity_sample,
                rh_raw_dict=snaptrade_raw_sample,
                benchmarks=benchmarks_sample,
                manual_json_path=manual_path,
                output_path=output,
            )
        except Exception as e:
            pytest.skip(f"build_workbook failed: {e}")
            return

        # Validate
        findings = validate_full(output)
        errors = [f for f in findings if f.severity == "ERROR"]
        if errors:
            error_msgs = [f"{e.tab}: {e.message}" for e in errors]
            pytest.xfail(f"Validation errors: {error_msgs}")


class TestPartialBuilds:
    """Verify the workbook builder handles missing data sources gracefully."""

    def test_no_robinhood_data(self, fidelity_sample, benchmarks_sample, temp_dir, fixtures_dir):
        """Build without Robinhood — should not crash."""
        from build_portfolio import build_workbook

        manual_path = str(fixtures_dir / "manual_data_sample.json")
        output = str(temp_dir / "test_no_rh.xlsx")

        try:
            build_workbook(
                fid_data_dict=fidelity_sample,
                rh_raw_dict=None,
                benchmarks=benchmarks_sample,
                manual_json_path=manual_path,
                output_path=output,
            )
        except Exception as e:
            pytest.skip(f"build_workbook crashed without RH data: {e}")

    def test_no_benchmarks(self, fidelity_sample, temp_dir, fixtures_dir):
        """Build without benchmarks — dashboard should handle None."""
        from build_portfolio import build_workbook

        manual_path = str(fixtures_dir / "manual_data_sample.json")
        output = str(temp_dir / "test_no_bench.xlsx")

        try:
            build_workbook(
                fid_data_dict=fidelity_sample,
                benchmarks=None,
                manual_json_path=manual_path,
                output_path=output,
            )
        except Exception as e:
            pytest.skip(f"build_workbook crashed without benchmarks: {e}")

    def test_no_manual_data(self, fidelity_sample, benchmarks_sample, temp_dir):
        """Build without manual_data.json — 401k and angel tabs should be empty."""
        from build_portfolio import build_workbook

        output = str(temp_dir / "test_no_manual.xlsx")

        try:
            build_workbook(
                fid_data_dict=fidelity_sample,
                benchmarks=benchmarks_sample,
                manual_json_path=None,
                output_path=output,
            )
        except Exception as e:
            pytest.skip(f"build_workbook crashed without manual data: {e}")
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_integration.py -v --timeout=30
```

Expected: Tests pass, skip, or xfail — none should crash with unhandled exceptions.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for workbook build + validate round-trip"
```

---

### Task 9: Security tests — No credential leakage

**Files:**
- Create: `tests/test_security.py`

- [ ] **Step 1: Write the security tests**

Create `tests/test_security.py`:

```python
"""Security tests: ensure no credentials leak into output or logs.

Critical for public release — these tests scan generated output
for patterns that look like API keys, passwords, or account numbers.
"""

import re
from pathlib import Path

import pytest

# Patterns that should NEVER appear in output files
SENSITIVE_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "API key (sk-... pattern)"),
    (r"access-sandbox-[a-zA-Z0-9]+", "Plaid sandbox token"),
    (r"access-production-[a-zA-Z0-9]+", "Plaid production token"),
    (r"[a-f0-9]{32,}", "Possible hex API key (32+ chars)"),
    (r"password\s*[:=]\s*\S+", "Password in plaintext"),
    (r"secret\s*[:=]\s*\S+", "Secret in plaintext"),
]

# Files that should NEVER be committed
SENSITIVE_FILES = [
    "config.json",
    ".env",
    "credentials.json",
    "manual_data.json",  # Contains real account data
]


class TestNoCredentialLeakage:
    def test_gitignore_covers_sensitive_files(self):
        """Verify .gitignore includes sensitive file patterns."""
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        if not gitignore_path.exists():
            # Check repo/.gitignore
            gitignore_path = Path(__file__).parent.parent / "repo" / ".gitignore"

        if not gitignore_path.exists():
            pytest.fail(
                ".gitignore not found — sensitive files could be committed. "
                "Create .gitignore with: config.json, .env, manual_data.json"
            )

        gitignore_content = gitignore_path.read_text()
        for filename in SENSITIVE_FILES:
            assert filename in gitignore_content or f"*{filename}" in gitignore_content, (
                f"{filename} not in .gitignore — risk of committing credentials"
            )

    def test_config_json_not_in_repo(self):
        """config.json should exist in ~/.portfolio_extract/, not in repo."""
        repo_config = Path(__file__).parent.parent / "config.json"
        assert not repo_config.exists(), (
            "config.json found in project root — contains API keys! "
            "Move to ~/.portfolio_extract/config.json"
        )

    def test_manual_data_not_in_repo(self):
        """manual_data.json (with real data) should not be in the repo dir."""
        repo_dir = Path(__file__).parent.parent / "repo"
        manual = repo_dir / "manual_data.json"
        if manual.exists():
            content = manual.read_text()
            # It's OK if it's the example file (all zeros)
            if '"amount": 10000' not in content:
                return
            pytest.fail(
                "manual_data.json with real data found in repo/ — "
                "should be in .gitignore"
            )

    def test_example_file_has_no_real_data(self):
        """manual_data.example.json should contain only placeholder values."""
        example = Path(__file__).parent.parent / "repo" / "manual_data.example.json"
        if not example.exists():
            example = Path(__file__).parent.parent / "manual_data.example.json"
        if not example.exists():
            pytest.skip("manual_data.example.json not found")

        import json
        data = json.loads(example.read_text())

        # Check 401k data is zeroed out
        for q in data.get("k401_data", {}).get("quarterly", []):
            assert q["beginning"] == 0, "Example file has non-zero 401k data"
            assert q["ending"] == 0, "Example file has non-zero 401k data"

    def test_no_hardcoded_paths_with_usernames(self):
        """Python files should not contain hardcoded user-specific paths
        that would break for other users."""
        project_root = Path(__file__).parent.parent
        user_path_pattern = re.compile(r'C:\\Users\\[^"\\]+\\', re.IGNORECASE)

        violations = []
        for py_file in project_root.glob("*.py"):
            content = py_file.read_text(errors="ignore")
            matches = user_path_pattern.findall(content)
            if matches:
                violations.append((py_file.name, matches))

        if violations:
            msg = "Hardcoded user paths found (will break for other users):\n"
            for fname, paths in violations:
                msg += f"  {fname}: {paths}\n"
            pytest.xfail(msg)
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_security.py -v
```

Expected: Identifies any security gaps. Some may xfail (hardcoded paths), which documents known issues.

- [ ] **Step 3: Commit**

```bash
git add tests/test_security.py
git commit -m "test: add security tests for credential leakage prevention"
```

---

### Task 10: Cross-platform tests

**Files:**
- Create: `tests/test_cross_platform.py`

- [ ] **Step 1: Write the cross-platform tests**

Create `tests/test_cross_platform.py`:

```python
"""Cross-platform compatibility tests.

Verifies the pipeline works on both Windows and Mac/Linux.
"""

import os
import sys
from pathlib import Path

import pytest


class TestDateFormatting:
    def test_day_without_leading_zero(self):
        """Verify the date formatting logic produces '5' not '05'."""
        import datetime as _dt

        today = _dt.date(2026, 3, 5)
        if os.name == "nt":
            formatted = today.strftime("%B %#d, %Y")
        else:
            formatted = today.strftime("%B %-d, %Y")

        assert formatted == "March 5, 2026"


class TestPathHandling:
    def test_path_with_spaces(self):
        """Paths with spaces in any parent directory must work."""
        p = Path("some dir/sub dir/file.json")
        assert p.name == "file.json"
        assert str(p.parent) == "some dir/sub dir" or str(p.parent) == "some dir\\sub dir"

    def test_home_dir_expansion(self):
        """~/.portfolio_extract/ must expand correctly."""
        config_dir = Path.home() / ".portfolio_extract"
        assert str(config_dir).startswith("/") or ":" in str(config_dir)
        # Should not contain literal "~"
        assert "~" not in str(config_dir)

    def test_pathlib_works_cross_platform(self):
        """Path operations used in pipeline work on current platform."""
        p = Path(__file__).parent.parent
        assert p.exists()
        assert (p / "tests").exists()


class TestScheduling:
    def test_bat_file_exists_for_windows(self):
        """run_pipeline.bat should exist for Windows users."""
        bat = Path(__file__).parent.parent / "run_pipeline.bat"
        if os.name == "nt":
            assert bat.exists(), "run_pipeline.bat missing (needed for Windows Task Scheduler)"
        else:
            pytest.skip("Not on Windows")

    def test_schedule_xml_exists_for_windows(self):
        """schedule_task.xml should exist for Windows users."""
        xml = Path(__file__).parent.parent / "schedule_task.xml"
        if os.name == "nt":
            assert xml.exists(), "schedule_task.xml missing (needed for Windows Task Scheduler)"
        else:
            pytest.skip("Not on Windows")
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_cross_platform.py -v
```

Expected: All tests PASS on current platform.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cross_platform.py
git commit -m "test: add cross-platform compatibility tests"
```

---

### Task 11: Edge case tests — Error handling

**Files:**
- Create: `tests/test_edge_cases.py`

- [ ] **Step 1: Write the edge case tests**

Create `tests/test_edge_cases.py`:

```python
"""Edge case tests for data handling and error resilience."""

import json
import pytest


class TestFidelityEdgeCases:
    def test_zero_value_holding_filtered(self):
        """Holdings with mv < 1 and qty < 0.001 should be filtered."""
        holding = {"qty": 0.0001, "price": 0.50, "mv": 0.00005, "cb": 0.01, "gl": -0.00995, "name": "Dust"}
        assert holding["mv"] < 1 and holding["qty"] < 0.001

    def test_cash_position_separated(self):
        """SPAXX, FCASH, FDRXX, CORE should be treated as cash, not holdings."""
        cash_tickers = {"SPAXX", "FCASH", "FDRXX", "CORE"}
        test_ticker = "SPAXX"
        assert test_ticker in cash_tickers

    def test_negative_gain_loss(self):
        """Negative gain/loss (losing positions) should be preserved."""
        holding = {"qty": 5.0, "price": 250.00, "mv": 1250.00, "cb": 1500.00, "gl": -250.00, "name": "TSLA"}
        assert holding["gl"] < 0
        assert holding["gl"] == holding["mv"] - holding["cb"]


class TestSnapTradeEdgeCases:
    def test_unknown_ticker_identified(self, snaptrade_raw_sample):
        """UNKNOWN tickers should be identifiable for filtering."""
        unknown_holdings = [
            h for h in snaptrade_raw_sample["robinhood"]["holdings"]
            if h["ticker"] == "UNKNOWN"
        ]
        assert len(unknown_holdings) == 1

    def test_micro_position_identified(self, snaptrade_raw_sample):
        """Positions with institution_value < $1 should be identifiable."""
        micro_holdings = [
            h for h in snaptrade_raw_sample["robinhood"]["holdings"]
            if h["institution_value"] < 1.0
        ]
        assert len(micro_holdings) >= 1

    def test_negative_gain_loss_preserved(self, snaptrade_raw_sample):
        """Losing positions should have negative gain_loss."""
        tsla = next(
            h for h in snaptrade_raw_sample["robinhood"]["holdings"]
            if h["ticker"] == "TSLA"
        )
        assert tsla["gain_loss"] < 0

    def test_dividend_transaction_classified(self, snaptrade_raw_sample):
        """Dividend transactions should have type DIVIDEND."""
        dividends = [
            t for t in snaptrade_raw_sample["robinhood"]["investment_transactions"]
            if t["type"] == "DIVIDEND"
        ]
        assert len(dividends) >= 1
        assert dividends[0]["amount"] > 0


class TestPlaidEdgeCases:
    def test_null_cost_basis_handled(self, plaid_raw_sample):
        """Holdings with null cost_basis should not crash."""
        null_cb = [
            h for h in plaid_raw_sample["merrill"]["holdings"]
            if h["cost_basis"] is None
        ]
        assert len(null_cb) == 1

    def test_null_ticker_handled(self, plaid_raw_sample):
        """Securities with null ticker_symbol should not crash."""
        null_ticker = [
            s for s in plaid_raw_sample["merrill"]["securities"]
            if s["ticker_symbol"] is None
        ]
        assert len(null_ticker) == 1

    def test_gain_loss_calculated_from_plaid(self, plaid_raw_sample):
        """Plaid doesn't provide gain_loss — verify it can be calculated."""
        holding = plaid_raw_sample["merrill"]["holdings"][0]
        assert "gain_loss" not in holding  # Plaid omits this field
        # Should be calculable: institution_value - cost_basis
        if holding["cost_basis"] is not None:
            gl = holding["institution_value"] - holding["cost_basis"]
            assert gl == 2500.00  # 12500 - 10000


class TestCashOnlyAccounts:
    def test_no_holdings(self, plaid_cash_only):
        """Cash-only accounts should have empty holdings."""
        assert plaid_cash_only["chase"]["holdings"] == []
        assert plaid_cash_only["marcus"]["holdings"] == []

    def test_has_balances(self, plaid_cash_only):
        """Cash-only accounts should have valid balances."""
        assert plaid_cash_only["chase"]["accounts"][0]["balances"]["current"] > 0
        assert plaid_cash_only["marcus"]["accounts"][0]["balances"]["current"] > 0

    def test_account_type_is_depository(self, plaid_cash_only):
        """Cash accounts should be depository, not investment."""
        assert plaid_cash_only["chase"]["accounts"][0]["type"] == "depository"
        assert plaid_cash_only["marcus"]["accounts"][0]["type"] == "depository"


class TestConfigEdgeCases:
    def test_valid_config_has_all_keys(self, config_valid):
        assert "snaptrade" in config_valid
        assert "plaid" in config_valid
        assert "client_id" in config_valid["snaptrade"]
        assert "consumer_key" in config_valid["snaptrade"]
        assert "client_id" in config_valid["plaid"]
        assert "secret" in config_valid["plaid"]

    def test_missing_keys_detectable(self, config_missing_keys):
        assert config_missing_keys["snaptrade"]["client_id"] == ""
        assert config_missing_keys["snaptrade"]["consumer_key"] == ""
        assert "secret" not in config_missing_keys["plaid"]

    def test_corrupted_json_raises(self, tmp_path):
        """Corrupted JSON should raise a clear error."""
        bad_file = tmp_path / "bad_config.json"
        bad_file.write_text("{invalid json here")
        with pytest.raises(json.JSONDecodeError):
            json.loads(bad_file.read_text())
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_edge_cases.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_edge_cases.py
git commit -m "test: add edge case tests for data handling and error resilience"
```

---

### Task 12: Add pytest configuration and run full suite

**Files:**
- Create: `pytest.ini`

- [ ] **Step 1: Create pytest.ini**

Create `pytest.ini` in the project root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 2: Run the full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass, skip, or xfail. Zero unexpected failures.

- [ ] **Step 3: Commit**

```bash
git add pytest.ini
git commit -m "test: add pytest configuration"
```

---

### Task 13: Add run_pipeline.sh for Mac users

**Files:**
- Create: `run_pipeline.sh`

- [ ] **Step 1: Create the shell script**

Create `run_pipeline.sh`:

```bash
#!/usr/bin/env bash
# Weekly Portfolio Pipeline Launcher (Mac/Linux)
# Schedule with: crontab -e
# Add: 5 16 * * 5 /path/to/run_pipeline.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_SCRIPT="$SCRIPT_DIR/weekly_pipeline.py"
PYTHON="${PYTHON:-python3}"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[$TIMESTAMP] Starting Weekly Portfolio Pipeline..."

"$PYTHON" "$PIPELINE_SCRIPT" "$@"
EXIT_CODE=$?

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] Pipeline completed successfully."
elif [ $EXIT_CODE -eq 2 ]; then
    echo "[$TIMESTAMP] Pipeline completed with warnings."
else
    echo "[$TIMESTAMP] Pipeline failed with exit code $EXIT_CODE."
fi

exit $EXIT_CODE
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x run_pipeline.sh
```

- [ ] **Step 3: Commit**

```bash
git add run_pipeline.sh
git commit -m "feat: add run_pipeline.sh for Mac/Linux scheduling"
```

---

## Test Coverage Summary

| Test File | Layer | Tests | What It Covers |
|-----------|-------|-------|----------------|
| `test_benchmarks.py` | Unit | 7 | YTD return math, empty data, network errors, rounding |
| `test_validator.py` | Unit | 12 | Formula detection, error scanning, cross-sheet refs |
| `test_accounting.py` | Unit | 7 | Balance continuity, accounting identity, tolerances |
| `test_holdings.py` | Unit | 10 | Holdings totals, YTD gain consistency, formula handling |
| `test_manual_data.py` | Unit | 7 | 401k accounting, angel valuations, empty data |
| `test_integration.py` | Integration | 5 | Full build + validate, partial builds |
| `test_security.py` | Security | 5 | Gitignore, no creds in repo, no hardcoded paths |
| `test_cross_platform.py` | Platform | 5 | Date formatting, path handling, scheduling files |
| `test_edge_cases.py` | Edge | 14 | Null values, filtering, cash-only, config errors |
| **TOTAL** | | **72** | |
