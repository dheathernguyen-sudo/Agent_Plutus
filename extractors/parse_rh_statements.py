#!/usr/bin/env python3
"""Parse Robinhood monthly account statements from PDF to extract monthly returns."""

import pdfplumber
import os
import re
import json
import sys
from pathlib import Path

DOWNLOADS = Path.home() / "Downloads"


def parse_dollar(s):
    """Parse a dollar string like '($14,787.43)' or '$37,790.89' to float."""
    s = s.strip()
    negative = "(" in s or s.startswith("-")
    s = re.sub(r'[$()\s,]', '', s)
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def extract_statement_data(pdf_path):
    """Extract key financial data from a Robinhood monthly statement PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        page1_text = pdf.pages[0].extract_text() or ''

        if 'robinhood' not in page1_text.lower():
            return None

        # Date range
        dm = re.search(r'(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})', page1_text)
        if not dm:
            return None

        data = {
            'start_date': dm.group(1),
            'end_date': dm.group(2),
            'file': os.path.basename(pdf_path),
        }

        lines = page1_text.split('\n')

        for line in lines:
            # Net Account Balance — has opening and closing
            if 'Net Account Balance' in line:
                # Match dollar amounts including negatives in parens
                nums = re.findall(r'[\(]?\$[\d,]+\.\d+\)?', line)
                if not nums:
                    nums = re.findall(r'\([\d,]+\.\d+\)', line)
                if len(nums) >= 2:
                    data['net_balance_opening'] = parse_dollar(nums[0])
                    data['net_balance_closing'] = parse_dollar(nums[1])

            # Total Securities
            if 'Total Securities' in line and '*' in line:
                nums = re.findall(r'\$[\d,]+\.\d+', line)
                if len(nums) >= 2:
                    data['securities_opening'] = parse_dollar(nums[0])
                    data['securities_closing'] = parse_dollar(nums[1])

            # Portfolio Value
            if 'Portfolio Value' in line:
                nums = re.findall(r'\$[\d,]+\.\d+', line)
                if len(nums) >= 2:
                    data['portfolio_opening'] = parse_dollar(nums[0])
                    data['portfolio_closing'] = parse_dollar(nums[1])

            # Dividends
            if line.strip().startswith('Dividends') and 'Capital' not in line:
                nums = re.findall(r'\$[\d,]+\.\d+', line)
                if len(nums) >= 1:
                    data['dividends_period'] = parse_dollar(nums[0])
                if len(nums) >= 2:
                    data['dividends_ytd'] = parse_dollar(nums[1])

            # Interest Earned
            if 'Interest Earned' in line:
                nums = re.findall(r'\$[\d,]+\.\d+', line)
                if len(nums) >= 1:
                    data['interest_period'] = parse_dollar(nums[0])

        # Also get all-pages text to find cash activity (deposits/withdrawals)
        all_text = ''
        for page in pdf.pages:
            all_text += (page.extract_text() or '') + '\n'

        # Look for transfers/deposits in activity section
        deposits = 0.0
        withdrawals = 0.0
        for line in all_text.split('\n'):
            if re.search(r'ACH\s+(Deposit|Transfer)', line, re.IGNORECASE):
                nums = re.findall(r'\$[\d,]+\.\d+', line)
                if nums:
                    amt = parse_dollar(nums[-1])
                    if amt and amt > 0:
                        deposits += amt
            if re.search(r'ACH\s+Withdrawal', line, re.IGNORECASE):
                nums = re.findall(r'\$[\d,]+\.\d+', line)
                if nums:
                    amt = parse_dollar(nums[-1])
                    if amt and amt > 0:
                        withdrawals += amt

        data['deposits'] = deposits
        data['withdrawals'] = withdrawals

        return data


def calculate_monthly_returns(statements):
    """Calculate monthly TWR-approximate returns from statement data.

    Uses: Return = (Ending - Beginning - Net Deposits) / Beginning
    where Beginning/Ending are portfolio values (securities + cash).
    """
    results = []
    for key in sorted(statements.keys()):
        s = statements[key]

        # Use portfolio value (securities only) or net account balance
        opening = s.get('portfolio_opening')
        closing = s.get('portfolio_closing')

        if opening is None or closing is None:
            # Fall back to securities values
            opening = s.get('securities_opening')
            closing = s.get('securities_closing')

        if opening is None or closing is None or opening == 0:
            results.append({
                'month': key,
                'return': None,
                'note': 'Missing data',
            })
            continue

        net_deposits = s.get('deposits', 0) - s.get('withdrawals', 0)
        dividends = s.get('dividends_period', 0) or 0

        # Simple return: (End - Start - Net New Money) / Start
        gain = closing - opening - net_deposits
        monthly_return = gain / abs(opening)

        results.append({
            'month': key,
            'start_date': s['start_date'],
            'end_date': s['end_date'],
            'opening': opening,
            'closing': closing,
            'deposits': s.get('deposits', 0),
            'withdrawals': s.get('withdrawals', 0),
            'net_deposits': net_deposits,
            'dividends': dividends,
            'gain_loss': round(gain, 2),
            'return_pct': round(monthly_return * 100, 2),
        })

    return results


def main():
    # Find all Robinhood statements
    statements = {}
    for f in os.listdir(DOWNLOADS):
        if not f.endswith('.pdf'):
            continue
        path = DOWNLOADS / f
        try:
            data = extract_statement_data(str(path))
            if data:
                # Key by MM/YYYY of end date
                end = data['end_date']
                key = end[0:2] + '/' + end[6:10]
                # Avoid duplicates (keep first found, skip -1.pdf copies)
                if key not in statements or '-1.pdf' in f:
                    if key not in statements:
                        statements[key] = data
        except Exception as e:
            print(f"Error parsing {f}: {e}", file=sys.stderr)

    if not statements:
        print("No Robinhood statements found.")
        sys.exit(1)

    # Calculate returns
    returns = calculate_monthly_returns(statements)

    # Print summary
    print(f"\n{'='*80}")
    print(f"  ROBINHOOD MONTHLY RETURNS")
    print(f"{'='*80}")
    print(f"\n  {'Month':<10} {'Opening':>12} {'Closing':>12} {'Deposits':>10} {'Withdrawals':>12} {'Gain/Loss':>10} {'Return':>8}")
    print(f"  {'-'*74}")

    cumulative = 1.0
    for r in returns:
        if r.get('return_pct') is not None:
            cumulative *= (1 + r['return_pct'] / 100)
            print(f"  {r['month']:<10} ${r['opening']:>11,.2f} ${r['closing']:>11,.2f} "
                  f"${r['deposits']:>9,.2f} ${r['withdrawals']:>11,.2f} "
                  f"${r['gain_loss']:>9,.2f} {r['return_pct']:>7.2f}%")
        else:
            print(f"  {r['month']:<10} {'N/A':>12} {'N/A':>12} {'':>10} {'':>12} {'':>10} {'N/A':>8}")

    # Separate 2025 and 2026
    ytd_2025 = 1.0
    ytd_2026 = 1.0
    for r in returns:
        if r.get('return_pct') is None:
            continue
        year = r['end_date'][6:10]
        if year == '2025':
            ytd_2025 *= (1 + r['return_pct'] / 100)
        elif year == '2026':
            ytd_2026 *= (1 + r['return_pct'] / 100)

    print(f"\n  {'='*74}")
    print(f"  2025 Total Return (Jan-Dec): {(ytd_2025 - 1) * 100:.2f}%")
    print(f"  2026 YTD Return (Jan-Mar):   {(ytd_2026 - 1) * 100:.2f}%")
    print(f"  Cumulative Return:           {(cumulative - 1) * 100:.2f}%")
    print()

    # Output JSON for pipeline use
    output = {
        'monthly_returns': returns,
        'ytd_2025': round((ytd_2025 - 1) * 100, 2),
        'ytd_2026': round((ytd_2026 - 1) * 100, 2),
        'cumulative': round((cumulative - 1) * 100, 2),
    }
    out_path = Path(__file__).parent / 'rh_monthly_returns.json'
    out_path.write_text(json.dumps(output, indent=2))
    print(f"  Data saved to: {out_path}")


if __name__ == '__main__':
    main()
