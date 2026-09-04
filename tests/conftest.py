from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture(autouse=True)
def _no_live_agentmail(monkeypatch) -> None:
    """Tests must never inherit real AgentMail keys from the process environment."""
    monkeypatch.delenv("AGENTMAIL_API_KEY", raising=False)
    monkeypatch.delenv("AGENTMAIL_INBOX", raising=False)
    monkeypatch.delenv("AGENTMAIL_TO", raising=False)
