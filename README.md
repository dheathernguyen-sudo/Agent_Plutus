# Agent Plutus

**See all your investments in one place.** The agent automatically pulls your latest balances from Fidelity, Robinhood, your 401(k), and other accounts — then builds a single Excel report showing how your money is doing daily, plus a one-page advisor brief that interprets it in plain English.

**Privacy first:** Your raw financial data — holdings, account numbers, balances, credentials — never leaves your machine. The optional advisor brief sends a *summary* of findings (severities, percentages, headlines) to Anthropic's API to compose the narrative; without an API key, it falls back to a deterministic local-only brief. See [Your Advisor Brief](#your-advisor-brief) for details.

## What It Does

If you have investments spread across multiple apps, you probably have no idea how your total portfolio is actually performing. Each app shows you a piece, but none shows the whole picture. This tool fixes that.

1. **Connects to your accounts** — securely pulls your latest balances and holdings from each brokerage via read-only APIs
2. **Compares you to the market** — grabs S&P 500, Dow Jones, and NASDAQ performance so you can see if you're ahead or behind
3. **Builds your daily report** — creates one Excel file with everything organized by account
4. **Tracks changes over time** — saves daily snapshots so you can see how your portfolio moved day to day
5. **Writes you a one-page advisor brief** — runs your portfolio through ~15 standard CFP-style health checks (concentration risk, glide path, cash buffer, tax-loss opportunities, etc.) and asks Claude to turn the results into calm, plain-English narrative — not "buy this stock," more "your margin debt is 47% of equity; here's what that means and a commonly recommended response"

## What You'll See

Your report is an Excel workbook with these pages:

- **Dashboard** — your total net worth across all accounts, whether you're beating the market, and where your money is concentrated
- **Account pages** (Fidelity Brokerage, Roth IRA, HSA, Robinhood, 401k) — what you own in each account, what you paid for it, and your profit or loss
- **Angel Investments** — if you have any private company investments, they're tracked here with automatic valuation lookups
- **Cash** — liquid balances across checking, savings, and brokerage cash positions
- **Recommendations** — a one-page advisor brief interpreting your portfolio's health (see [Your Advisor Brief](#your-advisor-brief))

### Sample Report

**Dashboard** — benchmark comparison, YTD gains, account overview, and sector concentration at a glance. Dollar amounts are redacted; returns and percentages are real.

![Dashboard](docs/screenshots/Dashboard.png)

**Account tab** — each brokerage account gets its own page with return metrics, gain/loss summary, and current holdings.

![Account Tab](docs/screenshots/Fidelity_Brokerage.png)

**Recommendations tab** — the advisor brief, grouped into Immediate Priority, Active Concerns, and Opportunities, with severity-coded rows and per-finding narrative. Synthetic example below (no real holdings shown).

![Recommendations](docs/screenshots/Recommendations.png)

## Your Advisor Brief

Every workbook also includes a **Recommendations** tab — a one-page executive summary of your portfolio's health, written in plain English by Claude (Anthropic's LLM). It runs 15 CFP-style health checks (concentration, leverage, glide path, tax-loss, etc.), classifies each finding by severity (urgent / attention / context / positive), and respects "hard rules" from your profile (e.g. *"never sell NVDA"*). Tone is calm and educational, never prescriptive — see the screenshot above for an example. Lifecycle checks (glide path, retirement risk, employer stock, emergency fund) only fire if your profile is configured; without one, you still get the rest. Day-over-day, the brief surfaces *new* findings with fresh narrative and reminds you of *standing* concerns in one line each.

