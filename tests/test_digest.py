from __future__ import annotations

from datetime import date, datetime, time

from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.digest import (
    DIGEST_SENT_ON_KEY,
    build_daily_digest,
    digest_due,
    digest_recipients_for,
    digest_time_for,
    parse_digest_time,
    send_daily_digest,
)
from fencer_schedules.models import Event, EventResult, Fencer, Tournament
from fencer_schedules.notify import SKIPPED

SEVEN_AM = datetime(2026, 8, 22, 7, 0)
AFTERNOON = datetime(2026, 8, 22, 14, 0)


def _settings() -> Settings:
    return Settings(
        club_name="Elite Fencers Club",
        club_aliases=["Elite FC"],
        agentmail_api_key="k",
        agentmail_inbox="inbox@agentmail.to",
    )


def _event(event_id: str, fencers: list[Fencer], clock: time | None = None) -> Event:
    return Event(
        source_event_id=event_id,
        name="Junior Men's Epee",
        day=date(2026, 8, 22),
        clock=clock,
        fencers=fencers,
    )


def _tournament(askfred_id: str = "one", events: list[Event] | None = None) -> Tournament:
    return Tournament(
        askfred_id=askfred_id,
        name="Trick or Retreat ROC / RJCC",
        start_date=date(2026, 8, 22),
        end_date=date(2026, 8, 23),
        venue="Edison, NJ",
        events=events or [],
    )


def test_parse_digest_time() -> None:
    assert parse_digest_time("07:00") == "07:00"
    assert parse_digest_time(" 7am ") is None
    assert parse_digest_time("") is None
    assert parse_digest_time(None) is None


def test_digest_time_defaults_when_unset(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    assert digest_time_for(store) == "07:00"
    store.set_setting("digest_time", "bogus")
    assert digest_time_for(store) == "07:00"


def test_digest_recipients_are_separate_from_alerts(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.set_setting("alert_recipient", "alerts@example.com")
    store.set_setting("digest_recipient", "frankcng@gmail.com, coach@example.com")
    assert digest_recipients_for(store) == ["frankcng@gmail.com", "coach@example.com"]


def test_digest_due_once_per_day(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    assert digest_due(store, SEVEN_AM)
    assert not digest_due(store, AFTERNOON)
    store.set_setting(DIGEST_SENT_ON_KEY, "2026-08-22")
    assert not digest_due(store, SEVEN_AM)
    assert digest_due(store, datetime(2026, 8, 23, 7, 10))


def test_build_digest_lists_tracked_members_and_places() -> None:
    event = _event(
        "e1",
        [Fencer(name="Doe, Jordan", club="Elite Fencers Club"), Fencer(name="Guest, Gil", club="Other Club", source="manual")],
        clock=time(8, 0),
    ).model_copy(update={"results": [EventResult(place="3", name="Doe, Jordan", club="Elite Fencers Club")]})
    subject, body, html = build_daily_digest([_tournament(events=[event])], _settings(), date(2026, 8, 22))
    assert subject == "Club schedule · Saturday, August 22"
    assert "TRICK OR RETREAT" in body
    assert "8:00 AM" in body
    assert "★  Doe, Jordan  (3rd)" in body
    assert "·  Guest, Gil" in body
    assert "Doe, Jordan" in html
    assert "3rd" in html
    assert "&lt;" not in html


def test_build_digest_escapes_html() -> None:
    event = _event("e1", [Fencer(name="O'Brien & Co", club="Club <X>", source="manual")])
    event = event.model_copy(update={"name": "Cadet <Men's> Epee"})
    _, _, html = build_daily_digest(
        [_tournament(events=[event]).model_copy(update={"name": "Cup & <Final>"})],
        _settings(),
        date(2026, 8, 22),
    )
    assert "<Men's>" not in html
    assert "&lt;Men's&gt;" in html
    assert "Cup &amp; &lt;Final&gt;" in html
    assert "O'Brien &amp; Co" in html


def test_build_digest_keeps_a_watched_tournament_with_nobody() -> None:
    _, body, html = build_daily_digest([_tournament()], _settings(), date(2026, 8, 22))
    assert "Nobody signed up yet." in body
    assert "Nobody signed up yet." in html
    assert "Trick or Retreat" in html


def test_nothing_watched_sends_nothing(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_tournament(events=[_event("e1", [Fencer(name="Doe, Jordan", club="Elite Fencers Club")])]))
    sent: list = []
    monkeypatch.setattr("fencer_schedules.digest.send_digest", lambda *a, **kw: sent.append(a) or True)

    assert send_daily_digest(_settings(), store, now=SEVEN_AM) is None
    assert sent == []


def test_scheduled_send_includes_an_empty_watched_tournament(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_tournament())
    store.set_watch("one", None, "club")
    sent: list = []
    monkeypatch.setattr("fencer_schedules.digest.send_digest", lambda *a, **kw: sent.append(a) or True)

    subject = send_daily_digest(_settings(), store, now=SEVEN_AM)

    assert subject is not None
    assert len(sent) == 1
    assert "Nobody signed up yet." in sent[0][2]
    assert store.get_setting(DIGEST_SENT_ON_KEY) == "2026-08-22"


def test_scheduled_send_goes_out_once(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_tournament(events=[_event("e1", [Fencer(name="Doe, Jordan", club="Elite Fencers Club")])]))
    store.set_watch("one", None, "club")
    sent: list = []
    monkeypatch.setattr("fencer_schedules.digest.send_digest", lambda *a, **kw: sent.append(a) or True)

    assert send_daily_digest(_settings(), store, now=SEVEN_AM)
    assert send_daily_digest(_settings(), store, now=datetime(2026, 8, 22, 7, 20)) is None
    assert len(sent) == 1


def test_failed_send_is_not_marked_sent(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_tournament())
    store.set_watch("one", None, "club")
    monkeypatch.setattr("fencer_schedules.digest.send_digest", lambda *a, **kw: SKIPPED)

    assert send_daily_digest(_settings(), store, now=SEVEN_AM) is None
    assert store.get_setting(DIGEST_SENT_ON_KEY) == ""
    assert digest_due(store, SEVEN_AM)


def test_on_demand_ignores_the_window_and_does_not_consume_the_day(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_tournament())
    store.set_watch("one", None, "club")
    sent: list = []
    monkeypatch.setattr("fencer_schedules.digest.send_digest", lambda *a, **kw: sent.append(a) or True)

    assert send_daily_digest(_settings(), store, now=AFTERNOON, force=True)
    assert store.get_setting(DIGEST_SENT_ON_KEY) == ""
    assert send_daily_digest(_settings(), store, now=SEVEN_AM)
    assert len(sent) == 2
