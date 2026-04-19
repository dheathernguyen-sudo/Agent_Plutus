"""Tests for manual_data.json parsing and validation."""

import json
import pytest


class TestManualDataStructure:
    def test_sample_has_required_keys(self, manual_data_sample):
        assert "k401_data" in manual_data_sample
        assert "angel_data" in manual_data_sample
        assert "cash_balances" in manual_data_sample

    def test_k401_quarterly_accounting_identity(self, manual_data_sample):
        """ending = beginning + ee + er + fees + change_in_value."""
        for q in manual_data_sample["k401_data"]["quarterly"]:
            expected = (
                q["beginning"]
                + q["ee_contributions"]
                + q["er_contributions"]
                + q["fees"]
                + q["change_in_value"]
            )
            assert abs(q["ending"] - expected) < 0.01, (
                f"Quarter {q['period']}: expected ending={expected}, got {q['ending']}"
            )

    def test_k401_quarterly_continuity(self, manual_data_sample):
        """Ending of Q(N) should equal beginning of Q(N+1)."""
        quarters = manual_data_sample["k401_data"]["quarterly"]
        for i in range(len(quarters) - 1):
            ending = quarters[i]["ending"]
            next_beginning = quarters[i + 1]["beginning"]
            assert abs(ending - next_beginning) < 0.01, (
                f"{quarters[i]['period']} ending={ending} != "
                f"{quarters[i+1]['period']} beginning={next_beginning}"
            )

    def test_angel_valuation_multiples(self, manual_data_sample):
        for angel in manual_data_sample["angel_data"]:
            assert angel["pm_invest"] > 0, f"{angel['company']} has zero pm_invest"
            multiple = angel["pm_latest"] / angel["pm_invest"]
            assert multiple >= 0, f"{angel['company']} has negative valuation multiple"

    def test_angel_required_fields(self, manual_data_sample):
        required = {"company", "sector", "year", "series", "amount", "pm_invest", "pm_latest", "source"}
        for angel in manual_data_sample["angel_data"]:
            missing = required - set(angel.keys())
            assert not missing, f"{angel.get('company', '?')} missing fields: {missing}"

    def test_empty_manual_data_does_not_crash(self, manual_data_empty):
        assert manual_data_empty == {}
        k401 = manual_data_empty.get("k401_data", {})
        angels = manual_data_empty.get("angel_data", [])
        cash = manual_data_empty.get("cash_balances", {})
        assert k401 == {}
        assert angels == []
        assert cash == {}

    def test_cash_balance_keys_are_strings(self, manual_data_sample):
        for key in manual_data_sample["cash_balances"]:
            assert isinstance(key, str)
            assert key.startswith("fidelity_"), f"Unexpected cash key: {key}"
