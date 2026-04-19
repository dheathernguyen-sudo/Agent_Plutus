#!/usr/bin/env python3
"""
robinhood_history.py — Extract Robinhood monthly portfolio history
==================================================================
Uses robin_stocks to pull:
  - Historical portfolio values (daily/monthly snapshots)
  - Dividends
  - Margin interest
  - Bank transfers (deposits/withdrawals)

First run requires interactive login (email + password + SMS MFA code).
Session is cached in ~/.tokens/robinhood.pickle for subsequent runs.

Usage:
    python robinhood_history.py --login          # Interactive login + save credentials
    python robinhood_history.py                  # Pull history (uses cached session)
    python robinhood_history.py --year 2026      # Specific year
"""

import argparse
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

import robin_stocks.robinhood as rh

CONFIG_DIR = Path.home() / ".portfolio_extract"
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_DIR = CONFIG_DIR / "tokens"
OUTPUT_DIR = Path(__file__).parent.resolve()


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def _get_password(service, username):
    """Retrieve password from OS keyring, falling back to config.json."""
    try:
        import keyring
        pw = keyring.get_password(service, username)
        if pw:
            return pw
    except ImportError:
        pass
    return None


def _set_password(service, username, password):
    """Store password in OS keyring if available."""
    try:
        import keyring
        keyring.set_password(service, username, password)
        return True
    except ImportError:
        return False


