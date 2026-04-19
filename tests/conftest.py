"""Shared pytest fixtures for portfolio pipeline tests."""

import json
import sys
from pathlib import Path

# Add src/ and extractors/ to path so we can import pipeline modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "extractors"))

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def fidelity_sample():
    return json.loads((FIXTURES_DIR / "fidelity_sample.json").read_text())


@pytest.fixture
def snaptrade_raw_sample():
    return json.loads((FIXTURES_DIR / "snaptrade_raw_sample.json").read_text())


@pytest.fixture
def plaid_raw_sample():
    return json.loads((FIXTURES_DIR / "plaid_raw_sample.json").read_text())


@pytest.fixture
def plaid_cash_only():
    return json.loads((FIXTURES_DIR / "plaid_cash_only.json").read_text())


@pytest.fixture
def manual_data_sample():
    return json.loads((FIXTURES_DIR / "manual_data_sample.json").read_text())


@pytest.fixture
def manual_data_empty():
    return {}


@pytest.fixture
def benchmarks_sample():
    return json.loads((FIXTURES_DIR / "benchmarks_sample.json").read_text())


@pytest.fixture
def config_valid():
    return json.loads((FIXTURES_DIR / "config_valid.json").read_text())


@pytest.fixture
def config_missing_keys():
    return json.loads((FIXTURES_DIR / "config_missing_keys.json").read_text())
