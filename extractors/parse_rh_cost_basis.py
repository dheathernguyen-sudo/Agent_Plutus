#!/usr/bin/env python3
"""Parse all Robinhood statements to build transaction history and calculate cost basis."""

import pdfplumber
import os
import re
import json
from pathlib import Path
from collections import defaultdict

DOWNLOADS = Path.home() / "Downloads"


def parse_dollar(s):
    s = s.strip()
    negative = "(" in s or s.startswith("-")
    s = re.sub(r'[$() ,]', '', s)
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def extract_transactions(pdf_path):
    """Extract buy/sell transactions from a Robinhood statement."""
    transactions = []
    statement_period = None

    with pdfplumber.open(pdf_path) as pdf:
        page1 = pdf.pages[0].extract_text() or ''
        if 'robinhood' not in page1.lower():
            return None, None

        dm = re.search(r'(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})', page1)
        if dm:
            statement_period = (dm.group(1), dm.group(2))

        all_text = ''
        for page in pdf.pages:
            all_text += (page.extract_text() or '') + '\n'

        lines = all_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            # Match buy/sell lines: "TICKER Margin Buy/Sell MM/DD/YYYY QTY PRICE AMOUNT"
            # The ticker name is on the line before, then the detail line follows
            m = re.match(
                r'\s*(\w+)\s+Margin\s+(Buy|Sell)\s+(\d{2}/\d{2}/\d{4})\s+'
                r'(\d+)\s+\$([\d,.]+)\s+\$([\d,.]+)',
                line
            )
            if m:
                ticker = m.group(1)
                action = m.group(2)
                date = m.group(3)
                qty = int(m.group(4))
                price = float(m.group(5).replace(',', ''))
                amount = float(m.group(6).replace(',', ''))

                transactions.append({
                    'ticker': ticker,
                    'action': action,
                    'date': date,
                    'qty': qty,
                    'price': price,
                    'amount': amount,
                })
            i += 1

    return transactions, statement_period


def extract_holdings(pdf_path):
    """Extract end-of-month holdings from a Robinhood statement."""
    holdings = {}

    with pdfplumber.open(pdf_path) as pdf:
        page1 = pdf.pages[0].extract_text() or ''
        if 'robinhood' not in page1.lower():
            return None, None

        dm = re.search(r'(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})', page1)
        period = dm.group(2) if dm else None

        for page in pdf.pages:
            text = page.extract_text() or ''
            if 'Portfolio Summary' not in text:
                continue

            lines = text.split('\n')
            for line in lines:
                m = re.match(
                    r'\s*(\w+)\s+Margin\s+(\d+)\s+\$([\d,.]+)\s+\$([\d,.]+)',
                    line
                )
                if m:
                    ticker = m.group(1)
                    qty = int(m.group(2))
                    price = float(m.group(3).replace(',', ''))
                    mv = float(m.group(4).replace(',', ''))
                    holdings[ticker] = {
                        'qty': qty,
                        'price': price,
                        'market_value': mv,
                    }

    return holdings, period


def calculate_cost_basis(all_transactions):
    """Calculate cost basis per ticker using average cost method."""
    # Track: total shares, total cost for each ticker
    positions = defaultdict(lambda: {'shares': 0, 'total_cost': 0.0, 'realized_gl': 0.0,
                                      'buys': [], 'sells': []})

    for txn in sorted(all_transactions, key=lambda t: t['date']):
        ticker = txn['ticker']
        pos = positions[ticker]

        if txn['action'] == 'Buy':
            pos['shares'] += txn['qty']
            pos['total_cost'] += txn['amount']
            pos['buys'].append(txn)
        elif txn['action'] == 'Sell':
            if pos['shares'] > 0:
                avg_cost = pos['total_cost'] / pos['shares']
                cost_of_sold = avg_cost * txn['qty']
                realized = txn['amount'] - cost_of_sold
                pos['realized_gl'] += realized
                pos['total_cost'] -= cost_of_sold
                pos['shares'] -= txn['qty']
            pos['sells'].append(txn)

    return positions


