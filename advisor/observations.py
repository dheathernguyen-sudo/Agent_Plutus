"""Pure-function observation generators that produce structured Findings
from a portfolio model and user profile.

Each observation function in this module has the signature:
    fn(model: dict, profile: Profile) -> List[Finding]

The run() function calls every registered observation in order and
concatenates results.

All thresholds are CFP-aligned per Project Finance/financial_agent_knowledge_base.docx
(see spec §6.6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

from .profile import Profile

VALID_SEVERITIES = {"urgent", "attention", "context", "positive"}


@dataclass
class Finding:
    category: str
    key: str
    severity: str
    headline: str
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity {self.severity!r}; "
                f"must be one of {sorted(VALID_SEVERITIES)}"
            )


# Observation functions register themselves here in import order.
_OBSERVATIONS: List[Callable[[dict, Profile], List[Finding]]] = []


def _register(fn: Callable[[dict, Profile], List[Finding]]):
    _OBSERVATIONS.append(fn)
    return fn


def _ext_cash_total(model: dict) -> float:
    """Sum external cash, handling both numeric and Plaid dict values.

    Plaid returns {"chase": {"accounts": [...], "total": X}, ...} but tests
    inject plain numbers. Both are normalised here so callers don't fail.
    """
    ext = (model.get("cash", {}).get("external", {}) or {})
    total = 0.0
    for v in ext.values():
        if isinstance(v, dict):
            total += v.get("total", 0) or 0
        else:
            total += v or 0
    return total


def run(model: dict, profile: Profile) -> List[Finding]:
    """Run every registered observation generator and concatenate results."""
    findings: List[Finding] = []
    for fn in _OBSERVATIONS:
        try:
            findings.extend(fn(model, profile) or [])
        except Exception as exc:
            import logging
            logging.warning(f"Observation {fn.__name__} raised: {exc}; skipping")
    return findings


# ---------------------------------------------------------------------------
# Observation #1 — sector_concentration
# ---------------------------------------------------------------------------
@_register
def _obs_sector_concentration(model: dict, profile: Profile) -> List[Finding]:
    out: List[Finding] = []
    limit = profile.concentration_limits.max_sector
    for sec in model.get("sectors", []) or []:
        pct = sec.get("pct", 0) or 0
        if pct <= limit:
            continue
        severity = "urgent" if pct > 0.50 else "attention"
        contribs = []
        for acct, value in (sec.get("by_account", {}) or {}).items():
            contribs.append({"account": acct, "mv": value})
        contribs.sort(key=lambda c: c["mv"], reverse=True)
        out.append(Finding(
            category="sector_concentration",
            key=sec.get("name", "Unknown"),
            severity=severity,
            headline=f"{sec.get('name')} is {pct:.0%} of portfolio (limit {limit:.0%}).",
            detail={
                "sector": sec.get("name"),
                "pct": pct,
                "value": sec.get("value"),
                "top_contributors": contribs[:3],
                "limit": limit,
            },
        ))
    return out


# ---------------------------------------------------------------------------
# Observation #2 — single_position_concentration
# ---------------------------------------------------------------------------
@_register
def _obs_single_position_concentration(model: dict, profile: Profile) -> List[Finding]:
    out: List[Finding] = []
    limit = profile.concentration_limits.max_single_position
    # Total liquid value = sum of liquid accounts' (holdings MV + cash_position)
    total_liquid = 0.0
    for key in model.get("liquid_accounts", []):
        acct = model["accounts"][key]
        total_liquid += sum(h.get("mv", 0) or 0 for h in acct.get("holdings", []))
        total_liquid += acct.get("cash_position", 0) or 0
    if total_liquid <= 0:
        return out

    for key in model.get("liquid_accounts", []):
        acct = model["accounts"][key]
        for h in acct.get("holdings", []):
            mv = h.get("mv", 0) or 0
            pct = mv / total_liquid
            if pct <= limit:
                continue
            severity = "urgent" if pct > 0.20 else "attention"
            ticker = h.get("ticker", "?")
            out.append(Finding(
                category="single_position_concentration",
                key=ticker,
                severity=severity,
                headline=f"{ticker} in {acct.get('tab_name', key)} is {pct:.0%} of liquid portfolio.",
                detail={
                    "ticker": ticker,
                    "account": acct.get("tab_name", key),
                    "pct": pct,
                    "mv": mv,
                    "cb": h.get("cb", 0) or 0,
                    "limit": limit,
                },
            ))
    return out


# ---------------------------------------------------------------------------
# Observation #3 — cash_vs_target
# ---------------------------------------------------------------------------
@_register
def _obs_cash_vs_target(model: dict, profile: Profile) -> List[Finding]:
    target = profile.liquidity.emergency_fund_target
    monthly = profile.employment.monthly_expenses
    if target <= 0:
        return []
    external = _ext_cash_total(model)

    # Urgent if cash covers fewer than 3 months of expenses (CFP standard floor).
    if monthly and external < 3 * monthly:
        return [Finding(
            category="cash_vs_target", key="external_cash",
            severity="urgent",
            headline=f"External cash ${external:,.0f} covers only {external/monthly:.1f} months of expenses (CFP floor: 3 months).",
            detail={"external_cash": external, "target": target,
                    "monthly_expenses": monthly,
                    "months_of_expenses": external / monthly,
                    "delta": external - target},
        )]

    # Attention if below the user's stated emergency_fund_target.
    if external < target:
        return [Finding(
            category="cash_vs_target", key="external_cash",
            severity="attention",
            headline=f"External cash ${external:,.0f} is below target ${target:,.0f}.",
            detail={"external_cash": external, "target": target,
                    "monthly_expenses": monthly,
                    "months_of_expenses": external / monthly if monthly else None,
                    "delta": external - target},
        )]

    # Context if more than 2× target (cash drag).
    if external > 2 * target:
        return [Finding(
            category="cash_vs_target", key="external_cash",
            severity="context",
            headline=f"External cash ${external:,.0f} is {external/target:.1f}× the target — potential cash drag versus inflation.",
            detail={"external_cash": external, "target": target,
                    "monthly_expenses": monthly,
                    "months_of_expenses": external / monthly if monthly else None,
                    "delta": external - target},
        )]

    return []


# ---------------------------------------------------------------------------
# Observation #4 — margin_leverage
# ---------------------------------------------------------------------------
@_register
def _obs_margin_leverage(model: dict, profile: Profile) -> List[Finding]:
    out: List[Finding] = []
    for key in model.get("liquid_accounts", []):
        acct = model["accounts"][key]
        debt = abs(acct.get("margin_debt", 0) or 0)
        if debt == 0:
            continue
        gross_mv = acct.get("gains", {}).get("total_mv", 0) or 0
        net = gross_mv - debt
        if net <= 0:
            continue
        ratio = debt / net
        if ratio <= 0.15:
            continue
        severity = "urgent" if ratio >= 0.25 else "attention"
        out.append(Finding(
            category="margin_leverage", key=acct.get("tab_name", key),
            severity=severity,
            headline=f"Margin debt in {acct.get('tab_name', key)} is {ratio:.0%} of net equity.",
            detail={"debt": debt, "net_mv": net, "ratio": ratio,
                    "interest_cost_est": debt * 0.05},  # ~4.5% actual rate implied by RH Gold statements (Jan–Apr 2026); 5% used as a slightly conservative estimate
        ))
    return out


# ---------------------------------------------------------------------------
# Observation #5 — glide_path_drift (multi-leg: equity / bond / cash / alt)
# ---------------------------------------------------------------------------
import datetime as _dt
from .asset_classifier import classify as _classify

# (age_min, age_max) → {tolerance: (equity_pct, bond_pct, cash_alt_pct)}
_GLIDE_PATH = {
    (0, 35): {
        "conservative": (0.70, 0.25, 0.05),
        "moderate":     (0.80, 0.15, 0.05),
        "moderate-aggressive": (0.88, 0.07, 0.05),
        "aggressive":   (0.92, 0.03, 0.05),
    },
    (35, 50): {
        "conservative": (0.60, 0.32, 0.08),
        "moderate":     (0.72, 0.22, 0.06),
        "moderate-aggressive": (0.80, 0.14, 0.06),
        "aggressive":   (0.88, 0.07, 0.05),
    },
    (50, 60): {
        "conservative": (0.50, 0.42, 0.08),
        "moderate":     (0.60, 0.32, 0.08),
        "moderate-aggressive": (0.70, 0.22, 0.08),
        "aggressive":   (0.80, 0.14, 0.06),
    },
    (60, 200): {
        "conservative": (0.40, 0.50, 0.10),
        "moderate":     (0.50, 0.42, 0.08),
        "moderate-aggressive": (0.60, 0.32, 0.08),
        "aggressive":   (0.70, 0.22, 0.08),
    },
}


def _glide_target(age: int, tolerance: str):
    for (lo, hi), bands in _GLIDE_PATH.items():
        if lo <= age < hi:
            return bands.get(tolerance, bands["moderate"])
    # Should not hit; fallback
    return (0.6, 0.3, 0.1)


def _portfolio_legs(model: dict) -> dict:
    """Return {equity, bond, cash, alt} totals across liquid + 401k accounts."""
    legs = {"equity": 0.0, "bond": 0.0, "cash": 0.0, "alt": 0.0}
    for key in model.get("liquid_accounts", []) + model.get("illiquid_accounts", []):
        acct = model["accounts"][key]
        # Skip angel — not part of glide-path comparison
        if "investments" in acct:
            continue
        for h in acct.get("holdings", []):
            cls = _classify(h.get("ticker", ""), h.get("name"))
            mv = h.get("mv", 0) or h.get("current_value", 0) or 0
            if cls == "bond":
                legs["bond"] += mv
            elif cls == "cash":
                legs["cash"] += mv
            elif cls in ("reit", "commodity", "tips"):
                legs["alt"] += mv
            else:
                legs["equity"] += mv
        # Add cash_position (uninvested cash) to cash leg
        legs["cash"] += acct.get("cash_position", 0) or 0
        # 401(k) live_holdings if present
        for h in acct.get("live_holdings", []) or []:
            cls = _classify(h.get("ticker", ""), h.get("name"))
            mv = h.get("current_value", 0) or h.get("mv", 0) or 0
            if cls == "bond":
                legs["bond"] += mv
            elif cls == "cash":
                legs["cash"] += mv
            elif cls in ("reit", "commodity", "tips"):
                legs["alt"] += mv
            else:
                legs["equity"] += mv
    return legs


@_register
def _obs_glide_path_drift(model: dict, profile: Profile) -> List[Finding]:
    if profile.birth_year is None:
        return []
    today = _dt.date.fromisoformat(model.get("as_of", _dt.date.today().isoformat()))
    age = today.year - profile.birth_year
    target_eq, target_bond, target_alt_cash = _glide_target(age, profile.risk_tolerance)

    legs = _portfolio_legs(model)
    total = sum(legs.values())
    if total <= 0:
        return []
    actual_eq = legs["equity"] / total
    actual_bond = legs["bond"] / total
    actual_cash = legs["cash"] / total
    actual_alt = legs["alt"] / total
    actual_alt_cash = actual_cash + actual_alt

    deviations = [
        {"leg": "equity", "actual": actual_eq, "target": target_eq,
         "gap": actual_eq - target_eq},
        {"leg": "bond", "actual": actual_bond, "target": target_bond,
         "gap": actual_bond - target_bond},
        {"leg": "cash_alt", "actual": actual_alt_cash, "target": target_alt_cash,
         "gap": actual_alt_cash - target_alt_cash},
    ]

    max_gap = max(abs(d["gap"]) for d in deviations)
    if max_gap <= 0.15:
        return []
    severity = "urgent" if max_gap > 0.30 else "attention"
    return [Finding(
        category="glide_path_drift", key=f"age_{age}_{profile.risk_tolerance}",
        severity=severity,
        headline=(
            f"Allocation drifted from age-{age} {profile.risk_tolerance} target: "
            f"actual {actual_eq:.0%}/{actual_bond:.0%}/{actual_alt_cash:.0%} (eq/bond/alt+cash) "
            f"vs target {target_eq:.0%}/{target_bond:.0%}/{target_alt_cash:.0%}."
        ),
        detail={
            "actual": {"equity": actual_eq, "bond": actual_bond,
                       "cash": actual_cash, "alt": actual_alt},
            "target": {"equity": target_eq, "bond": target_bond,
                       "cash_alt": target_alt_cash},
            "leg_deviations": deviations,
            "age": age,
            "rationale": "Per CFP Module 5; bond-leg deficit is the most common gap.",
        },
    )]


# ---------------------------------------------------------------------------
# Observation #6 — illiquid_ratio
# ---------------------------------------------------------------------------
@_register
def _obs_illiquid_ratio(model: dict, profile: Profile) -> List[Finding]:
    liquid_total = 0.0
    for key in model.get("liquid_accounts", []):
        acct = model["accounts"][key]
        liquid_total += acct.get("gains", {}).get("total_mv", 0) or 0
        liquid_total += acct.get("cash_position", 0) or 0
    illiquid_total = 0.0
    components = {}
    for key in model.get("illiquid_accounts", []):
        acct = model["accounts"][key]
        v = acct.get("gains", {}).get("total_mv", 0) or 0
        illiquid_total += v
        components[acct.get("tab_name", key)] = v
    total = liquid_total + illiquid_total
    if total <= 0:
        return []
    ratio = illiquid_total / total
    if ratio <= 0.60:
        return []
    severity = "urgent" if ratio > 0.75 else "attention"
    return [Finding(
        category="illiquid_ratio", key="illiquid_share",
        severity=severity,
        headline=f"Illiquid assets are {ratio:.0%} of total portfolio (401k + Angel).",
        detail={"ratio": ratio, "components": components,
                "liquid": liquid_total, "illiquid": illiquid_total},
    )]


# ---------------------------------------------------------------------------
# Observation #7 — upcoming_expense_coverage
# ---------------------------------------------------------------------------
@_register
def _obs_upcoming_expense_coverage(model: dict, profile: Profile) -> List[Finding]:
    out: List[Finding] = []
    today = _dt.date.fromisoformat(model.get("as_of", _dt.date.today().isoformat()))
    today_year = today.year
    liquid_total = sum(
        (model["accounts"][k].get("gains", {}).get("total_mv", 0) or 0)
        + (model["accounts"][k].get("cash_position", 0) or 0)
        for k in model.get("liquid_accounts", [])
    )
    external_cash = _ext_cash_total(model)
    available = liquid_total + external_cash

    for exp in profile.liquidity.known_upcoming_expenses:
        years = exp.target_year - today_year
        if years < 0:
            severity = "urgent"
            projected = available
            gap = exp.amount - projected
        else:
            projected = available * (1.05 ** years)
            gap = exp.amount - projected
            if gap <= 0:
                continue
            severity = "attention"
        out.append(Finding(
            category="upcoming_expense_coverage", key=exp.purpose,
            severity=severity,
            headline=(
                f"{exp.purpose}: ${exp.amount:,.0f} needed by {exp.target_year}; "
                f"projected available ${projected:,.0f} (gap ${gap:,.0f})."
            ),
            detail={"expense": exp.purpose, "amount": exp.amount,
                    "target_year": exp.target_year, "years_out": years,
                    "projected_liquid": projected, "gap": gap},
        ))
    return out


# ---------------------------------------------------------------------------
# Observation #8 — ytd_vs_benchmark
# ---------------------------------------------------------------------------
@_register
def _obs_ytd_vs_benchmark(model: dict, profile: Profile) -> List[Finding]:
    sp500 = (model.get("benchmarks", {}) or {}).get("S&P 500")
    if sp500 is None:
        return []
    twr_values, mv_values = [], []
    for key in model.get("liquid_accounts", []):
        acct = model["accounts"][key]
        twr = (acct.get("returns") or {}).get("twr")
        mv = acct.get("gains", {}).get("total_mv", 0) or 0
        if twr is not None and mv > 0:
            twr_values.append(twr)
            mv_values.append(mv)
    if not twr_values:
        return []
    portfolio_twr = sum(t * w for t, w in zip(twr_values, mv_values)) / sum(mv_values)
    alpha = portfolio_twr - sp500
    if abs(alpha) <= 0.05:
        return []
    return [Finding(
        category="ytd_vs_benchmark", key="liquid_vs_sp500",
        severity="context",
        headline=(
            f"Liquid YTD return {portfolio_twr:+.1%} vs S&P 500 {sp500:+.1%} "
            f"(alpha {alpha:+.1%})."
        ),
        detail={"portfolio_pct": portfolio_twr, "benchmark_pct": sp500, "alpha": alpha},
    )]


# ---------------------------------------------------------------------------
# Observation #9 — ytd_investment_gain
# ---------------------------------------------------------------------------
@_register
def _obs_ytd_investment_gain(model: dict, profile: Profile) -> List[Finding]:
    div = unr = rea = 0.0
    for key in model.get("liquid_accounts", []):
        g = model["accounts"][key].get("gains", {}) or {}
        div += g.get("dividends", 0) or 0
        unr += g.get("unrealized", 0) or 0
        rea += g.get("realized", 0) or 0
    total = div + unr + rea
    if total == 0:
        return []
    severity = "positive" if total > 0 else "context"
    return [Finding(
        category="ytd_investment_gain", key="liquid_total",
        severity=severity,
        headline=f"YTD liquid investment gain: ${total:,.0f} (div ${div:,.0f}, unrealized ${unr:,.0f}, realized ${rea:,.0f}).",
        detail={"total": total, "dividends": div,
                "unrealized": unr, "realized": rea},
    )]


# ---------------------------------------------------------------------------
# Observation #10 — international_equity_share
# ---------------------------------------------------------------------------
@_register
def _obs_international_equity_share(model: dict, profile: Profile) -> List[Finding]:
    # Long-horizon check only
    if profile.target_retirement_year:
        today = _dt.date.fromisoformat(model.get("as_of", _dt.date.today().isoformat()))
        if profile.target_retirement_year - today.year < 10:
            return []
    us_eq = intl_eq = 0.0
    for key in model.get("liquid_accounts", []) + model.get("illiquid_accounts", []):
        acct = model["accounts"][key]
        if "investments" in acct:
            continue  # angel — skip
        for h in acct.get("holdings", []):
            cls = _classify(h.get("ticker", ""), h.get("name"))
            mv = h.get("mv", 0) or 0
            if cls == "international_equity":
                intl_eq += mv
            elif cls == "equity":
                us_eq += mv
        for h in acct.get("live_holdings", []) or []:
            cls = _classify(h.get("ticker", ""), h.get("name"))
            mv = h.get("current_value", 0) or h.get("mv", 0) or 0
            if cls == "international_equity":
                intl_eq += mv
            elif cls == "equity":
                us_eq += mv
    total_eq = us_eq + intl_eq
    if total_eq <= 0:
        return []
    intl_pct = intl_eq / total_eq
    if 0.15 <= intl_pct <= 0.50:
        return []
    return [Finding(
        category="international_equity_share", key="intl_share",
        severity="attention",
        headline=(
            f"International equity is {intl_pct:.0%} of total equity — "
            f"{'below' if intl_pct < 0.15 else 'above'} the 15–50% home/global balance band."
        ),
        detail={"intl_pct": intl_pct, "us_pct": us_eq / total_eq,
                "recommended_range": "15-50%"},
    )]


# ---------------------------------------------------------------------------
# Observation #11 — asset_location_inefficiency
# ---------------------------------------------------------------------------
# Map of (asset_class, tax_status) → reason if mismatched.
# tax_status is read from acct["tax_status"]:
#   "taxable"     — Fidelity Brokerage TOD, Robinhood
#   "tax_deferred" — 401(k), Traditional IRA
#   "tax_free"    — Roth IRA, HSA
_LOCATION_RULES = [
    # (asset_class, bad_account_type, suggestion)
    ("reit", "taxable", "REIT dividends are ordinary-income; better in tax-deferred or Roth."),
    ("bond", "taxable", "Taxable bond interest is ordinary-income; better in tax-deferred."),
]


@_register
def _obs_asset_location_inefficiency(model: dict, profile: Profile) -> List[Finding]:
    items = []
    for key in model.get("liquid_accounts", []) + model.get("illiquid_accounts", []):
        acct = model["accounts"][key]
        if "investments" in acct:
            continue
        tax_status = acct.get("tax_status", "taxable")
        for h in acct.get("holdings", []):
            cls = _classify(h.get("ticker", ""), h.get("name"))
            for rule_cls, bad_status, reason in _LOCATION_RULES:
                if cls == rule_cls and tax_status == bad_status:
                    items.append({
                        "holding": h.get("ticker", "?"),
                        "current_account": acct.get("tab_name", key),
                        "asset_class": cls,
                        "recommended_account": "tax_deferred or tax_free",
                        "reason": reason,
                        "mv": h.get("mv", 0) or 0,
                    })
    if not items:
        return []
    return [Finding(
        category="asset_location_inefficiency", key="suboptimal_placements",
        severity="attention",
        headline=f"{len(items)} holding(s) placed in tax-suboptimal accounts.",
        detail={"items": items},
    )]


# ---------------------------------------------------------------------------
# Observation #12 — tax_loss_harvest_candidate (taxable accounts only)
# ---------------------------------------------------------------------------
@_register
def _obs_tax_loss_harvest_candidate(model: dict, profile: Profile) -> List[Finding]:
    items = []
    for key in model.get("liquid_accounts", []):
        acct = model["accounts"][key]
        if acct.get("tax_status", "taxable") != "taxable":
            continue
        for h in acct.get("holdings", []):
            mv = h.get("mv", 0) or 0
            cb = h.get("cb", 0) or 0
            if cb <= 0:
                continue
            loss = cb - mv  # positive = loss
            pct_loss = loss / cb
            # Both gates: $500 absolute AND > 5% pct.
            if loss >= 500 and pct_loss > 0.05:
                items.append({
                    "ticker": h.get("ticker", "?"),
                    "account": acct.get("tab_name", key),
                    "loss": loss,
                    "pct_loss": pct_loss,
                    "mv": mv,
                    "cb": cb,
                })
    if not items:
        return []
    return [Finding(
        category="tax_loss_harvest_candidate", key="tlh_opportunities",
        severity="context",
        headline=f"{len(items)} taxable position(s) with > 5% / > $500 unrealized loss.",
        detail={"items": items, "wash_sale_reminder": (
            "Cannot repurchase the same or substantially identical security within 30 days "
            "before or after realizing the loss."
        )},
    )]


# ---------------------------------------------------------------------------
# Observation #13 — employer_stock_concentration
# ---------------------------------------------------------------------------
@_register
def _obs_employer_stock_concentration(model: dict, profile: Profile) -> List[Finding]:
    ticker = (profile.employment.employer_ticker or "").upper()
    if not ticker:
        return []
    employer_value = 0.0
    total = 0.0
    for key in model.get("liquid_accounts", []) + model.get("illiquid_accounts", []):
        acct = model["accounts"][key]
        if "investments" in acct:
            continue
        for h in acct.get("holdings", []):
            mv = h.get("mv", 0) or 0
            total += mv
            if (h.get("ticker") or "").upper() == ticker:
                employer_value += mv
        total += acct.get("cash_position", 0) or 0
    if total <= 0 or employer_value <= 0:
        return []
    pct = employer_value / total
    if pct <= 0.10:
        return []
    severity = "urgent" if pct > 0.20 else "attention"
    return [Finding(
        category="employer_stock_concentration", key=ticker,
        severity=severity,
        headline=f"Employer stock {ticker} is {pct:.0%} of total portfolio.",
        detail={"ticker": ticker, "pct": pct,
                "employer_value": employer_value, "total": total},
    )]


# ---------------------------------------------------------------------------
# Observation #14 — pre_retirement_equity_risk
# ---------------------------------------------------------------------------
@_register
def _obs_pre_retirement_equity_risk(model: dict, profile: Profile) -> List[Finding]:
    if not profile.target_retirement_year:
        return []
    today = _dt.date.fromisoformat(model.get("as_of", _dt.date.today().isoformat()))
    years_out = profile.target_retirement_year - today.year
    if years_out > 10 or years_out < -1:
        return []
    legs = _portfolio_legs(model)
    total = sum(legs.values())
    if total <= 0:
        return []
    equity_pct = legs["equity"] / total
    if equity_pct <= 0.70:
        return []
    severity = "urgent" if (years_out <= 5 and equity_pct > 0.80) else "attention"
    return [Finding(
        category="pre_retirement_equity_risk", key="years_to_retirement",
        severity=severity,
        headline=(
            f"Equity is {equity_pct:.0%} with {years_out} years to target retirement; "
            f"sequence-of-returns risk per CFP Module 6."
        ),
        detail={"years_to_retirement": years_out, "equity_pct": equity_pct,
                "recommended_max": 0.70 if years_out > 5 else 0.60},
    )]


# ---------------------------------------------------------------------------
# Observation #15 — inflation_hedge_exposure
# ---------------------------------------------------------------------------
@_register
def _obs_inflation_hedge_exposure(model: dict, profile: Profile) -> List[Finding]:
    # Long-horizon only
    if not profile.target_retirement_year:
        return []
    today = _dt.date.fromisoformat(model.get("as_of", _dt.date.today().isoformat()))
    if profile.target_retirement_year - today.year < 10:
        return []
    has = {"tips": False, "reit": False, "commodity": False, "international_equity": False}
    for key in model.get("liquid_accounts", []) + model.get("illiquid_accounts", []):
        acct = model["accounts"][key]
        if "investments" in acct:
            continue
        for h in acct.get("holdings", []):
            cls = _classify(h.get("ticker", ""), h.get("name"))
            if cls in has:
                has[cls] = True
        for h in acct.get("live_holdings", []) or []:
            cls = _classify(h.get("ticker", ""), h.get("name"))
            if cls in has:
                has[cls] = True
    if any(has.values()):
        return []
    return [Finding(
        category="inflation_hedge_exposure", key="no_hedges",
        severity="context",
        headline="No allocation to TIPS, REITs, commodities, or international equity — long-horizon inflation exposure unhedged.",
        detail={"has_tips": has["tips"], "has_reits": has["reit"],
                "has_commodities": has["commodity"],
                "has_intl": has["international_equity"]},
    )]
