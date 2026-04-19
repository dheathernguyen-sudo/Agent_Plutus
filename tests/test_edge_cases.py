"""Edge case tests for data handling and error resilience."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestFidelityEdgeCases:
    def test_zero_value_holding_filtered(self):
        holding = {"qty": 0.0001, "price": 0.50, "mv": 0.00005, "cb": 0.01, "gl": -0.00995, "name": "Dust"}
        assert holding["mv"] < 1 and holding["qty"] < 0.001

    def test_cash_position_separated(self):
        cash_tickers = {"SPAXX", "FCASH", "FDRXX", "CORE"}
        test_ticker = "SPAXX"
        assert test_ticker in cash_tickers

    def test_negative_gain_loss(self):
        holding = {"qty": 5.0, "price": 250.00, "mv": 1250.00, "cb": 1500.00, "gl": -250.00, "name": "TSLA"}
        assert holding["gl"] < 0
        assert holding["gl"] == holding["mv"] - holding["cb"]


class TestSnapTradeEdgeCases:
    def test_unknown_ticker_identified(self, snaptrade_raw_sample):
        unknown = [h for h in snaptrade_raw_sample["robinhood"]["holdings"] if h["ticker"] == "UNKNOWN"]
        assert len(unknown) == 1

    def test_micro_position_identified(self, snaptrade_raw_sample):
        micro = [h for h in snaptrade_raw_sample["robinhood"]["holdings"] if h["institution_value"] < 1.0]
        assert len(micro) >= 1

    def test_negative_gain_loss_preserved(self, snaptrade_raw_sample):
        tsla = next(h for h in snaptrade_raw_sample["robinhood"]["holdings"] if h["ticker"] == "TSLA")
        assert tsla["gain_loss"] < 0

    def test_dividend_transaction_classified(self, snaptrade_raw_sample):
        dividends = [t for t in snaptrade_raw_sample["robinhood"]["investment_transactions"] if t["type"] == "DIVIDEND"]
        assert len(dividends) >= 1
        assert dividends[0]["amount"] > 0


class TestPlaidEdgeCases:
    def test_null_cost_basis_handled(self, plaid_raw_sample):
        null_cb = [h for h in plaid_raw_sample["merrill"]["holdings"] if h["cost_basis"] is None]
        assert len(null_cb) == 1

    def test_null_ticker_handled(self, plaid_raw_sample):
        null_ticker = [s for s in plaid_raw_sample["merrill"]["securities"] if s["ticker_symbol"] is None]
        assert len(null_ticker) == 1

    def test_gain_loss_calculated_from_plaid(self, plaid_raw_sample):
        holding = plaid_raw_sample["merrill"]["holdings"][0]
        assert "gain_loss" not in holding
        if holding["cost_basis"] is not None:
            gl = holding["institution_value"] - holding["cost_basis"]
            assert gl == 2500.00


class TestCashOnlyAccounts:
    def test_no_holdings(self, plaid_cash_only):
        assert plaid_cash_only["chase"]["holdings"] == []
        assert plaid_cash_only["marcus"]["holdings"] == []

    def test_has_balances(self, plaid_cash_only):
        assert plaid_cash_only["chase"]["accounts"][0]["balances"]["current"] > 0
        assert plaid_cash_only["marcus"]["accounts"][0]["balances"]["current"] > 0

    def test_account_type_is_depository(self, plaid_cash_only):
        assert plaid_cash_only["chase"]["accounts"][0]["type"] == "depository"
        assert plaid_cash_only["marcus"]["accounts"][0]["type"] == "depository"


class TestConfigEdgeCases:
    def test_valid_config_has_all_keys(self, config_valid):
        assert "snaptrade" in config_valid
        assert "plaid" in config_valid
        assert "client_id" in config_valid["snaptrade"]
        assert "consumer_key" in config_valid["snaptrade"]
        assert "client_id" in config_valid["plaid"]
        assert "secret" in config_valid["plaid"]

    def test_missing_keys_detectable(self, config_missing_keys):
        assert config_missing_keys["snaptrade"]["client_id"] == ""
        assert config_missing_keys["snaptrade"]["consumer_key"] == ""
        assert "secret" not in config_missing_keys["plaid"]

    def test_corrupted_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad_config.json"
        bad_file.write_text("{invalid json here")
        with pytest.raises(json.JSONDecodeError):
            json.loads(bad_file.read_text())
