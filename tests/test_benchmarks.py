"""Tests for benchmark YTD return calculation."""

import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


def test_benchmark_ytd_return_positive():
    """10% gain: (110 / 100) - 1 = 0.10"""
    import daily_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 105.0, 98.0, 110.0]},
        index=pd.date_range("2026-01-02", periods=4),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    assert "S&P 500" in result
    assert abs(result["S&P 500"] - 0.10) < 0.0001


def test_benchmark_ytd_return_negative():
    """5% loss: (95 / 100) - 1 = -0.05"""
    import daily_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 90.0, 95.0]},
        index=pd.date_range("2026-01-02", periods=3),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    assert result["S&P 500"] == pytest.approx(-0.05, abs=0.0001)


def test_benchmark_flat_return():
    """0% return when first_close == last_close."""
    import daily_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 110.0, 100.0]},
        index=pd.date_range("2026-01-02", periods=3),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    assert result["S&P 500"] == pytest.approx(0.0, abs=0.0001)


def test_benchmark_empty_dataframe_skipped():
    """Empty DataFrame should skip the ticker, not crash."""
    import daily_pipeline

    empty_df = pd.DataFrame()

    with patch("yfinance.download", return_value=empty_df):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    assert result == {} or all(v is not None for v in result.values())


def test_benchmark_network_error_handled():
    """Network error should be caught, not crash the pipeline."""
    import daily_pipeline

    with patch("yfinance.download", side_effect=Exception("Connection timeout")):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    assert isinstance(result, dict)


def test_benchmark_all_three_indices_present():
    """All three benchmarks should be populated when data is available."""
    import daily_pipeline

    mock_data = pd.DataFrame(
        {"Close": [100.0, 110.0]},
        index=pd.date_range("2026-01-02", periods=2),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    assert "S&P 500" in result
    assert "Dow Jones" in result
    assert "NASDAQ" in result


def test_benchmark_return_rounded_to_6_decimals():
    """Returns should be rounded to 6 decimal places."""
    import daily_pipeline

    mock_data = pd.DataFrame(
        {"Close": [300.0, 400.0]},
        index=pd.date_range("2026-01-02", periods=2),
    )

    with patch("yfinance.download", return_value=mock_data):
        result = daily_pipeline.fetch_benchmarks(year=2026)

    for val in result.values():
        assert val == round(val, 6)
