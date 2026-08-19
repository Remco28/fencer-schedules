from __future__ import annotations

from datetime import date, datetime

from fencer_schedules.db import Store
from fencer_schedules.models import Tournament


def test_save_and_load(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    t = Tournament(
        askfred_id="abc",
        name="Sample Cup",
        start_date=date(2026, 8, 22),
        end_date=date(2026, 8, 23),
    )
    store.save(t)
    loaded = store.current()
    assert loaded is not None
    assert loaded.name == "Sample Cup"


def test_replace_keeps_one(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.save(Tournament(askfred_id="a", name="A", start_date=date(2026, 9, 1), end_date=date(2026, 9, 1)))
    store.save(Tournament(askfred_id="b", name="B", start_date=date(2026, 9, 2), end_date=date(2026, 9, 2)))
    loaded = store.current()
    assert loaded is not None
    assert loaded.askfred_id == "b"


def test_cleanup_expired(tmp_path) -> None:
    store = Store(tmp_path / "t.db")
    store.save(Tournament(askfred_id="old", name="Old", start_date=date(2026, 1, 1), end_date=date(2026, 1, 2)))
    store.cleanup(now=datetime(2026, 1, 10))
    assert store.current() is None