def login(config, interactive=False):
    """Login to Robinhood. Uses OS keyring for password, falls back to config."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    pickle_path = str(TOKEN_DIR / "robinhood.pickle")

    rh_config = config.get("robinhood_login", {})
    email = rh_config.get("email", "")
    password = _get_password("agent-plutus-robinhood", email) if email else None
    # Fall back to config.json for backward compatibility
    if not password:
        password = rh_config.get("password", "")

    if interactive or not email or not password:
        print("\n  Robinhood Login")
        print("  " + "=" * 40)
        email = input("  Email: ").strip()
        password = input("  Password: ").strip()

        # Save email to config, password to OS keyring
        config.setdefault("robinhood_login", {})["email"] = email
        if _set_password("agent-plutus-robinhood", email, password):
            config["robinhood_login"].pop("password", None)  # Remove from plaintext
            print("  Password saved to OS keyring. Email saved to config.")
        else:
            config["robinhood_login"]["password"] = password
            print("  Password saved to config (install 'keyring' for secure storage).")
        save_config(config)

    print(f"\n  Logging in as {email}...")
    print("  (You may receive an SMS code)")

    try:
        login_result = rh.login(
            email, password,
            store_session=True,
            pickle_name=pickle_path,
        )
        if login_result:
            print("  Login successful!")
            return True
        else:
            print("  Login failed.")
            return False
    except Exception as e:
        print(f"  Login error: {e}")
        return False


def get_monthly_portfolio_values(year):
    """Get month-end portfolio values using daily historicals."""
    print(f"\n  Fetching portfolio historicals for {year}...")

    # Get daily portfolio values for the whole year
    # span options: 'day', 'week', 'month', '3month', 'year', '5year', 'all'
    # bounds options: 'extended', 'regular', 'trading'
    historicals = rh.get_historical_portfolio(
        interval='day',
        span='year',
    )

    if not historicals:
        print("  No portfolio historicals returned.")
        return {}

    # Parse into month-end values
    monthly = {}
    for entry in historicals:
        try:
            dt = datetime.fromisoformat(entry['begins_at'].replace('Z', '+00:00'))
            if dt.year != year:
                continue
            month_key = dt.strftime("%Y-%m")
            val = float(entry.get('adjusted_close_equity') or entry.get('close_equity') or 0)
            # Keep the last value for each month (month-end)
            monthly[month_key] = {
                'date': dt.date().isoformat(),
                'value': round(val, 2),
            }
        except (ValueError, KeyError) as e:
            continue

    print(f"  Got {len(monthly)} months of data")
    for k, v in sorted(monthly.items()):
        print(f"    {k}: ${v['value']:,.2f} ({v['date']})")

    return monthly


def get_dividends(year):
    """Get dividend payments for the year."""
    print(f"\n  Fetching dividends for {year}...")
    divs = rh.get_dividends()

    monthly_divs = {}
    for d in (divs or []):
        try:
            paid_date = d.get('paid_at') or d.get('payable_date', '')
            if not paid_date:
                continue
            dt = datetime.fromisoformat(paid_date.replace('Z', '+00:00')) if 'T' in paid_date else datetime.strptime(paid_date[:10], '%Y-%m-%d')
            if dt.year != year:
                continue
            month_key = dt.strftime("%Y-%m")
            amount = float(d.get('amount', 0))
            monthly_divs[month_key] = monthly_divs.get(month_key, 0) + amount
        except (ValueError, KeyError):
            continue

    total = sum(monthly_divs.values())
    print(f"  Total dividends: ${total:.2f}")
    for k, v in sorted(monthly_divs.items()):
        print(f"    {k}: ${v:.2f}")

    return monthly_divs


def get_transfers(year):
    """Get bank transfers (deposits/withdrawals) for the year."""
    print(f"\n  Fetching bank transfers for {year}...")
    transfers = rh.get_bank_transfers()

    monthly_deposits = {}
    monthly_withdrawals = {}
    for t in (transfers or []):
        try:
            created = t.get('created_at', '')
            if not created:
                continue
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            if dt.year != year:
                continue
            if t.get('state') not in ('completed', 'pending'):
                continue
            month_key = dt.strftime("%Y-%m")
            amount = float(t.get('amount', 0))
            direction = t.get('direction', '')
            if direction == 'deposit':
                monthly_deposits[month_key] = monthly_deposits.get(month_key, 0) + amount
            elif direction == 'withdraw':
                monthly_withdrawals[month_key] = monthly_withdrawals.get(month_key, 0) + amount
        except (ValueError, KeyError):
            continue

    print(f"  Total deposits: ${sum(monthly_deposits.values()):.2f}")
    print(f"  Total withdrawals: ${sum(monthly_withdrawals.values()):.2f}")

    return monthly_deposits, monthly_withdrawals


def get_margin_interest(year):
    """Get margin interest charges for the year."""
    print(f"\n  Fetching margin interest for {year}...")
    try:
        interest = rh.get_margin_interest()
        monthly_interest = {}
        for entry in (interest or []):
            try:
                created = entry.get('created_at', '')
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                if dt.year != year:
                    continue
                month_key = dt.strftime("%Y-%m")
                amount = float(entry.get('amount', 0))
                monthly_interest[month_key] = monthly_interest.get(month_key, 0) + amount
            except (ValueError, KeyError):
                continue
        total = sum(monthly_interest.values())
        print(f"  Total margin interest: ${total:.2f}")
        return monthly_interest
    except Exception as e:
        print(f"  Could not fetch margin interest: {e}")
        return {}


def build_monthly_summary(year):
    """Build complete monthly summary combining all data sources."""
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    portfolio_vals = get_monthly_portfolio_values(year)
    dividends = get_dividends(year)
    deposits, withdrawals = get_transfers(year)
    margin_interest = get_margin_interest(year)

    # Also get the very start of year value
    # Use December of previous year or first available
    prev_year_vals = {}
    try:
        hist_all = rh.get_historical_portfolio(interval='day', span='year')
        for entry in (hist_all or []):
            dt = datetime.fromisoformat(entry['begins_at'].replace('Z', '+00:00'))
            if dt.year == year - 1 and dt.month == 12:
                month_key = dt.strftime("%Y-%m")
                val = float(entry.get('adjusted_close_equity') or entry.get('close_equity') or 0)
                prev_year_vals[month_key] = round(val, 2)
    except Exception:
        pass

    # Build monthly rows
    summary = []
    prev_ending = prev_year_vals.get(f"{year-1}-12", 0)

    for i in range(12):
        month_key = f"{year}-{i+1:02d}"
        ending = portfolio_vals.get(month_key, {}).get('value', 0)
        divs = round(dividends.get(month_key, 0), 2)
        deps = round(deposits.get(month_key, 0), 2)
        withs = round(withdrawals.get(month_key, 0), 2)
        interest = round(margin_interest.get(month_key, 0), 2)

        # Market change = Ending - Beginning - Deposits + Withdrawals - Dividends
        if prev_ending and ending:
            market_change = round(ending - prev_ending - deps + withs - divs, 2)
        else:
            market_change = 0

        row = {
            "month": MONTHS[i],
            "month_key": month_key,
            "beginning": prev_ending,
            "deposits": deps,
            "withdrawals": withs,
            "dividends": divs,
            "market_change": market_change,
            "ending": ending,
            "margin_interest": interest,
        }
        summary.append(row)

        if ending:
            prev_ending = ending

    return summary


def main():
    parser = argparse.ArgumentParser(description="Robinhood Monthly History Extractor")
    parser.add_argument("--login", action="store_true", help="Interactive login")
    parser.add_argument("--year", type=int, default=date.today().year)
    args = parser.parse_args()

    config = load_config()

    if args.login:
        if not login(config, interactive=True):
            sys.exit(1)
    else:
        if not login(config):
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Robinhood Monthly History — {args.year}")
    print(f"{'='*60}")

    summary = build_monthly_summary(args.year)

    # Save output
    output_file = OUTPUT_DIR / f"robinhood_monthly_{args.year}.json"
    output_file.write_text(json.dumps(summary, indent=2))
    print(f"\n  Saved: {output_file}")

    # Print summary table
    print(f"\n  {'Month':5s} {'Beginning':>12s} {'Deposits':>10s} {'Withdrawals':>12s} {'Dividends':>10s} {'Mkt Change':>12s} {'Ending':>12s}")
    print(f"  {'-'*75}")
    for row in summary:
        if row['ending'] or row['beginning']:
            print(f"  {row['month']:5s} ${row['beginning']:>11,.2f} ${row['deposits']:>9,.2f} ${row['withdrawals']:>11,.2f} ${row['dividends']:>9,.2f} ${row['market_change']:>11,.2f} ${row['ending']:>11,.2f}")

    rh.logout()
    print("\n  Logged out.")


if __name__ == "__main__":
    main()
