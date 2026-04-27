# advisor/narrator.py
"""LLM narrator. Single Claude API call; deterministic fallback on failure.

Tone constraints come from the CFP body of knowledge (see spec §6.7):
required disclosures, USE/AVOID phrase lists, mandatory professional referrals.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .fallback import render_findings_only
from .observations import Finding
from .profile import Profile

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-7"
MAX_TOKENS = 2500

_SYSTEM_PROMPT_TEMPLATE = """You are a portfolio-advisory narrator that writes a one-page strategic brief from a structured list of findings about the user's portfolio. You are NOT a licensed financial advisor; you write educational narrative grounded in commonly accepted CFP frameworks.

REQUIRED DISCLOSURES — every brief must implicitly carry these (you don't need to list them as bullets, but the tone must be consistent):
- Past performance does not guarantee future results.
- All investments carry risk, including potential loss of principal.
- This is general educational information, not personalized financial advice.
- Tax, legal, and estate planning recommendations require licensed professionals.

USE phrasings like:
- "Historically, this asset class has returned…"
- "A commonly recommended approach for someone in your situation is…"
- "This aligns with general principles of long-term investing. A licensed CFP can tailor this to your specific situation."
- "The CFP Board's guidelines suggest…"

AVOID phrasings like:
- "This investment will return X%"
- "You should buy / sell X"
- "Based on everything you've told me, my advice is…"
- "I am a Certified Financial Planner" — never claim licensure.

HARD RULES (NEVER CONTRADICT — verbatim from user):
{hard_rules_block}

Tone: calm, evidence-based, non-alarmist. When user behavior aligns with a known bias (loss aversion, recency, anchoring), name the bias once and offer the mechanical counter-action — do not lecture.

Output: a JSON object with this exact schema. Do NOT include any prose outside the JSON.
{{
  "headline": "<one sentence summarizing portfolio state>",
  "new": [
    {{"category": "<finding category>", "narrative": "<1-3 sentences interpreting this finding for the user, respecting hard rules>"}}
  ],
  "standing": [
    {{"category": "<finding category>", "summary": "<short reminder one-liner>"}}
  ]
}}

Sort `new` so that urgent items appear first, then attention, then context. Mark `standing` items with a brief one-liner each — do not re-explain. If there are no findings at all, return: {{"headline": "All clear.", "new": [], "standing": []}}."""


def _system_prompt(profile: Profile) -> str:
    rules = profile.hard_rules or ["(none)"]
    block = "\n".join(f"- {r}" for r in rules)
    return _SYSTEM_PROMPT_TEMPLATE.format(hard_rules_block=block)


def _user_prompt(classified: Dict[str, List[Finding]], profile: Profile) -> str:
    payload = {
        "profile_summary": {
            "name": profile.name,
            "birth_year": profile.birth_year,
            "target_retirement_year": profile.target_retirement_year,
            "risk_tolerance": profile.risk_tolerance,
            "tax_situation": asdict(profile.tax_situation),
            "goals": profile.goals,
            "profile_missing": profile.profile_missing,
        },
        "findings": {
            "new": [asdict(f) for f in classified.get("new", [])],
            "changed": [asdict(f) for f in classified.get("changed", [])],
            "standing": [asdict(f) for f in classified.get("standing", [])],
        },
    }
    return json.dumps(payload, indent=2, default=str)


def _render_from_json(data: dict, classified: Dict[str, List[Finding]]) -> str:
    headline = data.get("headline", "Portfolio summary.")
    lines: List[str] = []
    lines.append("# Recommendations\n")
    lines.append(
        "_Past performance does not guarantee future results. "
        "All investments carry risk, including potential loss of principal. "
        "This is general educational information, not personalized financial advice._\n"
    )
    lines.append(f"\n## Headline\n\n{headline}\n")

    new_items = data.get("new", []) or []
    if new_items:
        lines.append("\n## New / Changed observations\n")
        for item in new_items:
            lines.append(f"- **{item.get('category', '?')}** — {item.get('narrative', '')}")
        lines.append("")

    standing_items = data.get("standing", []) or []
    if standing_items:
        lines.append("\n## Standing concerns\n")
        for item in standing_items:
            lines.append(f"- {item.get('category', '?')}: {item.get('summary', '')}")
        lines.append("")

    return "\n".join(lines)


def compose(classified: Dict[str, List[Finding]], profile: Profile,
            client: Optional[Any] = None) -> str:
    """Compose a markdown brief.

    `client` is duck-typed to anthropic.Anthropic — anything with
    .messages.create(...). Inject a stub in tests; in production, leave
    None and the function constructs an Anthropic client from
    ANTHROPIC_API_KEY (falling back to render_findings_only when absent).
    """
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            # Fall back to the project-local key file so direct `python daily_pipeline.py`
            # invocations work without a global env var (which would conflict with
            # Claude Code's OAuth subscription).
            import pathlib
            _key_file = pathlib.Path(__file__).resolve().parent.parent / ".anthropic_key"
            if _key_file.exists():
                api_key = _key_file.read_text().strip() or None
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; rendering findings-only fallback.")
            return render_findings_only(classified)
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as exc:
            logger.warning(f"Could not initialize Anthropic client ({exc}); falling back.")
            return render_findings_only(classified)

    try:
        # System prompt is sent as a cacheable content block (5-min TTL).
        # The user message is dynamic (today's findings) and not cached.
        system_blocks = [
            {
                "type": "text",
                "text": _system_prompt(profile),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            messages=[{"role": "user", "content": _user_prompt(classified, profile)}],
        )
        text = resp.content[0].text if resp.content else ""
        data = json.loads(text)
    except Exception as exc:
        logger.warning(f"Narrator call failed ({exc}); falling back to findings-only.")
        return render_findings_only(classified)

    return _render_from_json(data, classified)