Profile setup is in [Step 8 of Getting Started](#step-8-optional-set-up-your-advisor-profile). Without one, the advisor still runs the 10 portfolio-only checks; the 5 lifecycle-aware checks just sit out.

### Privacy and API key

Findings (severity, category, headline, detail JSON) plus a profile summary are sent to Anthropic's API to compose the brief. **Raw holdings, account numbers, and credentials never leave your machine.**

**No API key? The advisor still works.** All 15 checks run identically — you get the same Recommendations tab with the same severity-classified findings and day-over-day diff. What you lose is the LLM-generated narrative: instead of *"Historically, when margin debt approaches 50%..."*, you get the bare headline *"[URGENT] Margin debt is 47% of net equity"*. The tab title also gets a *"(LLM narrator unavailable — findings only)"* suffix so it's clear you're in fallback mode. Fully local, no network call.

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

## Before You Start

Quick self-check before investing setup time:

- ✅ You have at least one account at Fidelity, Robinhood, Merrill Lynch, Chase, Marcus, or another supported institution
- ✅ You're comfortable spending **30–60 minutes** on initial setup
- ⚠️ The advisor's *narrative* (the plain-English interpretation) requires a paid [Anthropic API key](#anthropic-optional--for-the-advisors-narrative) — typically a few cents per daily run. Skip it and you still get the workbook plus structured findings; you just lose the narrative wrapper.
- 💡 Never used a terminal or edited JSON before? You don't need to know either ahead of time — Steps 1–10 walk you through every command and the example files are heavily annotated.

If those are workable, continue.

## Getting Started

**Initial setup takes 30–60 minutes** the first time. After that, the tool runs automatically every weekday and your report is waiting for you.

### What You'll Need

- **A computer** — Windows 10+, macOS 12+, or Linux
- **Python 3.12 or newer** — [download here](https://www.python.org/downloads/)
- **A code editor** — [VS Code](https://code.visualstudio.com/) (free) or Notepad++ (Windows). **Don't use regular Notepad** — it can corrupt the JSON config files.
- **Your brokerage login credentials** — stored locally on your machine
- **Free API keys** from two services (instructions below)

### Step 1: Install Python

1. Download Python 3.12+ from [python.org/downloads](https://www.python.org/downloads/) and run the installer.
2. **⚠️ On Windows, check the box "Add Python to PATH" on the first installer screen.** If you skip this, the `python` and `pip` commands won't work in your terminal — and re-installing is the easiest fix.
3. After install, verify by opening a terminal (next step) and running `python --version`. You should see something like `Python 3.12.x`. On macOS you may need `python3` instead of `python` everywhere in this guide.

### Step 2: Open a Terminal

You'll be running a handful of commands in your computer's terminal (also called "command line" or "shell").

- **Windows:** Press `Win + R`, type `cmd`, press Enter. Or right-click the Start button and choose "Terminal" / "Windows PowerShell".
- **macOS:** Press `Cmd + Space`, type `Terminal`, press Enter.
- **Linux:** Press `Ctrl + Alt + T`, or search for "Terminal" in your applications.

You'll know you're in a terminal when you see a blinking cursor after text like `C:\Users\you>` (Windows) or `you@machine ~ $` (Mac/Linux). You type a command, press Enter, and read the output.

### Step 3: Download the Code

Easiest path — download a ZIP:

1. Go to [github.com/dheathernguyen-sudo/Agent_Plutus](https://github.com/dheathernguyen-sudo/Agent_Plutus)
2. Click the green **Code** button → **Download ZIP**
3. Unzip the folder somewhere memorable, e.g. `C:\Users\you\agent-plutus` (Windows) or `~/agent-plutus` (Mac/Linux)
4. In your terminal, **navigate into that folder**:

   ```
   cd C:\Users\you\agent-plutus       (Windows)
   cd ~/agent-plutus                  (Mac/Linux)
   ```

If you already have **git** installed, you can clone instead:

```
git clone https://github.com/dheathernguyen-sudo/Agent_Plutus.git
cd Agent_Plutus
```

✅ **Verify:** type `dir` (Windows) or `ls` (Mac/Linux). You should see `requirements.txt`, `daily_pipeline.py`, and folders like `data/`, `advisor/`, `extractors/`.

### Step 4: Install Dependencies

```
pip install -r requirements.txt
```

This installs the Python libraries the tool needs (openpyxl for Excel, anthropic for the advisor, plaid-python, snaptrade-python-sdk, etc.). Takes about a minute.

✅ **Verify:** the last line should be something like `Successfully installed ...`.

### Step 5: Get Your API Keys

You'll need free developer accounts from two services for brokerage data — and optionally a third (Anthropic) if you want the advisor's LLM-generated narrative.

#### SnapTrade (for Robinhood + Fidelity)

1. Sign up at [dashboard.snaptrade.com/signup](https://dashboard.snaptrade.com/signup)
2. Verify your email
3. Generate an API key from the dashboard

You'll get a **Client ID** and **Consumer Key** — save both. Access is instant after email verification, no approval process.

The free tier includes 5 brokerage connections, which is enough for most users. Beyond that, it's $1.50/user/month with no minimums.

#### Plaid (for 401k, checking, savings)

1. Sign up at [dashboard.plaid.com/signup](https://dashboard.plaid.com/signup)
2. Choose the **Trial** plan — it's free, instant, and supports up to 10 real brokerage accounts. No approval process.
3. Go to **Developers > Keys** to find your **Client ID** and **Secret**
4. Enable the **Investments** product in your dashboard (required for 401k holdings)

#### Anthropic (Optional — for the advisor's narrative)

Skip this and the advisor still runs and writes the Recommendations tab — you just won't get the LLM-generated narrative. See [Privacy and API key](#privacy-and-api-key) for the trade-off.

To enable the narrative version:

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Add a payment method — there is no free tier. The advisor uses Claude Opus 4.7 with prompt caching, so a daily run typically costs a few cents. Check current rates at [anthropic.com/pricing](https://www.anthropic.com/pricing).
3. Create an API key under **Settings → API Keys** (it starts with `sk-ant-`)
4. Save the key as a single line in `<project>/.anthropic_key` (gitignored — never commit this file)

The pipeline reads `.anthropic_key` automatically; no env var needed.

### Step 6: Connect Your Accounts

Run the interactive setup — it'll prompt for the keys you got in Step 5 and walk you through linking each brokerage:

```
python extractors/plaid_extract.py --setup
```

If using the Fidelity browser-automation fallback (needed only if SnapTrade can't reach your Fidelity account):

```
python extractors/fidelity_extract.py
```

✅ **Verify:** the setup script should report each account it linked. The credentials and tokens are saved to `~/.portfolio_extract/config.json` (a hidden folder in your home directory) — never to the project folder, never to the cloud.

### Step 7: Set Up Your Account Data

Copy the example templates to working files and fill in your details. **Open them in your code editor** (VS Code or Notepad++ — *not* regular Notepad).

**Windows (cmd or PowerShell):**
```
copy data\fidelity_brokerage.example.json data\fidelity_brokerage.json
copy data\robinhood.example.json data\robinhood.json
copy data\k401.example.json data\k401.json
copy manual_data.example.json manual_data.json
```

**Mac/Linux:**
```
cp data/fidelity_brokerage.example.json data/fidelity_brokerage.json
cp data/robinhood.example.json data/robinhood.json
cp data/k401.example.json data/k401.json
cp manual_data.example.json manual_data.json
```

Then edit each `.json` file in your editor. The example files are heavily commented to show what each field means and which are required vs. optional.

> **JSON tips for first-time editors:** keep the quotes `"like this"` around keys and string values, keep the commas between items, keep brackets matching. If the pipeline complains about JSON later, paste the file contents into [jsonlint.com](https://jsonlint.com/) — most breakage is a missing comma or unbalanced brace.

✅ **Verify:** you have one `.json` file per account you want to track, alongside the corresponding `.example.json`. The real ones are gitignored — they never leave your machine.

### Step 8: (Optional) Set Up Your Advisor Profile

The advisor reads `user_profile.json` (gitignored — stays local) to enable lifecycle-aware checks (glide path, retirement risk, emergency fund, employer-stock concentration).

1. Copy the template:
   - **Windows:** `copy user_profile.example.json user_profile.json`
   - **Mac/Linux:** `cp user_profile.example.json user_profile.json`
2. Open `user_profile.json` in your code editor — it's plain JSON.
3. Set your birth year, target retirement year, risk tolerance, and any hard rules. Save.

The next pipeline run picks it up automatically — no restart needed. The annotated template shows every field, what it does, and which observation it powers (age → glide path; retirement year → lifecycle risk; employer ticker → employer stock check; etc.). All fields are optional. If the file is missing or malformed, the advisor logs a warning and runs with defaults rather than failing — so you can iterate on it without breaking your daily run.

> **What if I skip this step?** The advisor still runs and produces a brief — but ~5 of the 15 checks get silently skipped (glide path needs your age, emergency-fund check needs your target, employer-stock check needs your ticker, retirement-risk checks need your target year, upcoming-expense check needs your list). You'll get concentration, leverage, tax-loss, performance, and asset-location findings either way. Recommended minimum: `birth_year`, `target_retirement_year`, and `liquidity.emergency_fund_target` — re-enables most of the lifecycle checks.

### Step 9: First Run

Start with a dry run to test the brokerage connections without building the Excel:

```
python src/daily_pipeline.py --dry-run
```

✅ **Verify:** look for `Pipeline Complete` or `All steps completed successfully` near the end of the output.

Then a full run:

```
python src/daily_pipeline.py
```

✅ **Verify:** open the project folder; you should see `2026_Portfolio_Analysis.xlsx`. Open it — the Dashboard, account tabs, and Recommendations tab should all be populated.

### Step 10: Set It and Forget It

Schedule the tool to run automatically every weekday afternoon.

**Windows (Task Scheduler):**

The included `schedule_task.xml` is a template — you need to edit it before importing:

1. Open `schedule_task.xml` in your code editor.
2. Replace `<PROJECT_PATH>` (in `<Command>` and `<WorkingDirectory>`) with the absolute path to this project — e.g. `C:\Users\you\agent-plutus`.
3. Replace `YourUsername` (in `<Author>` and `<UserId>`) with your actual Windows username. To find it, run `whoami` in your terminal — use just the part after the backslash.
4. Save the file.

Then import the task:

```
schtasks /create /tn "AgentPlutus" /xml schedule_task.xml
```

✅ **Verify:** open Task Scheduler (search "Task Scheduler" in the Start menu), find "AgentPlutus" in the task list. Right-click → "Run" to test it now without waiting for 4pm.

**Mac/Linux (cron):**

```
crontab -e
```

Add this line (replace the path):
```
0 16 * * 1-5 cd /path/to/agent-plutus && python3 src/daily_pipeline.py
```

✅ **Verify:** run `crontab -l` to list your jobs and confirm yours appears.

> **Scheduling note:** the pipeline only runs while your computer is on or sleeping. Sleep mode is best — the scheduler wakes the machine, runs, and lets it sleep again. If the machine is fully off, the task fires on next boot (`StartWhenAvailable`). Missed trading days are caught up automatically from the last cached extraction. On Windows, enable "Wake timers" in Power Options for reliability.

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
python -m advisor                              # View today's advisor brief
python -m advisor --date YYYY-MM-DD            # View a past day's brief
python -m advisor --findings                   # Print structured findings as JSON
```

## Frequently Asked Questions

**Can this tool access or move my money?**
No. All connections are strictly read-only. It can see your balances and holdings, but has zero ability to trade, transfer, or modify anything.

**Do I need to know Python?**
Only for the initial setup (copy-pasting a few commands). After that, the tool runs on its own every weekday.

**Do I need all the brokerage accounts listed?**
No. The tool works with whatever you connect — Fidelity only, just Robinhood, no angel investments at all. Missing-account pages are simply skipped. Add more anytime by re-running setup and dropping the corresponding `data/*.json`.

**What does "beating the market" mean?**
If the S&P 500 is up 10% this year and your portfolio is up 12%, you're beating the market by 2 percentage points. That 2% is your "alpha."

**How current is the data?**
Each run pulls live data from your accounts. If you run it at 4pm, you'll see that day's prices.

**What if a brokerage connection breaks?**
The tool will still run — it falls back to the most recent successful extraction for that source and warns you in the log. Reconnect when you have a chance.

**What if my computer was off for a few days?**
The pipeline catches up automatically. When it runs again, it detects any missed trading days and rebuilds the workbook from the most recent cached data. On a trading day it also pulls fresh data.

**Can I run this on a Mac?**
Yes. Everything works on Mac. The only difference is how you schedule the automatic run (cron instead of Task Scheduler).

## File Structure

```
agent-plutus/
├── src/             # Core pipeline + workbook builder + tab rebuilders
├── advisor/         # CFP-style portfolio advisor
├── extractors/      # Brokerage data extraction (SnapTrade, Plaid, Fidelity)
├── tools/           # Angel valuation, redaction utility
├── data/            # Account data templates (*.example.json)
├── tests/           # Test suite
├── manual_data.example.json
├── user_profile.example.json
├── requirements.txt
├── run_pipeline.bat / run_pipeline.sh
├── schedule_task.xml
└── README.md
```

Browse the GitHub source tree for per-file detail.

## Architecture

```
SnapTrade API ─────┐
Plaid API ─────────┤
Yahoo Finance ─────┤──> portfolio_model.py ──> build_workbook.py ──> .xlsx
data/*.json ───────┤       (pure math)          (formatting)            ↑
manual_data.json ──┘                                                    │
                                                                        │
                                  observations.py ──> narrator.py ──> writer.py
                                  (15 CFP checks)     (Claude brief)   (Recommendations tab)
                                       ↑                  ↑
                              user_profile.json    .anthropic_key
```

- **Extraction** (`extractors/`): SnapTrade for Robinhood + Fidelity; Plaid for Merrill 401k + cash; Playwright fallback for Fidelity.
- **Computation** (`portfolio_model.py`): pure Python — merges JSON templates with live API data, computes TWR/MWRR/cost-basis returns, alpha. No Excel dependency.
- **Output** (`build_workbook.py` + `rebuild_*.py`): declarative Excel builder plus per-tab rebuilders (Dashboard, account tabs, Cash).
- **Advisor** (`advisor/`): post-build, non-fatal. `observations.py` runs 15 health checks; `narrator.py` sends classified findings to Claude with a CFP-aligned system prompt; `writer.py` renders the brief into the Recommendations tab. Falls back to deterministic local Markdown when no API key.
- **Validation** (`validate_workbook.py`): 7 structural checks (label matching, formula errors, balance continuity, accounting identity, etc.). Non-zero exit gates a scheduled run.

`daily_pipeline.py` orchestrates: extract → benchmarks → snapshot → build → validate → advise. Runs Mon–Fri at 4:00 PM PT via Windows Task Scheduler; skips weekends and US market holidays. See `tests/README.md` for the testing philosophy and `skills.md` for a per-script capability map.

## License

MIT
