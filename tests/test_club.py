from fencer_schedules.club import is_our_club
from fencer_schedules.config import Settings


def _settings() -> Settings:
    return Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"])


def test_matches_elite_fencers_club() -> None:
    assert is_our_club("Elite Fencers Club", _settings())


def test_matches_elite_fc() -> None:
    assert is_our_club("Elite FC", _settings())


def test_rejects_efc_abbreviation() -> None:
    assert not is_our_club("EFC", _settings())


def test_rejects_elite_fencing_club() -> None:
    assert not is_our_club("Elite Fencing Club", _settings())


def test_rejects_elite_fencing_academy() -> None:
    assert not is_our_club("Elite Fencing Academy", _settings())
