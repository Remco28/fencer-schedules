from __future__ import annotations

from datetime import date, datetime, time

from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.models import Event, EventResult, Fencer, Tournament
from fencer_schedules.monitor import (
    alert_times_for,
    build_digest,
    is_check_hour,
    new_names,
    normalize_alert_times,
    parse_alert_times,
    run,
)

NINE_AM = datetime(2026, 8, 22, 9, 0)

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
    tournament = _tournament([event])
    subject, body, html = build_digest(
        tournament,
        [(event, [["Doe, Jordan", "Elite Fencers Club"], ["Smith, James", "Other Club"]])],
        _settings(),
    )
    assert subject == "2 new registrants · Trick or Retreat ROC / RJCC"
    assert "SATURDAY, AUGUST 22" in body
    assert "8:00 AM" in body
    assert "Junior Men's Epee" in body
    assert "★  Doe, Jordan" in body
    assert "Elite Fencers Club" in body
    assert "·  Smith, James" in body
    assert "Other Club" in body
    assert "[CLUB]" not in body
    assert "Event e1" not in body
    assert "Elite Fencers Club" in html
    assert "★" in html
    assert "Open on AskFRED" in html
    assert "Doe, Jordan" in html
    assert html.startswith("<div")


def test_build_digest_escapes_html() -> None:
    event = _event("e1", [], clock=time(8, 0))
    event = event.model_copy(update={"name": "Cadet <Men's> Epee"})
    _, _, html = build_digest(
        _tournament([event]),
        [(event, [["O'Brien & Co", "Club <X>"]])],
        _settings(),
    )
    assert "<Men's>" not in html
    assert "&lt;Men's&gt;" in html
    assert "O'Brien &amp; Co" in html
    assert "Club &lt;X&gt;" in html


# ---- run loop ----


def test_first_run_baselines_silently(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    event = _event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])
    _seed(store, _tournament([event]))
    store.set_watch(TRICK_ID, None, "club")

    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", lambda aid, s, **kw: _tournament([event]))
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store, now=NINE_AM)
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

    subjects = run(_settings(), store, now=NINE_AM)
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
    subjects = run(_settings(), store, now=NINE_AM)
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
    subjects = run(_settings(), store, now=NINE_AM)
    assert len(subjects) == 1
    assert sent and "Junior Men's Epee" in sent[0][2]


def test_overlapping_watches_send_one_digest_per_tournament(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    current = _tournament(
        [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("Smith, James", "Elite FC")])]
    )
    _seed(store, current)
    club_watch = store.set_watch(TRICK_ID, None, "club")
    event_watch = store.set_watch(TRICK_ID, "e1", "all")
    baseline = {"e1": [["Doe, Jordan", "Elite Fencers Club"]]}
    store.save_last_seen(club_watch, baseline)
    store.save_last_seen(event_watch, baseline)

    loads: list[str] = []
    monkeypatch.setattr(
        "fencer_schedules.monitor.load_tournament",
        lambda aid, s, **kw: loads.append(aid) or current,
    )
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store, now=NINE_AM)

    assert len(loads) == 1
    assert len(subjects) == 1
    assert len(sent) == 1
    assert sent[0][1] == "1 new registrant · Trick or Retreat ROC / RJCC"
    assert sent[0][2].count("Smith, James") == 1
    assert store.watch_for(TRICK_ID, None, "club").last_seen == '{"e1": [["Doe, Jordan", "Elite Fencers Club"], ["Smith, James", "Elite FC"]]}'
    assert store.watch_for(TRICK_ID, "e1", "all").last_seen == '{"e1": [["Doe, Jordan", "Elite Fencers Club"], ["Smith, James", "Elite FC"]]}'


def test_failing_load_does_not_kill_run(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, None, "club")

    def _boom(aid, s, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", _boom)
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))
    subjects = run(_settings(), store, now=NINE_AM)
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


# ---- alert times ----


def test_parse_alert_times_valid_sorted_deduped() -> None:
    assert parse_alert_times("21:00, 09:00,09:00") == ["09:00", "21:00"]
    assert parse_alert_times("07:30") == ["07:30"]


def test_parse_alert_times_drops_invalid() -> None:
    assert parse_alert_times("9am, 25:00, , 12:60") == []
    assert parse_alert_times("") == []
    assert parse_alert_times(None) == []
    assert parse_alert_times("09:00, bogus, 18:15") == ["09:00", "18:15"]


