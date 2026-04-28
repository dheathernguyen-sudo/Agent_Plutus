"""Tests for advisor.fallback — deterministic findings → markdown."""


def _f(category, key, severity, headline, detail=None):
    from advisor.observations import Finding
    return Finding(category=category, key=key, severity=severity,
                   headline=headline, detail=detail or {})


def test_render_empty_findings():
    from advisor.fallback import render_findings_only

    md = render_findings_only({"new": [], "standing": [], "changed": []})
    assert "no findings" in md.lower() or "all clear" in md.lower()


def test_render_orders_urgent_first():
    from advisor.fallback import render_findings_only
    findings = {
        "new": [
            _f("c1", "k1", "attention", "Attention item"),
            _f("c2", "k2", "urgent", "Urgent item"),
            _f("c3", "k3", "context", "Context item"),
        ],
        "standing": [],
        "changed": [],
    }
    md = render_findings_only(findings)
    # Urgent must appear before attention in the output
    assert md.index("Urgent item") < md.index("Attention item")
    assert md.index("Attention item") < md.index("Context item")


def test_standing_concerns_section_present_when_any():
    from advisor.fallback import render_findings_only
    md = render_findings_only({
        "new": [],
        "standing": [_f("c", "k", "attention", "Old item")],
        "changed": [],
    })
    assert "standing" in md.lower()
    assert "old item" in md.lower()
