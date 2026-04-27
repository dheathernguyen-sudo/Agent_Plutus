# Portfolio Advisory Agent — Design

**Status:** Draft
**Date:** 2026-04-24
**Owner:** D Heather Nguyen
**Related code:** `Project Finance/daily_pipeline.py`, `Project Finance/portfolio_model.py`, `Project Finance/build_workbook.py`

---

## 1. Summary

Add an advisory layer on top of the existing daily portfolio pipeline. After each daily run, a new `Recommendations` tab in `2026_Portfolio_Analysis.xlsx` contains a one-page strategic brief tailored to a persistent user profile (age, risk tolerance, tax situation, hard rules, goals). The same reasoning core is exposed via a Python CLI and, in a later phase, a Claude Code slash command for deeper on-demand conversations. The core pattern is a **two-stage pipeline: deterministic observations + LLM narrator**. Observation logic is pure-function and unit-tested; the LLM only writes narrative over structured findings, which keeps the system testable and the advice reproducible.

This spec covers the v1 (strategic advisory) build. Tactical trade recommendations and market-context enrichment are out of scope for v1 but the architecture is designed to accommodate them in later phases.

---

## 2. Motivation

The existing pipeline produces an accurate, live Excel workbook but no interpretation. Today a human reader has to open the workbook, eyeball concentration, compare against personal goals, and decide whether anything needs attention. This is low-frequency, high-friction, and easily skipped — which is how problems (concentration drift, cash drag, hard-rule violations, underfunded near-term expenses) accumulate silently.

The advisory agent is a deliberate, scoped attempt to close that loop: surface a handful of load-bearing observations every day, and make deeper strategic reasoning available when the user wants to think something through.

It is explicitly **not** a robo-advisor, a trade executor, or a prediction engine. It's a reader and critic of the user's own portfolio against the user's own declared rules.

---

## 3. Goals and Non-Goals

### 3.1 Goals

- **Daily strategic brief.** A ≤250-word markdown brief written to a new `Recommendations` tab after every successful daily pipeline run.
- **Personalized reasoning.** Advice is tailored to a persistent `user_profile.json`: age, retirement timeline, risk tolerance, tax situation, hard rules, goals, concentration limits, liquidity requirements.
- **Deduplication across days.** Findings that haven't changed since the last run move to a compact "standing concerns" footer; only new/changed findings get main-body treatment.
- **Testability.** Observation logic is pure functions with unit tests. LLM narrator is integration-tested with stubbed API calls. No test touches the real Claude API in the default suite.
- **Non-critical path.** Advisor failures never block the workbook build. The workbook is the critical output; the Recommendations tab is value-add.
- **Two surfaces.** Passive daily brief (Excel tab) + on-demand CLI that shares the same core module.

### 3.2 Non-Goals (v1)

- No specific buy/sell trade recommendations ("sell 10 HUT, buy 20 VOO"). That is (D) tactical, deferred to Phase 4.
- No live market/macro data. Observations reason from portfolio data + profile only.
- No tax-lot-level awareness. "Avoid short-term capital gains" is a profile-level rule, not a per-lot calculation.
- No automated execution. Human is always in the loop.
- No portfolio-optimization math (mean-variance, risk parity, Monte Carlo). Advisory, not prescriptive.
- No Claude Code slash command in v1. Deferred to Phase 2 once the daily brief has run stably.

---

## 4. User-Facing Behavior

### 4.1 Daily surface

After the scheduled 4:00 PM PT pipeline finishes, the workbook at `Project Finance/2026_Portfolio_Analysis.xlsx` contains a new `Recommendations` tab. The tab has three sections:

1. **Headline** — a single sentence summarizing current portfolio state and whether anything requires attention. Example:
   > Portfolio $535K as of April 24, 2026. Two attention-level findings (Defense Tech concentration at 48%, illiquid share at 61%). No urgent items.
2. **New or changed observations** — 2-5 bullets with brief narrative written by the LLM, drawing from structured findings.
3. **Standing concerns** — compact list of findings that have been flagged for multiple days without change, so they don't fill the main body each day.

A footer notes when the last run was, what profile was used, and a link to the longer on-demand path.

### 4.2 On-demand CLI

