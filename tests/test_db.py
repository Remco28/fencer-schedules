from __future__ import annotations

from datetime import date, datetime, timedelta

from fencer_schedules.db import Store
from fencer_schedules.models import Tournament


def _t(askfred_id: str, name: str, start: date, end: date | None = None) -> Tournament:
    return Tournament(
        askfred_id=askfred_id,
        name=name,
        start_date=start,
        end_date=end or start,
    )


def test_save_and_load(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_t("abc", "Sample Cup", date(2026, 8, 22), date(2026, 8, 23)))
    loaded = store.current()
    assert loaded is not None
    assert loaded.name == "Sample Cup"


def test_keeps_multiple_and_selects_latest_save(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_t("a", "A", date(2026, 9, 1)))
    store.save(_t("b", "B", date(2026, 9, 2)))
    assert store.current().askfred_id == "b"
    assert {t.askfred_id for t in store.list()} == {"a", "b"}
    store.select("a")
    assert store.current().askfred_id == "a"


def test_remove_keeps_the_other(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.save(_t("a", "A", date(2026, 9, 1)))
    store.save(_t("b", "B", date(2026, 9, 2)))
    store.remove("b")
    assert store.current().askfred_id == "a"
    assert [t.askfred_id for t in store.list()] == ["a"]


def test_cleanup_expired(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    now = datetime(2026, 1, 10)
    store.save(_t("old", "Old", date(2026, 1, 1), date(2026, 1, 2)), now=now - timedelta(hours=49))
    store.save(_t("keep", "Keep", date(2026, 9, 1)), now=now)
    store.cleanup(now=now)
    assert {t.askfred_id for t in store.list(now=now)} == {"keep"}
    assert store.current(now=now).askfred_id == "keep"


def test_watch_upsert_and_toggle(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    assert store.watch_for("abc", None, "club") is None
    store.set_watch("abc", None, "club")
    assert store.watch_for("abc", None, "club") is not None
    # idempotent
    store.set_watch("abc", None, "club")
    assert len(store.watches()) == 1
    store.delete_watch("abc", None, "club")
    assert store.watch_for("abc", None, "club") is None


def test_watch_distinct_by_event_and_kind(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.set_watch("abc", None, "club")
    store.set_watch("abc", "e1", "all")
    assert len(store.watches()) == 2
    store.delete_watches("abc")
    assert store.watches() == []


def test_save_and_load_last_seen(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    watch = store.set_watch("abc", None, "club")
    store.save_last_seen(watch, {"e1": [["Doe, Jordan", "Elite Fencers Club"]]})
    reloaded = store.watch_for("abc", None, "club")
    assert reloaded.last_seen == '{"e1": [["Doe, Jordan", "Elite Fencers Club"]]}'


def test_app_settings_get_set(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    assert store.get_setting("alert_recipient", "default@example.com") == "default@example.com"
    store.set_setting("alert_recipient", "frankcng@gmail.com")
    assert store.get_setting("alert_recipient") == "frankcng@gmail.com"