def test_normalize_alert_times_from_form_list() -> None:
    assert normalize_alert_times(["21:00", "09:00"]) == "09:00,21:00"
    assert normalize_alert_times(["07:30, 19:00"]) == "07:30,19:00"
    assert normalize_alert_times(["", "bogus"]) == ""
    assert normalize_alert_times([]) == ""


def test_alert_times_default_when_unset(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    assert alert_times_for(store) == ["09:00", "21:00"]


def test_alert_times_default_when_invalid(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.set_setting("alert_times", "bogus, ,")
    assert alert_times_for(store) == ["09:00", "21:00"]


def test_alert_times_save_roundtrip(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.set_setting("alert_times", normalize_alert_times(["19:00", "07:30"]))
    assert store.get_setting("alert_times") == "07:30,19:00"
    assert alert_times_for(store) == ["07:30", "19:00"]


def test_is_check_hour_boundaries() -> None:
    assert is_check_hour(datetime(2026, 8, 22, 9, 0), ["09:00"])
    assert is_check_hour(datetime(2026, 8, 22, 8, 30), ["09:00"])
    assert is_check_hour(datetime(2026, 8, 22, 9, 30), ["09:00"])
    assert not is_check_hour(datetime(2026, 8, 22, 8, 29), ["09:00"])
    assert not is_check_hour(datetime(2026, 8, 22, 9, 31), ["09:00"])


def test_is_check_hour_midnight_wrap() -> None:
    assert is_check_hour(datetime(2026, 8, 22, 23, 50), ["00:10"])
    assert is_check_hour(datetime(2026, 8, 22, 0, 20), ["00:10"])
    assert not is_check_hour(datetime(2026, 8, 22, 1, 0), ["00:10"])


def _seed_watched(store: Store) -> None:
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    store.set_watch(TRICK_ID, None, "club")
    store.save_last_seen(store.watch_for(TRICK_ID, None, "club"), {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})


def _fresh_with_newcomer(aid, s, **kw):
    return _tournament(
        [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("Smith, James", "Elite FC")])]
    )


def test_run_skips_when_not_check_hour(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed_watched(store)

    def _boom(aid, s, **kw):
        raise AssertionError("load_tournament must not be called outside check hours")

    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", _boom)
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store, now=datetime(2026, 8, 22, 14, 0))
    assert subjects == []
    assert sent == []
    # last_seen untouched
    assert store.watch_for(TRICK_ID, None, "club").last_seen == '{"e1": [["Doe, Jordan", "Elite Fencers Club"]]}'


def test_run_runs_within_window(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed_watched(store)
    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", _fresh_with_newcomer)
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store, now=datetime(2026, 8, 22, 9, 10))
    assert len(subjects) == 1
    assert len(sent) == 1


def test_run_uses_saved_times(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "t.db")
    _seed_watched(store)
    store.set_setting("alert_times", "07:30")
    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", _fresh_with_newcomer)
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    assert run(_settings(), store, now=datetime(2026, 8, 22, 9, 0)) == []
    assert sent == []
    assert len(run(_settings(), store, now=datetime(2026, 8, 22, 7, 40))) == 1
    assert len(sent) == 1


def test_dry_run_ignores_check_window(tmp_path, monkeypatch, capsys) -> None:
    store = Store(tmp_path / "t.db")
    _seed_watched(store)
    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", _fresh_with_newcomer)
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    # 14:00 is outside the default 09:00/21:00 windows, but dry-run evaluates.
    run(_settings(), store, dry_run=True, now=datetime(2026, 8, 22, 14, 0))
    assert sent == []
    out = capsys.readouterr().out
    assert "new registrant" in out


# ---- watcher persistence, failure isolation, and baseline safety ----


def _tournament_as(askfred_id: str, events: list[Event]) -> Tournament:
    return _tournament(events).model_copy(update={"askfred_id": askfred_id})


def _watch_with_baseline(store: Store, askfred_id: str, baseline: dict) -> None:
    store.set_watch(askfred_id, None, "club")
    store.save_last_seen(store.watch_for(askfred_id, None, "club"), baseline)


def test_send_failure_does_not_stop_the_rest_of_the_run(tmp_path, monkeypatch) -> None:
    """One bad email must not blackhole the other watched tournaments."""
    store = Store(tmp_path / "t.db")
    for askfred_id in ("aa", "bb"):
        _seed(store, _tournament_as(askfred_id, [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
        _watch_with_baseline(store, askfred_id, {"e1": []})

    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", lambda aid, s, **kw: store.get(aid))
    attempted: list[str] = []

    def _send(settings, subject, body, recipients, **kwargs):
        attempted.append(subject)
        if len(attempted) == 1:
            raise RuntimeError("AgentMail 500")
        return True

    monkeypatch.setattr("fencer_schedules.monitor.send_digest", _send)

    subjects = run(_settings(), store, now=NINE_AM)

    assert len(attempted) == 2, "the second tournament should still be attempted"
    assert len(subjects) == 1
    baselines = {aid: store.watch_for(aid, None, "club").last_seen for aid in ("aa", "bb")}
    assert list(baselines.values()).count('{"e1": []}') == 1  # only the failed one held back


def test_watcher_persists_the_roster_it_fetched(tmp_path, monkeypatch) -> None:
    """The roster the watcher already paid for should reach the app's pages."""
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    _watch_with_baseline(store, TRICK_ID, {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})
    fresh = _tournament(
        [_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club"), _fencer("New, Nina", "Elite FC")])]
    )
    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", lambda aid, s, **kw: fresh)
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: True)

    run(_settings(), store, now=NINE_AM)

    stored = store.get(TRICK_ID)
    assert stored is not None
    assert "New, Nina" in [f.name for e in stored.events for f in e.fencers]


def test_watcher_keeps_tracking_choices_and_cached_results(tmp_path, monkeypatch) -> None:
    """Persisting a fetch must not wipe manual tracking or cached results."""
    store = Store(tmp_path / "t.db")
    old_event = _event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")]).model_copy(
        update={
            "fencers": [
                _fencer("Doe, Jordan", "Elite Fencers Club"),
                Fencer(name="Guest, Gil", club="Other Club", source="manual"),
            ],
            "results": [EventResult(place="8", name="Doe, Jordan", club="Elite Fencers Club")],
        }
    )
    _seed(store, _tournament([old_event]))
    _watch_with_baseline(store, TRICK_ID, {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})
    monkeypatch.setattr(
        "fencer_schedules.monitor.load_tournament",
        lambda aid, s, **kw: _tournament(
            [
                _event(
                    "e1",
                    [
                        _fencer("Doe, Jordan", "Elite Fencers Club"),
                        _fencer("Guest, Gil", "Other Club"),
                    ],
                )
            ]
        ),
    )
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: True)
    # A different tournament is open on the phone; the watcher must leave it be.
    store.save(_tournament_as("open-in-app", [_event("e9", [])]), select=True)

    run(_settings(), store, now=NINE_AM)

    stored = store.get(TRICK_ID)
    assert stored is not None
    event = stored.events[0]
    assert event.results is not None, "cached final results must survive"
    guest = next(f for f in event.fencers if f.name == "Guest, Gil")
    assert guest.source == "manual", "manual tracking must survive"
    current = store.current()
    assert current is not None
    assert current.askfred_id == "open-in-app", "the open tournament must not change"


def test_hidden_fencer_is_not_reported(tmp_path, monkeypatch) -> None:
    """Untracking someone should silence alerts about them too."""
    store = Store(tmp_path / "t.db")
    hidden = _event("e1", []).model_copy(
        update={"fencers": [Fencer(name="Hidden, Hana", club="Elite Fencers Club", source="hidden")]}
    )
    _seed(store, _tournament([hidden]))
    _watch_with_baseline(store, TRICK_ID, {"e1": []})
    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", lambda aid, s, **kw: store.get(aid))
    sent: list = []
    monkeypatch.setattr("fencer_schedules.monitor.send_digest", lambda *a, **kw: sent.append(a))

    subjects = run(_settings(), store, now=NINE_AM)

    assert subjects == []
    assert sent == []


def test_unsent_digest_keeps_the_baseline(tmp_path, monkeypatch) -> None:
    """With AgentMail unconfigured nothing is delivered, so nothing is consumed."""
    store = Store(tmp_path / "t.db")
    _seed(store, _tournament([_event("e1", [_fencer("Doe, Jordan", "Elite Fencers Club")])]))
    _watch_with_baseline(store, TRICK_ID, {"e1": []})
    monkeypatch.setattr("fencer_schedules.monitor.load_tournament", lambda aid, s, **kw: store.get(aid))
    unconfigured = Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])

    subjects = run(unconfigured, store, now=NINE_AM)

    assert subjects == []
    assert store.watch_for(TRICK_ID, None, "club").last_seen == '{"e1": []}'