From `Project Finance/`:

```bash
python -m advisor                          # print today's brief to stdout
python -m advisor --date 2026-04-20        # print a previous day's brief
python -m advisor --findings               # print today's raw findings JSON
```

Non-interactive: each invocation prints and exits. For strategic back-and-forth, Phase 2 adds a Claude Code slash command.

---

## 5. Architecture

### 5.1 Core pattern

**Two-stage pipeline for the daily path:**

```
  Portfolio model ──┐
  (existing)        │
                    ├─► observations.run() ──► [Finding, Finding, ...]
  user_profile ─────┤         (pure fns)              │
                    │                                 ▼
  yesterday's       │                        state.diff(today, yesterday)
  findings ─────────┘                                 │
                                                      ▼
                                             narrator.compose()
                                      (single Claude API call, prompt-cached)
                                                      │
                                                      ▼
                                              markdown brief
                                                      │
                                                      ▼
                                      writer.write_recommendations_tab()
```

The on-demand CLI uses the same observation set but invokes a single-call narrator variant without dedup (it just prints the current findings, narrated). When Phase 4 (D) arrives, the narrator becomes a tool-using agent; the observation layer is unchanged.

### 5.2 Why two-stage

- **Testability.** Each observation is a pure function of `(model, profile)`. Unit-testable with small fixtures.
- **Reproducibility.** Facts are deterministic. Only the narrative is LLM-generated.
- **Cost.** One LLM call per daily run; prompt-cached profile and system prompt.
- **Dedup is deterministic.** Today's findings vs yesterday's findings is a set-diff over structured keys — the LLM doesn't decide what's new.
- **Extensibility.** New observation type = new pure function + test. Narrator doesn't change.
- **Extends to Phase 4.** Same pattern: deterministic candidate-trade generator → LLM ranks/explains.

### 5.3 Module layout

```
Project Finance/
├── advisor/
│   ├── __init__.py          # exposes run_daily() and run_cli()
│   ├── observations.py      # one pure function per finding type (15 in v1)
│   ├── asset_classifier.py  # ticker → {equity, bond, cash, REIT, TIPS, commodity, intl} tagging; needed by #5/#11/#15
│   ├── narrator.py          # Claude API call (stubbable); CFP-aligned tone constraints in system prompt
│   ├── profile.py           # load/validate user_profile.json
│   ├── state.py             # persist + diff findings across days
│   ├── writer.py            # write Recommendations tab to workbook
│   ├── fallback.py          # deterministic findings→markdown when LLM unavailable
│   └── __main__.py          # CLI entry (python -m advisor)
├── user_profile.example.json    # committed, safe example
├── user_profile.json            # gitignored, user-populated
├── advisor_state/               # gitignored
│   ├── findings_YYYY-MM-DD.json
│   └── brief_YYYY-MM-DD.md
```

### 5.4 Claude API choices

- **Model:** `claude-opus-4-7` (the same Opus 4.7 the user runs Claude Code on). Quality matters more than cost for one call per day.
- **Prompt caching:** system prompt (observation-type schema, tone instructions) + the user_profile block are cached. The dynamic portion is today's findings + yesterday's findings.
- **Thinking:** off in v1. Add later if narrator reasoning quality demands it.
- **Structured output:** the narrator returns JSON:
  ```json
  {
    "headline": "...",
    "new": [{"category": "...", "narrative": "..."}],
    "standing": [{"category": "...", "summary": "..."}]
  }
  ```
  A deterministic renderer converts JSON → markdown. Keeps the LLM focused on content, not Excel-friendly formatting.
- **Hard rules passthrough:** each string in `profile.hard_rules` is included verbatim in the system prompt under a "NEVER contradict these" header.

### 5.5 Integration with existing pipeline

In `daily_pipeline.py`, after `build(model, OUTPUT_XLSX)` succeeds and `validate_workbook` runs:

```python
try:
    from advisor import run_daily
    run_daily(model, str(OUTPUT_XLSX))
except Exception as e:
    logging.warning(f"Advisor failed (non-fatal): {e}")
    errors.append(f"Advisor: {e}")
```