def main():
    # Step 1: Find all Robinhood statements
    rh_files = []
    for f in os.listdir(DOWNLOADS):
        if not f.endswith('.pdf'):
            continue
        path = DOWNLOADS / f
        try:
            with pdfplumber.open(str(path)) as pdf:
                text = (pdf.pages[0].extract_text() or '')[:300]
                if 'robinhood' in text.lower():
                    dm = re.search(r'(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})', text)
                    if dm:
                        rh_files.append((dm.group(1), dm.group(2), str(path), f))
        except:
            pass

    rh_files.sort()
    print(f"Found {len(rh_files)} Robinhood statements\n")

    # Step 2: Extract all transactions
    all_transactions = []
    seen_txns = set()
    for start, end, path, fname in rh_files:
        txns, period = extract_transactions(path)
        if txns:
            for t in txns:
                # Deduplicate
                key = (t['ticker'], t['action'], t['date'], t['qty'], t['price'])
                if key not in seen_txns:
                    seen_txns.add(key)
                    all_transactions.append(t)
                    print(f"  {t['date']} {t['action']:4s} {t['ticker']:6s} x{t['qty']} @ ${t['price']:.2f} = ${t['amount']:.2f}")

    print(f"\nTotal transactions: {len(all_transactions)}")

    # Step 3: Get current holdings from latest statement
    latest_path = rh_files[-1][2]
    current_holdings, as_of = extract_holdings(latest_path)
    print(f"\nCurrent holdings as of {as_of}:")
    for ticker, h in sorted(current_holdings.items()):
        print(f"  {ticker:6s}: {h['qty']} shares @ ${h['price']:.2f} = ${h['market_value']:.2f}")

    # Step 4: Calculate cost basis
    positions = calculate_cost_basis(all_transactions)

    # Step 5: Report
    print(f"\n{'='*90}")
    print(f"  ROBINHOOD HOLDINGS: GAIN/LOSS & RETURN %")
    print(f"{'='*90}")
    print(f"\n  {'Ticker':<7} {'Qty':>5} {'Avg Cost':>10} {'Cost Basis':>12} {'Price':>10} "
          f"{'Mkt Value':>12} {'Gain/Loss':>12} {'Return %':>9}")
    print(f"  {'-'*82}")

    total_cost = 0
    total_mv = 0
    total_gl = 0

    results = []
    for ticker in sorted(current_holdings.keys()):
        h = current_holdings[ticker]
        pos = positions.get(ticker, {})
        shares = pos.get('shares', h['qty'])
        cost = pos.get('total_cost', 0)
        avg_cost = cost / shares if shares > 0 else 0
        mv = h['market_value']
        gl = mv - cost
        ret_pct = (gl / cost * 100) if cost > 0 else 0

        total_cost += cost
        total_mv += mv
        total_gl += gl

        print(f"  {ticker:<7} {h['qty']:>5} ${avg_cost:>9.2f} ${cost:>11.2f} ${h['price']:>9.2f} "
              f"${mv:>11.2f} ${gl:>11.2f} {ret_pct:>8.2f}%")

        results.append({
            'ticker': ticker,
            'qty': h['qty'],
            'avg_cost': round(avg_cost, 2),
            'cost_basis': round(cost, 2),
            'current_price': h['price'],
            'market_value': round(mv, 2),
            'gain_loss': round(gl, 2),
            'return_pct': round(ret_pct, 2),
        })

    print(f"  {'-'*82}")
    total_ret = (total_gl / total_cost * 100) if total_cost > 0 else 0
    print(f"  {'TOTAL':<7} {'':>5} {'':>10} ${total_cost:>11.2f} {'':>10} "
          f"${total_mv:>11.2f} ${total_gl:>11.2f} {total_ret:>8.2f}%")

    # Sold positions
    print(f"\n  SOLD POSITIONS (Realized Gain/Loss)")
    print(f"  {'-'*50}")
    total_realized = 0
    sold_results = []
    for ticker, pos in sorted(positions.items()):
        if ticker not in current_holdings and pos['sells']:
            rgl = pos['realized_gl']
            total_realized += rgl
            sell_total = sum(s['amount'] for s in pos['sells'])
            buy_total = sum(b['amount'] for b in pos['buys'])
            print(f"  {ticker:<7} Bought: ${buy_total:>10.2f}  Sold: ${sell_total:>10.2f}  "
                  f"Realized G/L: ${rgl:>10.2f}")
            sold_results.append({
                'ticker': ticker,
                'total_bought': round(buy_total, 2),
                'total_sold': round(sell_total, 2),
                'realized_gl': round(rgl, 2),
            })
        elif ticker in current_holdings and pos['realized_gl'] != 0:
            # Partially sold position
            rgl = pos['realized_gl']
            total_realized += rgl
            print(f"  {ticker:<7} (partial sells) Realized G/L: ${rgl:>10.2f}")

    print(f"  {'-'*50}")
    print(f"  Total Realized G/L: ${total_realized:>10.2f}")
    print(f"  Total Unrealized G/L: ${total_gl:>10.2f}")
    print(f"  Combined G/L: ${total_realized + total_gl:>10.2f}")

    # Save output
    output = {
        'as_of': as_of,
        'current_holdings': results,
        'sold_positions': sold_results,
        'total_cost_basis': round(total_cost, 2),
        'total_market_value': round(total_mv, 2),
        'total_unrealized_gl': round(total_gl, 2),
        'total_realized_gl': round(total_realized, 2),
    }
    out_path = Path(__file__).parent / 'rh_cost_basis.json'
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n  Data saved to: {out_path}")


if __name__ == '__main__':
    main()
