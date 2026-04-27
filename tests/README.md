# Testing Approach — Project Finance

This suite exists because on 2026-04-24 the daily pipeline was discovered to have 8 distinct bugs that had accumulated silently over ~6 days, including a $130K misstatement of the Dashboard total. The workbook still built; it was just wrong.

The goal is to make silent failure impossible — or at least, to catch each class of it before it reaches the Dashboard.

## Layers

| Layer | Where | What it catches | What it costs |
|---|---|---|---|
| **Regression** | `test_regressions.py` | A specific bug coming back. One test per bug fixed. | Cheap — usually <10 lines per test. |
| **Unit** (embedded in regression file) | `test_regressions.py` | Logic bugs in pure functions: gains math, merge logic, snapshot shape handling. | Cheap — fixtures are small dicts. |
| **Integration (golden)** | `test_integration_golden.py` | Output drift: Dashboard values wrong, tabs missing, cross-section aggregation broken. End-to-end without network. | Moderate — synthetic fixture takes effort to maintain as the data model evolves. |
| **Validator** (integration, against real workbook) | `test_regressions.py::test_current_workbook_passes_validator_with_zero_errors` | Builder/registry drift after a real pipeline run. | Free — reuses existing `validate_workbook.py`. |
| **Contract** (not yet built) | TBD | External API shape changes: SnapTrade renames a field, redacts a number, changes a list to a dict. | Requires auth token + some form of record/replay. |

## What's deliberately *not* here

- **No CI.** This is a personal daily workflow. `python -m pytest` on demand is the gate.
- **No coverage gate.** Coverage % is a metric, not a goal. The 16 tests cover what we know broke.
- **No mocked SnapTrade/Plaid network tests.** Integration uses a synthetic fixture; contract tests would need auth and aren't worth the maintenance for a single-user workflow.
- **No performance/load tests.** Not applicable.
- **No property-based tests.** Maybe worth it for the returns math later; not today.

## Running tests

From `Project Finance/`:

```bash
python -m pytest tests/ -v
```

Expected time: ~8 seconds for the full suite. If it's slower than that, something regressed in startup.

A selective run:

```bash
python -m pytest tests/test_regressions.py -v -k "live_holdings"
```

## Traceability — which test catches which bug

Every bug fixed in the 2026-04-24 session has at least one test. If a fix is reverted, the corresponding test fails.