The workbook is already saved before the advisor runs. Any advisor failure can at worst push the pipeline to exit code 2 (partial success) but cannot corrupt the workbook or block other pipeline steps.

---

## 6. Observation Catalog (v1)

Each observation is a pure function `fn(model, profile) -> List[Finding]` where:

```python
@dataclass
class Finding:
    category: str       # e.g. "sector_concentration"
    key: str            # stable dedup identifier, e.g. "Defense Tech"
    severity: str       # "urgent" | "attention" | "context" | "positive"
    headline: str       # one-line fact the LLM can draw from
    detail: dict        # structured payload for the LLM and the Excel row
```

| # | Category | Trigger | Default severity | Detail payload |
|---|---|---|---|---|
| 1 | `sector_concentration` | Any sector > `profile.max_sector` (default 30%) | `attention`; `urgent` if > 50% | `{sector, pct, top_contributors: [{ticker, mv}]}` |
| 2 | `single_position_concentration` | Any holding > `profile.max_single_position` (default 10%) of liquid | `attention`; `urgent` if > 20% | `{ticker, account, pct, mv, cb}` |
| 3 | `cash_vs_target` | External cash < `emergency_fund_target` → `urgent`. > 2× target → `context` (cash drag) | varies | `{external_cash, target, delta, pct_above_or_below}` |
| 4 | `margin_leverage` | Margin debt / net portfolio > 15% | `attention`; `urgent` if > 25% | `{debt, ratio, interest_cost_est}` |
| 5 | `glide_path_drift` | Actual equity / bond / cash legs deviate from age-and-tolerance glide-path target by > 15 pp on any leg. Bond-leg deficit treated as the most consequential per CFP Module 5 (most retail portfolios are equity-only). | `attention`; `urgent` if any leg deviates by > 30 pp | `{actual: {equity, bond, cash, alt}, target: {...}, leg_deviations: [{leg, actual, target, gap}], rationale}` |
| 6 | `illiquid_ratio` | (401k + Angel) / total > 60% | `attention`; `urgent` if > 75% | `{ratio, components: {k401, angel}}` |
| 7 | `upcoming_expense_coverage` | Any `known_upcoming_expense` underfunded at its `target_year` (naive: does `liquid + cash` projected at 5%/yr reach the amount?) | `attention`; `urgent` if already overdue | `{expense, year, gap, projected_liquid}` |
| 8 | `ytd_vs_benchmark` | Liquid portfolio YTD return differs from S&P 500 YTD by > 500bps (either direction) | `context` | `{portfolio_pct, benchmark_pct, alpha}` |
| 9 | `ytd_investment_gain` | Always emitted from existing Dashboard field | `context` or `positive` | `{total, dividends, unrealized, realized}` |
| 10 | `international_equity_share` | Non-US equity / total equity < 15% with > 10-year horizon (home-country bias; CFP Module 8) — or > 50% (over-rotation away from home market). | `attention` | `{intl_pct, recommended_range, country_breakdown}` |
| 11 | `asset_location_inefficiency` | Tax-inefficient holdings in suboptimal accounts: REITs / high-yield bonds / actively-managed in **taxable**; munis in IRA; lowest-growth assets in Roth. Per CFP Module 7. | `attention` | `[{holding, current_account, recommended_account, reason}]` |
| 12 | `tax_loss_harvest_candidate` | In **taxable** accounts only: any holding with unrealized loss > 5% AND > $500 absolute. Skips IRAs/HSA where TLH provides no benefit. Wash-sale rule reminded in narrative. | `context` (opportunity, not a problem) | `[{ticker, account, loss, pct_loss}]` |
| 13 | `employer_stock_concentration` | RSUs + open-market positions in `profile.employer_ticker` > 10% of total portfolio. CFP Modules 2 & 8 explicitly flag employer-stock concentration as a high-impact, common mistake. | `attention` if 10–20%; `urgent` if > 20% | `{ticker, pct, rsu_value, market_value, total_employer_exposure}` |
| 14 | `pre_retirement_equity_risk` | Within 10 years of `target_retirement_year` AND equity > 70%. Sequence-of-returns risk per CFP Module 6 — a 30% drawdown in the first 5 years of retirement is far more damaging than the same drawdown later. | `attention`; `urgent` within 5 years AND equity > 80% | `{years_to_retirement, equity_pct, recommended_max}` |
| 15 | `inflation_hedge_exposure` | Zero allocation to TIPS, REITs, commodities, AND international equity for users with > 10-year horizon. CFP Module 2 (inflation risk) — long-term cash + nominal-bond-only portfolios fail to preserve purchasing power. | `context` | `{has_tips, has_reits, has_commodities, has_intl}` |

