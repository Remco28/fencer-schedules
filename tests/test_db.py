from __future__ import annotations

from datetime import date, datetime

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
    store.save(_t("old", "Old", date(2026, 1, 1), date(2026, 1, 2)))
    store.save(_t("keep", "Keep", date(2026, 9, 1)))
    store.cleanup(now=datetime(2026, 1, 10))
    assert {t.askfred_id for t in store.list()} == {"keep"}
    assert store.current().askfred_id == "keep"
