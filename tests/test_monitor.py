from __future__ import annotations

from datetime import date, time

import pytest

from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.models import Event, Fencer, Tournament
from fencer_schedules.monitor import build_digest, new_names, run

TRICK_ID = "f4fbfddf-8316-46d2-9392-8a8245059f86"


def _settings() -> Settings:
    return Settings(
        club_name="Elite Fencers Club",
        club_aliases=["Elite FC"],
        askfred_api_token="x",
        agentmail_api_key="",
        agentmail_inbox="",
    )


def _fencer(name: str, club: str) -> Fencer:
    return Fencer(name=name, club=club)


def _event(event_id: str, fencers: list[Fencer], clock: time | None = None) -> Event:
    return Event(
        source_event_id=event_id,
        name="Junior Men's Epee",
        day=date(2026, 8, 22),
        clock=clock,
        fencers=fencers,
    )


def _tournament(events: list[Event]) -> Tournament:
    return Tournament(
        askfred_id=TRICK_ID,
        name="Trick or Retreat ROC / RJCC",
        start_date=date(2026, 8, 22),
        end_date=date(2026, 8, 23),
        events=events,
    )


def _seed(store: Store, tournament: Tournament) -> None:
    store.save(tournament, select=False)


# ---- diff logic ----


def test_new_names_returns_only_additions() -> None:
    last = [["Doe, Jordan", "Elite Fencers Club"]]
    current = [
        ["Doe, Jordan", "Elite Fencers Club"],
        ["Smith, James", "Other Club"],
    ]
    assert new_names(last, current) == [["Smith, James", "Other Club"]]


def test_new_names_empty_last_seen_returns_everything() -> None:
    assert new_names([], [["Doe, Jordan", "Elite Fencers Club"]]) == [
        ["Doe, Jordan", "Elite Fencers Club"]
    ]


def test_new_names_same_roster_returns_nothing() -> None:
    current = [["Doe, Jordan", "Elite Fencers Club"]]
    assert new_names(current, current) == []


# ---- digest ----


def test_build_digest_subject_and_body() -> None:
    event = _event("e1", [], clock=time(8, 0))
    subject, body = build_digest(
        _tournament([event]),
        [(event, [["Doe, Jordan", "Elite Fencers Club"], ["Smith, James", "Other Club"]])],
        _settings(),
    )
    assert subject == "New registrants: Trick or Retreat ROC / RJCC (2 new)"
    assert "Saturday, August 22" in body
    assert "8:00 AM" in body
    assert "Junior Men's Epee" in body
    assert "- Doe, Jordan — Elite Fencers Club [CLUB]" in body
    assert "- Smith, James — Other Club" in body
    assert "Event e1" not in body


# ---- run loop ----


def test_first_run_baselines_silently(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    event = _event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])
    _seed(store, _tournament([event]))
    store.set_watch(TRICK_ID, None, "club")

    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", lambda aid, s, **kw: _tournament([event]))
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store)
    assert subjects == []
    assert sent == []
    watch = store.watch_for(TRICK_ID, None, "club")
    assert watch is not None
    assert watch.last_seen == '{"e1": [["Doe, Jordan", "Elite Fencers Club"]]}'


def test_second_run_with_added_fencer_emails(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, None, "club")

    monkeypatch.setattr(
        "fencer_schedules.monitor.load_tournament",
        lambda aid, s, **kw: _tournament(
            [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("Smith, James", "Elite FC")])]
        ),
    )
    store.save_last_seen(store.watch_for(TRICK_ID, None, "club"), {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})

    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store)
    assert len(subjects) == 1
    assert "Trick or Retreat" in subjects[0]
    assert len(sent) == 1
    assert sent[0][3] == ["frankcng@gmail.com"]


def test_club_watch_filters_to_our_club(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, None, "club")

    # EFC is "Elite Fencing Club" — never ours. Nobody new should be reported.
    monkeypatch.setattr(
        "fencer_schedules.monitor.load_tournament",
        lambda aid, s, **kw: _tournament(
            [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("Rival, Rob", "EFC")])]
        ),
    )
    store.save_last_seen(store.watch_for(TRICK_ID, None, "club"), {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})

    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))
    subjects = run(_settings(), store)
    assert subjects == []
    assert sent == []


def test_event_watch_reports_anyone(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, "e1", "all")
    store.save_last_seen(store.watch_for(TRICK_ID, "e1", "all"), {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})

    monkeypatch.setattr(
        "fencer_schedules.monitor.load_tournament",
        lambda aid, s, **kw: _tournament(
            [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("Rival, Rob", "EFC")])]
        ),
    )
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))
    subjects = run(_settings(), store)
    assert len(subjects) == 1
    assert sent and "Junior Men's Epee" in sent[0][2]


def test_failing_load_does_not_kill_run(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, None, "club")

    def _boom(aid, s, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", _boom)
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))
    subjects = run(_settings(), store)
    assert subjects == []
    assert sent == []


def test_dry_run_sends_nothing_and_does_not_write(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, None, "club")

    monkeypatch.setattr(
        "fencer_schedules.monitor.load_tournament",
        lambda aid, s, **kw: _tournament(
            [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("Smith, James", "Elite FC")])]
        ),
    )
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store, dry_run=True)
    assert subjects == []
    assert sent == []
    # last_seen must be untouched (still the default "{}")
    assert store.watch_for(TRICK_ID, None, "club").last_seen == "{}"


def test_recipients_from_settings(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.set_setting("alert_recipient", "frankcng@gmail.com, wife@example.com")
    from fencer_schedules.monitor import recipients_for

    assert recipients_for(store) == ["frankcng@gmail.com", "wife@example.com"]


def test_recipients_default(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    from fencer_schedules.monitor import recipients_for

    assert recipients_for(store) == ["frankcng@gmail.com"]