### 6.1 Severity semantics

- **`urgent`** — something is broken or a hard target is missed; surface prominently; narrator should lead with it.
- **`attention`** — warrants review when convenient; surface in main body.
- **`context`** — informational, not a call to action (benchmark delta, current gain); narrator can reference, should not open with.
- **`positive`** — something going well; use sparingly to balance tone.

### 6.2 Glide-path defaults (used by #5 and #14)

Per CFP Module 5 (Life-Cycle Asset Allocation). Each cell shows the equity / bond / (cash + RE/alt) split. The bond-leg minimum is what observation #5 most often fires on; pure-equity portfolios are the most common gap among long-horizon retail investors.

| Age | Conservative | Moderate | Moderate-aggressive | Aggressive |
|---|---|---|---|---|
| < 35 | 70 / 25 / 5 | 80 / 15 / 5 | 88 / 7 / 5 | 92 / 3 / 5 |
| 35–49 | 60 / 32 / 8 | 72 / 22 / 6 | 80 / 14 / 6 | 88 / 7 / 5 |
| 50–59 | 50 / 42 / 8 | 60 / 32 / 8 | 70 / 22 / 8 | 80 / 14 / 6 |
| 60+ | 40 / 50 / 10 | 50 / 42 / 8 | 60 / 32 / 8 | 70 / 22 / 8 |

Equity = liquid equity holdings (Fidelity Brokerage + Roth + HSA + Robinhood equity positions) + 401(k) equity funds. Bond = bond funds + bond ETFs + money-market positions designated as fixed-income. Cash = external cash + sweep/money-market. Each is divided by total portfolio (excluding angel/illiquid for the comparison so the glide path is meaningful). The glide path is the only target available in v1; an explicit per-asset-class `target_allocation` field is deferred (see §7.1).

### 6.3 Dedup

Each finding has a stable `(category, key)` tuple. The `state.diff(today, yesterday)` function classifies:
- **`new`** — `(category, key)` not present yesterday.
- **`standing`** — same `(category, key)` and same `severity` as yesterday.
- **`changed`** — same `(category, key)` but different `severity`. Treated as `new` for narrative purposes.

The narrator receives findings with a `classification` field set accordingly. Its system prompt instructs: give `new`/`changed` a full sentence or two of narrative; reduce `standing` to a compact reference in the footer.

### 6.4 Hard rules

`profile.hard_rules` is a list of free-form strings. The narrator's system prompt includes them under:

```
HARD RULES (NEVER CONTRADICT):
- {hard_rule_1}
- {hard_rule_2}
...
```

The narrator is instructed that if an observation would imply advice that violates a hard rule, the narrative must acknowledge the tension without suggesting the violation. Example: if observation #1 flags Defense Tech concentration and `hard_rules: ["never recommend selling Anduril — conviction hold"]`, the narrative says "Defense Tech concentration is 48%, almost entirely in Anduril, which is held as a conviction position; diversification could be achieved by tilting new contributions elsewhere."

### 6.5 Adding an observation later

1. Write a new pure function in `observations.py`.
2. Add a row to this catalog table.
3. Add unit tests (triggers at threshold, just below, just above; severity escalation; detail payload shape).

The narrator does not need changes: it reasons over the Finding list uniformly.

### 6.6 Mapping observations to CFP modules

Provenance — every observation is anchored in a published CFP framework so the brief never invents thresholds out of thin air. Source: `Project Finance/financial_agent_knowledge_base.docx`.

