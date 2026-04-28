"""Load and validate user_profile.json for the advisor."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaxSituation:
    filing_status: str = "single"
    federal_bracket: str = ""
    state: str = ""


@dataclass
class Employment:
    employer_ticker: Optional[str] = None
    monthly_expenses: Optional[float] = None


@dataclass
class ConcentrationLimits:
    max_single_position: float = 0.10
    max_sector: float = 0.30


@dataclass
class UpcomingExpense:
    amount: float
    purpose: str
    target_year: int


@dataclass
class Liquidity:
    emergency_fund_target: float = 0
    known_upcoming_expenses: List[UpcomingExpense] = field(default_factory=list)


@dataclass
class Profile:
    name: str = ""
    birth_year: Optional[int] = None
    target_retirement_year: Optional[int] = None
    risk_tolerance: str = "moderate"  # default if absent
    tax_situation: TaxSituation = field(default_factory=TaxSituation)
    employment: Employment = field(default_factory=Employment)
    concentration_limits: ConcentrationLimits = field(default_factory=ConcentrationLimits)
    liquidity: Liquidity = field(default_factory=Liquidity)
    hard_rules: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    profile_missing: bool = False


def _to_tax(d: dict) -> TaxSituation:
    return TaxSituation(
        filing_status=d.get("filing_status", "single"),
        federal_bracket=d.get("federal_bracket", ""),
        state=d.get("state", ""),
    )


def _to_employment(d: dict) -> Employment:
    return Employment(
        employer_ticker=d.get("employer_ticker"),
        monthly_expenses=d.get("monthly_expenses"),
    )


def _to_limits(d: dict) -> ConcentrationLimits:
    return ConcentrationLimits(
        max_single_position=float(d.get("max_single_position", 0.10)),
        max_sector=float(d.get("max_sector", 0.30)),
    )


def _to_liquidity(d: dict) -> Liquidity:
    expenses = [
        UpcomingExpense(
            amount=float(e["amount"]),
            purpose=str(e.get("purpose", "")),
            target_year=int(e["target_year"]),
        )
        for e in d.get("known_upcoming_expenses", [])
    ]
    return Liquidity(
        emergency_fund_target=float(d.get("emergency_fund_target", 0)),
        known_upcoming_expenses=expenses,
    )


def load_profile(path: Path) -> Profile:
    """Load and validate a user profile from a JSON file.

    Returns a Profile with .profile_missing=True (and defaults populated) if
    the file is missing or malformed; never raises.
    """
    if not path.exists():
        logger.warning(f"user_profile.json missing at {path}; using defaults")
        return Profile(profile_missing=True)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(f"user_profile.json is malformed ({exc}); using defaults")
        return Profile(profile_missing=True)

    try:
        return Profile(
            name=raw.get("name", ""),
            birth_year=raw.get("birth_year"),
            target_retirement_year=raw.get("target_retirement_year"),
            risk_tolerance=raw.get("risk_tolerance", "moderate"),
            tax_situation=_to_tax(raw.get("tax_situation", {})),
            employment=_to_employment(raw.get("employment", {})),
            concentration_limits=_to_limits(raw.get("concentration_limits", {})),
            liquidity=_to_liquidity(raw.get("liquidity", {})),
            hard_rules=list(raw.get("hard_rules", [])),
            goals=list(raw.get("goals", [])),
            profile_missing=False,
        )
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning(f"user_profile.json data is malformed ({exc}); using defaults")
        return Profile(profile_missing=True)
