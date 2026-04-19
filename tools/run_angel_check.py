#!/usr/bin/env python3
"""Interactive angel investment valuation check.

Run this manually (not via the automated pipeline) to search for
new funding rounds and update valuations with your approval.

Usage:
    python tools/run_angel_check.py
"""
import sys
from pathlib import Path

# Add src/ to path for pipeline imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from daily_pipeline import check_angel_valuations, setup_logging, MANUAL_DATA

setup_logging()
print("Starting angel investment valuation check...")
print("You will be prompted to approve/reject each update.\n")

updates = check_angel_valuations(str(MANUAL_DATA), interactive=True)

if updates:
    print(f"\n{len(updates)} update(s) applied to manual_data.json")
    print("Run the pipeline to rebuild the workbook with new valuations.")
else:
    print("\nNo updates applied.")