| Observation | CFP module | Concept anchor |
|---|---|---|
| #1 sector_concentration | Module 2 (Risk Taxonomy) | Concentration risk — over-exposure to a single sector is unsystematic, can be diversified away, and is uncompensated. |
| #2 single_position_concentration | Module 2 (Risk Taxonomy) | Same as above, applied to a single security. |
| #3 cash_vs_target | Module 6 (Retirement Planning) | Emergency fund: 3–6 months of expenses in liquid, FDIC-insured accounts. Excess cash = drag on real returns vs ~3% inflation. |
| #4 margin_leverage | Module 2 (Risk Taxonomy) | Leverage amplifies both gains and losses; CFP guidance treats sustained margin > 25% of equity as inappropriate for long-horizon retail. |
| #5 glide_path_drift | Module 5 (Life-Cycle Asset Allocation) | Human-capital theory: equity/bond split should track decades remaining to retirement, with bond floor as a sequence-of-returns hedge. |
| #6 illiquid_ratio | Module 2 (Risk Taxonomy: Liquidity Risk) | Illiquid assets restrict ability to rebalance or meet obligations. |
| #7 upcoming_expense_coverage | Module 9 (Portfolio Construction) | Risk capacity: known near-term obligations require matched liquidity. |
| #8 ytd_vs_benchmark | Module 2 (CAPM, Alpha) | Alpha context — informational only; the brief never recommends action based on a single year's relative performance. |
| #9 ytd_investment_gain | Module 9 (Portfolio Construction) | Standard reporting metric. |
| #10 international_equity_share | Module 8 (Behavioral: Home-Country Bias) | US is ~60% of global market cap; US investors typically hold > 75% domestic. |
| #11 asset_location_inefficiency | Module 7 (Tax-Advantaged Accounts) | Asset location can add 0.2–0.8 % annually in after-tax returns with no change in risk. |
| #12 tax_loss_harvest_candidate | Module 7 (Capital Gains Framework) | Realized losses offset gains; up to $3,000/yr against ordinary income; wash-sale rule constrains the mechanic. |
| #13 employer_stock_concentration | Modules 2 & 8 | Employer-stock concentration is repeatedly called out as the highest-impact common mistake in retail portfolios. |
| #14 pre_retirement_equity_risk | Module 6 (Sequence-of-Returns Risk) | Most acute in years -5 to +5 around retirement start; demands de-risking glide path. |
| #15 inflation_hedge_exposure | Module 2 (Inflation Risk) | Long-run real return on cash and nominal bonds is near zero or negative; equities + TIPS + real assets are the standard hedges. |

When a new observation is added, the corresponding CFP module reference is required in the table — both as documentation and as a forcing function against ad-hoc rule invention.

### 6.7 Narrator constraints from the CFP body of knowledge

The narrator's system prompt encodes the CFP-aligned guardrails verbatim. These are not observations; they shape every output regardless of which findings fired.

**Required disclosures, included in every brief:**
- Past performance does not guarantee future results.
- All investments carry risk, including potential loss of principal.
- This is general educational information, not personalized financial advice.
- Tax, legal, and estate planning recommendations require licensed professionals.

**Phrases the narrator MUST use** (from CFP knowledge base Module 10):
- "Historically, this asset class has returned…"
- "A commonly recommended approach for someone in your situation is…"
- "This aligns with general principles of long-term investing. A licensed CFP can tailor this to your specific situation."
- "Past performance does not guarantee future results, but historically…"
- "The CFP Board's guidelines suggest…"

**Phrases the narrator MUST NEVER use:**
- "This investment will return X%"
- "You should buy / sell X"
- "Based on everything you've told me, my advice is…"
- "I am a Certified Financial Planner" — or any claim of licensure.
- "I'm confident this is the right move for you"

**Topics requiring mandatory professional referral** — the narrator surfaces a referral, never substitutes for one:
- Individual-specific tax questions → CPA / Enrolled Agent.
- Wills / trusts / POA → estate planning attorney.
- Insurance product recommendations → licensed insurance agent.
- Complex Social Security claiming strategies → SSA or CFP specialist.
- Bankruptcy consideration → credit counselor (NFCC member) or bankruptcy attorney.

**Tone rules:**
- Calm, evidence-based, non-alarmist — explicitly during market drawdowns (CFP Module 10).
- Frame in terms of the user's pre-committed plan, not market timing.
- When user behavior aligns with a known bias (loss aversion, recency, anchoring), name the bias once and offer the mechanical counter-action (rebalance, IPS, dollar-cost averaging) — do not lecture.

