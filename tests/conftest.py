from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "legacy"


@pytest.fixture
def etl_log() -> Path:
    return EXAMPLES / "nightly_orders_etl.log"


@pytest.fixture
def churn_sql() -> Path:
    return EXAMPLES / "churn_scores.sql"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests stay offline: any real HTTP call fails loudly."""
    import urllib.request

    def boom(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
