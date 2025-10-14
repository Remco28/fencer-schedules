import pytest

from app import main


class TestParseClubUrls:
    def test_returns_empty_list_for_blank_string(self):
        assert main._parse_club_urls("") == []

    def test_splits_and_trims_urls(self):
        raw = " https://example.com/one ,https://example.com/two ,, "
        assert main._parse_club_urls(raw) == [
            "https://example.com/one",
            "https://example.com/two",
        ]


class TestResolveInterval:
    def test_uses_fallback_when_value_missing(self):
        assert main._resolve_interval(None, 30) == 30

    def test_parses_positive_integer(self):
        assert main._resolve_interval("45", 30) == 45

    @pytest.mark.parametrize("value", ["0", "-5"])
    def test_rejects_non_positive_values(self, value):
        with pytest.raises(ValueError):
            main._resolve_interval(value, 30)

    def test_rejects_non_integer_values(self):
        with pytest.raises(ValueError):
            main._resolve_interval("abc", 30)