---

## 7. User Profile Schema

Stored at `Project Finance/user_profile.json`, gitignored. A safe example is committed at `user_profile.example.json`.

```yaml
name: "D Heather Nguyen"
birth_year: 1985
target_retirement_year: 2050
risk_tolerance: "moderate-aggressive"  # conservative | moderate | moderate-aggressive | aggressive

tax_situation:
  filing_status: "single"              # single | married_joint | married_separate | head_of_household
  federal_bracket: "24%"
  state: "CA"

employment:
  employer_ticker: "WMT"               # for observation #13; null if not applicable
  monthly_expenses: 8000               # for observation #3 (cash buffer in months); approximate is fine

concentration_limits:
  max_single_position: 0.10            # fraction of liquid portfolio
  max_sector: 0.30

liquidity:
  emergency_fund_target: 50000         # CFP standard: 3–6 months of expenses
  known_upcoming_expenses:
    - { amount: 80000, purpose: "house down payment", target_year: 2028 }

hard_rules:
  - "never recommend selling Anduril — conviction hold"
  - "avoid recommending short-term capital gains realization"

goals:
  - "retire by 2050"
  - "$100K house down payment by 2028"
```

### 7.1 Not in v1 (added later when needed)

- `target_allocation` — explicit per-asset-class targets. Inferred from `risk_tolerance` + age for now.
- `holding_notes` — per-ticker conviction/notes. `hard_rules` covers the high-conviction names for v1.
- Tax-lot detail — deferred to Phase 4 (tactical trade recs).

### 7.2 Validation

- Schema validated on load via a typed `Profile` dataclass (pydantic-style) with defaults.
- Missing file → `load_profile()` returns defaults with `profile_missing=True`.
- Malformed JSON → same behavior, with an additional logged warning.
- The Recommendations tab's header surfaces `profile_missing` or validation warnings so the user knows why advice feels generic.

---

## 8. Data Flow

### 8.1 Per daily run

**Inputs:**
- `model` — dict returned by existing `build_model()`.
- `user_profile.json` — loaded, validated, cached within the process.
- Most recent `advisor_state/findings_*.json` strictly before today's date.

**Outputs:**
- `advisor_state/findings_YYYY-MM-DD.json` — today's findings (machine-readable).
- `advisor_state/brief_YYYY-MM-DD.md` — rendered markdown brief.
- `Recommendations` tab appended to `2026_Portfolio_Analysis.xlsx`.

### 8.2 Sequence

```
run_daily(model, workbook_path):
  1. profile = profile.load()                                   # <50 ms
  2. findings_today = observations.run(model, profile)          # deterministic
  3. findings_yesterday = state.load_most_recent_before(today)
  4. classified = state.diff(findings_today, findings_yesterday)
  5. brief_md = narrator.compose(classified, profile)           # one Claude API call (or fallback)
  6. state.save(findings_today, brief_md)
  7. writer.write_recommendations_tab(workbook_path, brief_md, findings_today)
```

Step 5 has a fallback path (see §9) that renders findings deterministically to markdown when the LLM is unavailable. Steps 6 and 7 always run so at minimum the workbook gets a findings-only tab.

---

## 9. Error Handling

The advisor degrades gracefully. No failure mode produces an exception that escapes `run_daily()` or corrupts the workbook.

| Failure mode | Behavior | Workbook impact |
|---|---|---|
| `user_profile.json` missing | Log warning, load defaults. Tab header notes `Profile missing — defaults in use`. | Tab renders. |
| `user_profile.json` malformed | Log error, load defaults with explicit warning in tab header. | Tab renders. |
| Individual observation raises | Log, skip that observation. Other findings still surface. | Tab renders without the failing finding. |
| `ANTHROPIC_API_KEY` missing | Skip narrator; render findings-only markdown deterministically from Finding list. | Tab renders without LLM narrative. |
| Claude API call fails (network/5xx/rate limit) | Log, fall back to deterministic rendering. | Same. |
| Claude API returns malformed JSON | Log, fall back. | Same. |
| `openpyxl` writer fails | Log, workbook unchanged. | Workbook still has all pipeline-built tabs. |
| `run_daily` raises unexpected exception | Caught by `daily_pipeline.py` integration shim; logged, pipeline exit code ≤ 2. | None. |