| # | Bug (2026-04-24) | Root cause | Test(s) |
|---|---|---|---|
| 1 | Workbook saved to `agents\` instead of `Project Finance\` | `PROJECT_DIR = SCRIPT_DIR.parent.resolve()` — wrong in flat layout | `test_project_dir_equals_script_dir`, `test_output_xlsx_and_manual_data_files_exist` |
| 2 | Snapshot non-fatal `unexpected keyword argument 'k401_raw'` | Pipeline passed `k401_raw=...`, signature is `merrill_raw=...` | `test_save_snapshot_accepts_merrill_raw_kwarg`, `test_pipeline_passes_merrill_raw_not_k401_raw` |
| 3 | `Plaid cash extraction failed: ...extractors\plaid_extract.py` | Path was `PROJECT_DIR / "extractors"` but actual file is at `repo/extractors/` | `test_repo_plaid_extract_path_resolves`, `test_repo_plaid_extract_has_extract_plaid_cash` |
| 4 | Fidelity Brokerage showed $74K instead of live $89K | `_merge_live_holdings` keyed on un-redacted account numbers; SnapTrade returns redacted (`*****9908`) | `test_merge_live_holdings_matches_redacted_fidelity_keys`, `test_merge_live_holdings_falls_back_when_no_match` |
| 5 | 401(k) ending = $0 on Dashboard | `gains.total_mv = 0` because `k401.json` has no static holdings; live Plaid holdings were fetched but never folded into gains | `test_401k_gains_total_mv_from_live_merrill_holdings` |
| 6 | Fidelity values inflated by $14K (cash double-count) | Live SnapTrade holdings include money-market positions (FCASH/SPAXX/FDRXX); stale `cash_position` from JSON was being added on top | `test_live_holdings_source_zeroes_stale_cash_position`, `test_statement_holdings_preserve_cash_position` |
| 7 | Snapshot failed: `list indices must be integers or slices, not dict` | Raw SnapTrade rh_raw has `holdings` as a list of dicts; `_extract_provider_accounts` assumed ticker-keyed / date-keyed dict | `test_snapshot_handles_list_format_holdings`, `test_snapshot_still_handles_ticker_keyed_holdings` |
| 8 | 28 validation errors (label mismatches) | `registry.py` + `registry_data.json` expected old rebuild-script layout; new builder produces a different one and doesn't call `update_registry()` | `test_current_workbook_passes_validator_with_zero_errors` |

Additionally, the golden integration tests catch any future regression in the end-to-end model → builder pipeline:

| Test | Catches |
|---|---|
| `test_golden_workbook_dashboard_values` | Wrong Dashboard values (MV aggregation, subtotals, total portfolio). Would have caught bugs 4, 5, 6 at the output layer. |
| `test_golden_workbook_has_expected_tabs` | Missing tabs, accidental tab renames, extra tabs. |

## Adding a new test

When a new bug is fixed:

1. **Before fixing:** try to write a failing test that reproduces the bug. Run it, see it fail. (TDD-style.)
2. **After fixing:** the test should now pass. Confirm it would fail on the pre-fix code (read the assertion and the old code; if you can't tell, temporarily revert and re-run).
3. **Add a row to the traceability table above** with the bug description, root cause, and test name.
4. **Commit test + fix together** — never ship the fix without the test.

Naming convention: `test_<short_description_of_the_condition_that_must_hold>`. E.g. `test_live_holdings_source_zeroes_stale_cash_position` says *what must be true*, not *what bug it's about*. That's intentional — the test should read as a spec, not a war story.

For new feature work:
- If the change is purely in a pure function (returns math, merge logic), add a unit test alongside related ones in `test_regressions.py` (rename the file later if it becomes misleading).
- If the change affects the Dashboard output, update the golden fixture in `test_integration_golden.py` and the expected values table alongside.

## Fixture philosophy

The golden test uses **synthetic** fixtures (inline Python dicts), not real extracts. Reasons:

1. **No sensitive data committed.** Real holdings, cost bases, and account numbers stay out of the repo.
2. **Small and readable.** The whole golden fixture fits on one screen; you can verify expected values by hand.
3. **Deterministic.** No dates, no prices that change. A test that passed yesterday should pass tomorrow.
4. **Exercises the same code paths.** `build_model` and `build` don't care whether data is real or synthetic.

The trade-off: synthetic fixtures can't catch bugs that depend on real data shape (e.g. an unusual holding type we don't have in the fixture). That's why we also keep `test_current_workbook_passes_validator_with_zero_errors` — it runs against whatever was most recently built, which is real data.

## When tests fail

| Symptom | Likely cause |
|---|---|
| `test_current_workbook_passes_validator_with_zero_errors` fails | Builder layout drifted without updating `registry.py` / `registry_data.json`. See `memory/project_validator_drift.md`. |
| `test_golden_workbook_dashboard_values` fails on a value diff | A real aggregation bug, or the expected values need updating to match an intentional model change. Read the diff before mass-updating expected values. |
| `test_golden_workbook_has_expected_tabs` fails | A tab was removed, renamed, or added. If intentional, update the expected set. |
| Multiple regression tests fail together | Likely a shared-dependency change (e.g. `build_model` signature, `portfolio_model` import). Read the first error carefully. |
| Tests pass but the real pipeline is wrong | Missing test coverage. Add one before fixing — use the failure as the spec. |

## File map

```
tests/
├── __init__.py                     # package marker (empty)
├── conftest.py                     # puts the flat-layout project root on sys.path
├── test_regressions.py             # 14 tests, one+ per bug (see traceability table)
├── test_integration_golden.py      # 2 golden tests: Dashboard values + tab set
└── README.md                       # this file
```

## Advisor test suite

The advisor (`advisor/`) is tested under `tests/advisor/`. It follows the same layered pattern: pure functions get unit tests, anything LLM-backed is stubbed, the daily path gets one integration test.

### Layout

```
tests/advisor/
├── __init__.py
├── conftest.py                      # adds project root to sys.path
├── test_profile.py                  # Profile loading + defaults
├── test_asset_classifier.py         # ticker → asset class lookup
├── test_observations.py             # 15 observations + Finding dataclass + runner
├── test_state.py                    # findings persistence + dedup diff
├── test_fallback.py                 # findings → markdown when LLM unavailable
├── test_narrator.py                 # LLM call with stubbed AnthropicClient
├── test_writer.py                   # Recommendations tab writer
├── test_run_daily.py                # full daily orchestrator integration
└── test_cli.py                      # python -m advisor
```

### Traceability — observation → CFP module → test

| Obs | Category | CFP module | Test class |
|---|---|---|---|
| 1 | sector_concentration | Module 2 | `TestSectorConcentration` |
| 2 | single_position_concentration | Module 2 | `TestSinglePositionConcentration` |
| 3 | cash_vs_target | Module 6 | `TestCashVsTarget` |
| 4 | margin_leverage | Module 2 | `TestMarginLeverage` |
| 5 | glide_path_drift | Module 5 | `TestGlidePathDrift` |
| 6 | illiquid_ratio | Module 2 | `TestIlliquidRatio` |
| 7 | upcoming_expense_coverage | Module 9 | `TestUpcomingExpenseCoverage` |
| 8 | ytd_vs_benchmark | Module 2 | `TestYTDvsBenchmark` |
| 9 | ytd_investment_gain | Module 9 | `TestYTDInvestmentGain` |
| 10 | international_equity_share | Module 8 | `TestInternationalEquityShare` |
| 11 | asset_location_inefficiency | Module 7 | `TestAssetLocationInefficiency` |
| 12 | tax_loss_harvest_candidate | Module 7 | `TestTaxLossHarvestCandidate` |
| 13 | employer_stock_concentration | Modules 2 & 8 | `TestEmployerStockConcentration` |
| 14 | pre_retirement_equity_risk | Module 6 | `TestPreRetirementEquityRisk` |
| 15 | inflation_hedge_exposure | Module 2 | `TestInflationHedgeExposure` |

### Pipeline regression

`tests/test_regressions.py::test_advisor_failure_is_non_fatal` guarantees that any future regression where the advisor crashes the pipeline produces a failing test.

### What's deliberately NOT tested

- LLM output quality. Not automatable; the user judges by reading the brief.
- Real network calls to Claude. Stubbed in the default suite. A `@pytest.mark.contract` test exists for weekly verification — see spec §10.4.

### Running

```bash
python -m pytest tests/ -v          # everything
python -m pytest tests/advisor/ -v  # just the advisor
```

Expected total wall-clock: <15s with the original 16 tests plus the advisor's ~50.
