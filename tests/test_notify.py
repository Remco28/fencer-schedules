from __future__ import annotations

from types import SimpleNamespace

from fencer_schedules.config import Settings
from fencer_schedules.notify import send_digest


def _settings() -> Settings:
    return Settings(
        club_name="Elite Fencers Club",
        club_aliases=["Elite FC"],
        askfred_api_token="x",
        agentmail_api_key="k",
        agentmail_inbox="chunkymonkey@agentmail.to",
    )


class _Inbox:
    inbox_id = "in_123"
    address = "chunkymonkey@agentmail.to"


class _Messages:
    def __init__(self, calls: list) -> None:
        self._calls = calls

    def send(self, inbox_id, to, subject, text):
        self._calls.append({"inbox_id": inbox_id, "to": to, "subject": subject, "text": text})
        return SimpleNamespace(message_id="m_1")


class _Inboxes:
    def __init__(self, calls: list) -> None:
        self._messages = _Messages(calls)

    def list(self):
        return SimpleNamespace(inboxes=[_Inbox()])

    @property
    def messages(self):
        return self._messages


class _Client:
    def __init__(self, api_key: str, calls: list) -> None:
        self._calls = calls
        self.inboxes = _Inboxes(calls)


def test_send_digest_calls_sdk(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr("agentmail.AgentMail", lambda api_key: _Client(api_key, calls))
    send_digest(_settings(), "Subject", "Body", ["frankcng@gmail.com", "wife@example.com"])
    assert len(calls) == 1
    assert calls[0]["inbox_id"] == "in_123"
    assert calls[0]["to"] == ["frankcng@gmail.com", "wife@example.com"]
    assert calls[0]["subject"] == "Subject"
    assert calls[0]["text"] == "Body"


def test_send_digest_send_false_never_calls(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr("agentmail.AgentMail", lambda api_key: _Client(api_key, calls))
    send_digest(_settings(), "Subject", "Body", ["frankcng@gmail.com"], send=False)
    assert calls == []


def test_send_digest_no_recipients_skips(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr("agentmail.AgentMail", lambda api_key: _Client(api_key, calls))
    send_digest(_settings(), "Subject", "Body", ["", "  "])
    assert calls == []


def test_send_digest_missing_config_skips(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr("agentmail.AgentMail", lambda api_key: _Client(api_key, calls))
    settings = _settings().model_copy(update={"agentmail_api_key": ""})
    send_digest(settings, "Subject", "Body", ["frankcng@gmail.com"])
    assert calls == []