**Determinism guarantee:** the workbook is saved by the pipeline before the advisor ever runs. Advisor only *adds* a tab at the end; if anything fails, the workbook keeps the state it had before the advisor started.

---

## 10. Testing Strategy

Layers follow the pattern established in `tests/README.md` (2026-04-24).

### 10.1 Unit tests

- **`tests/advisor/test_observations.py`** — one module section per observation. Each function gets tests for: *triggers at threshold*, *does not trigger just below*, *escalates severity at upper threshold*, *dedup key is stable across runs*. Fixtures are small inline dicts.
- **`tests/advisor/test_state.py`** — `diff()` classifies `new` / `standing` / `changed` correctly. First run (no yesterday) → all findings classified `new`. Severity change → classified `changed`.
- **`tests/advisor/test_profile.py`** — valid profile loads; missing file → defaults + `profile_missing=True`; malformed JSON → same + logged warning; partial profile applies defaults to missing fields.

### 10.2 Integration tests (stubbed LLM)

- **`tests/advisor/test_narrator.py`** — injectable `AnthropicClient`. Stub returns canned JSON; assert the deterministic renderer converts it to markdown containing expected sections. Fallback path: stub raises / returns malformed JSON → assert findings-only fallback is used and no exception escapes. Hard-rules passthrough: stub receives system prompt containing each `profile.hard_rules` entry verbatim.
- **`tests/advisor/test_run_daily.py`** — builds a minimal workbook via the golden fixture pattern, calls `run_daily()` with stubbed narrator → assert `Recommendations` tab exists and contains findings content. Second invocation with day-1 state file present → assert dedup flows to the tab output.

### 10.3 Pipeline regression extension

- **`test_advisor_failure_is_non_fatal`** — in `tests/test_regressions.py`: simulate narrator raising (e.g. no API key) → `run_daily_pipeline` returns exit code ≤ 2, workbook unchanged from pre-advisor state.

### 10.4 Contract test (marked `@pytest.mark.contract`, skipped by default)

- **`tests/advisor/test_claude_api_contract.py`** — one real Claude API call with a fixed prompt → response parses to expected schema. Run manually or weekly (`pytest -m contract`).

### 10.5 Coverage matrix

| Bug class | Caught by |
|---|---|
| Observation threshold/math wrong | `test_observations.py` |
| Profile schema drift | `test_profile.py` |
| Dedup classification wrong | `test_state.py` |
| Narrator crashes daily run | `test_advisor_failure_is_non_fatal` |
| Narrator emits malformed output | `test_narrator.py` fallback path |
| Claude API shape drift | `test_claude_api_contract.py` (weekly) |
| `Recommendations` tab structure drift | `test_run_daily.py` |

Target: ~40 new tests (15 observations × ~2.5 tests each on average for trigger/threshold/escalation, plus state, profile, narrator, run_daily, classifier, and pipeline-regression tests). Suite wall-clock < 15 seconds combined with the existing 16 tests, since none touch the network in the default suite.

