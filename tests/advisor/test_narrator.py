# tests/advisor/test_narrator.py
"""Tests for advisor.narrator — LLM call with stubbable client."""
import json
import logging

import pytest


class StubClient:
    """Mimics anthropic.Anthropic client for tests. The narrator only
    uses .messages.create(...)."""
    def __init__(self, response_text=None, raise_exc=None):
        self._response_text = response_text
        self._raise = raise_exc
        self.calls = []

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise:
            raise self._raise
        # Mimic anthropic Message object shape with .content[0].text
        class _Block:
            def __init__(self, text): self.text = text
        class _Resp:
            def __init__(self, text): self.content = [_Block(text)]
        return _Resp(self._response_text)


def _f(category, key, severity, headline):
    from advisor.observations import Finding
    return Finding(category=category, key=key, severity=severity,
                   headline=headline, detail={})


def _classified(findings):
    return {"new": findings, "standing": [], "changed": []}


def test_narrator_returns_markdown_with_stub_response():
    from advisor.narrator import compose
    from advisor.profile import Profile

    response_json = json.dumps({
        "headline": "Portfolio is on track.",
        "new": [{"category": "ytd_investment_gain", "narrative": "Up $10K YTD."}],
        "standing": [],
    })
    client = StubClient(response_text=response_json)
    md = compose(_classified([_f("ytd_investment_gain", "k", "positive", "h")]),
                 Profile(), client=client)
    assert "Portfolio is on track" in md
    assert "Up $10K YTD" in md


def test_narrator_falls_back_when_client_raises(caplog):
    from advisor.narrator import compose
    from advisor.profile import Profile

    client = StubClient(raise_exc=RuntimeError("network down"))
    with caplog.at_level(logging.WARNING):
        md = compose(_classified([_f("a", "b", "urgent", "urgent thing")]),
                     Profile(), client=client)
    assert "urgent thing" in md  # fallback rendered findings
    assert "network down" in caplog.text or "narrator" in caplog.text.lower()


def test_narrator_falls_back_on_malformed_json(caplog):
    from advisor.narrator import compose
    from advisor.profile import Profile

    client = StubClient(response_text="{ not valid json")
    with caplog.at_level(logging.WARNING):
        md = compose(_classified([_f("a", "b", "attention", "thing")]),
                     Profile(), client=client)
    assert "thing" in md


def _flatten_system(system):
    """system can be a string or a list of {type:'text', text, cache_control?}."""
    if isinstance(system, str):
        return system
    return "".join(b.get("text", "") for b in system or [])


def test_system_prompt_contains_hard_rules():
    from advisor.narrator import compose
    from advisor.profile import Profile

    response_json = json.dumps({"headline": "ok", "new": [], "standing": []})
    client = StubClient(response_text=response_json)
    prof = Profile(hard_rules=["never sell Anduril", "always keep $30k cash"])
    compose(_classified([]), prof, client=client)

    sys_prompt = _flatten_system(client.calls[0].get("system"))
    assert "never sell Anduril" in sys_prompt
    assert "always keep $30k cash" in sys_prompt


def test_system_prompt_contains_required_disclosures():
    from advisor.narrator import compose
    from advisor.profile import Profile

    response_json = json.dumps({"headline": "ok", "new": [], "standing": []})
    client = StubClient(response_text=response_json)
    compose(_classified([]), Profile(), client=client)

    sys_prompt = _flatten_system(client.calls[0].get("system"))
    # Required disclosures from CFP Module 1
    assert "past performance" in sys_prompt.lower()
    assert "not personalized financial advice" in sys_prompt.lower() \
        or "general educational" in sys_prompt.lower()
    # Forbidden phrases
    assert "you should buy" in sys_prompt.lower() or "AVOID" in sys_prompt


def test_system_prompt_uses_cache_control():
    """Spec §5.4 v1: system prompt is cached via cache_control: ephemeral."""
    from advisor.narrator import compose
    from advisor.profile import Profile

    response_json = json.dumps({"headline": "ok", "new": [], "standing": []})
    client = StubClient(response_text=response_json)
    compose(_classified([]), Profile(), client=client)

    system = client.calls[0].get("system")
    assert isinstance(system, list), \
        "system must be a list of content blocks to enable prompt caching"
    assert any(b.get("cache_control", {}).get("type") == "ephemeral"
               for b in system), \
        "at least one system block must carry cache_control: ephemeral"