A new module — `tests/advisor/test_asset_classifier.py` — covers the ticker-classification table: known equity/bond/cash/REIT/TIPS tickers map correctly; unknown ticker falls through to `equity` with a logged warning (so it surfaces but doesn't break the pipeline).

### 10.6 Not tested

- LLM output quality. Not automatable; user judges by reading the brief.
- Actual network behavior. Stubbed by default.
- Prompt token counts / prompt-engineering specifics.

---

## 11. Rollout Phases

### Phase 1 — v1 (scope of this spec)

- `advisor/` package with all modules listed in §5.3.
- All 15 observations from §6 (the original 9 plus the CFP-aligned additions: international share, asset location, TLH candidates, employer-stock concentration, pre-retirement equity risk, inflation hedge exposure; observation #5 reframed to multi-leg glide-path drift).
- Narrator using Claude Opus 4.7 + prompt caching, with the CFP-aligned tone constraints from §6.7 baked into the system prompt.
- CLI entry point (`python -m advisor`).
- `daily_pipeline.py` integration (non-fatal, guarded).
- `Recommendations` tab written to workbook.
- `user_profile.example.json` committed; `user_profile.json` gitignored.
- Full test suite per §10.
- `advisor_state/` directory, gitignored.

### Phase 2 — Claude Code slash command

- Ship after Phase 1 has run for ~a week and the brief quality is validated by reading.
- `/portfolio-advice` slash command loads today's findings + profile into a Claude Code conversation with a dedicated system prompt.
- Same observation logic; slash command is a thin consumer. Expose a `advisor.get_context()` helper if needed.

### Phase 3 — Market context (still strategic)

- Optional `market_brief` input: either (a) a manually maintained weekly macro notes file, or (b) a tool the slash command can call (WebSearch).
- 1-2 new "market-aware" observations.
- Daily path stays pure-portfolio (deterministic); market context is an on-demand enrichment.

### Phase 4 — Tactical trade suggestions (D)

- New `advisor/trade_candidates.py`: deterministic generator of candidate trades respecting hard rules.
- Narrator evolves into a tool-using agent. Tools: `whatif_portfolio(trades)`, `tax_impact(trade)`, `compare_to_target_allocation(trades)`.
- Requires tax-lot data; extends SnapTrade/Fidelity extract.
- On-demand slash command becomes the primary surface; daily tab stays strategic-only (tactical without human context is dangerous).

### Phase-independent non-goals

- Never auto-executes trades. Human is in the loop forever.
- Never claims market-direction confidence. "Given current data, X seems imbalanced" is acceptable; "the market will do Y" is not.
- Never suggests violating hard rules.

### Phase 1 shipping criteria

- Brief arrives with daily workbook, always.
- Zero regressions in existing test suite.
- New advisor test suite at 100% pass.
- One week of reading the brief, user confirms it's *useful, not generic*. If generic, tune observations or narrator before Phase 2.

---

## 12. Open Questions Deferred

These are deliberate deferrals with a planned resolution path, not blockers on v1.

- **How much history does the narrator get for dedup?** V1 compares today vs the single most-recent prior findings file. If "standing concerns" needs to distinguish "flagged 3 days" vs "flagged 30 days" for tone, we'll add a small sliding window.
- **Asset-class classification source.** Several new observations (#5 multi-leg glide path, #11 asset location, #15 inflation hedge) need a per-holding asset-class tag (equity / bond / cash / REIT / TIPS / commodity / international). v1 derives this from a hand-maintained map keyed off ticker (extending the existing `sector_map`), with a hard-coded fallback list for common tickers (FCASH/SPAXX/FDRXX → cash, AGG/BND → bond, VNQ/IYR → REIT, etc.). Open question: do we let the narrator request a classification from the user when an unknown ticker appears, or fail closed and add it manually? Defer until first miss.
- **Multi-user.** Not a concern (single user).
- **Notifications.** Out of scope. The brief lives in the workbook; the user reads it when they open the file. Email/push alerts are not on any roadmap.
- **Handling when SnapTrade is down.** The pipeline already handles this; the advisor operates on whatever model the pipeline produced. No special casing needed.
- **Localization.** English only. Not on any roadmap.

---

## 13. References

- Existing pipeline: `Project Finance/daily_pipeline.py`, `portfolio_model.py`, `build_workbook.py`.
- Existing test harness: `Project Finance/tests/README.md` (2026-04-24).
- **CFP body of knowledge:** `Project Finance/financial_agent_knowledge_base.docx` — the authoritative source for thresholds, glide paths, asset-location guidance, behavioral framing, required disclosures, and the use/avoid phrase list referenced throughout §6.6 and §6.7. Any new observation should map back to a CFP module here.
- Claude API SDK: `anthropic` Python package; model `claude-opus-4-7`; use prompt caching per superpowers:claude-api guidance.
- Validator drift memory: `memory/project_validator_drift.md` — any changes to the builder must keep `registry.py` in sync, including the new `Recommendations` tab if it becomes validated.
- Project layout memory: `memory/project_layout.md` — advisor package lives at `Project Finance/advisor/` (flat layout, NOT `repo/src/advisor/`), consistent with the live code path.
