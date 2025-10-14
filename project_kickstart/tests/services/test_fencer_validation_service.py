"""Tests for fencer validation service."""

import pytest
from app.services import fencer_validation_service


def test_validate_fencer_id_valid():
    """Test validation of valid fencer IDs."""
    is_valid, error = fencer_validation_service.validate_fencer_id("12345")
    assert is_valid is True
    assert error is None

    is_valid, error = fencer_validation_service.validate_fencer_id("99999999")
    assert is_valid is True
    assert error is None


def test_validate_fencer_id_invalid():
    """Test validation of invalid fencer IDs."""
    # Empty string
    is_valid, error = fencer_validation_service.validate_fencer_id("")
    assert is_valid is False
    assert "cannot be empty" in error

    # Non-numeric
    is_valid, error = fencer_validation_service.validate_fencer_id("abc123")
    assert is_valid is False
    assert "must be numeric" in error

    # Contains spaces
    is_valid, error = fencer_validation_service.validate_fencer_id("123 456")
    assert is_valid is False
    assert "must be numeric" in error


def test_normalize_tracked_fencer_id_numeric():
    """Numeric input passes through the normalization helper."""
    normalized, error = fencer_validation_service.normalize_tracked_fencer_id("24680")
    assert normalized == "24680"
    assert error is None

    normalized, error = fencer_validation_service.normalize_tracked_fencer_id(" 13579 ")
    assert normalized == "13579"
    assert error is None


@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("https://www.fencingtracker.com/p/12345", "12345"),
        ("https://fencingtracker.com/p/22222/profile-slug", "22222"),
        ("HTTP://fencingtracker.com/p/33333/", "33333"),
        ("www.fencingtracker.com/p/44444", "44444"),
        ("/p/55555/someone", "55555"),
        ("https://fencingtracker.com/p/66666?tab=events", "66666"),
        ("https://www.fencingtracker.com/p/77777#results", "77777"),
        ("https://www.fencingtracker.com/p/88888/?ref=calendar", "88888"),
        ("https://www.fencingtracker.com/p/99999/slug-one/extra", "99999"),
    ],
)
def test_normalize_tracked_fencer_id_profile_urls(input_value, expected):
    """Profile URL variants normalize to the numeric ID."""
    normalized, error = fencer_validation_service.normalize_tracked_fencer_id(input_value)
    assert normalized == expected
    assert error is None


@pytest.mark.parametrize(
    "input_value,expected_error",
    [
        ("https://www.fencingtracker.com/p/not-a-number", "Could not find a numeric ID"),
        ("fencingtracker.com/profile/12345", "Could not find a numeric ID"),
        ("/profiles/99999", "Could not find a numeric ID"),
    ],
)
def test_normalize_tracked_fencer_id_invalid_urls(input_value, expected_error):
    """Invalid profile URLs surface a clear parsing error."""
    normalized, error = fencer_validation_service.normalize_tracked_fencer_id(input_value)
    assert normalized is None
    assert error is not None
    assert expected_error in error


def test_normalize_tracked_fencer_id_invalid_string():
    """Non-numeric strings that are not URLs return the numeric error."""
    normalized, error = fencer_validation_service.normalize_tracked_fencer_id("abc123")
    assert normalized is None
    assert error == "Fencer ID must be numeric"


def test_normalize_tracked_fencer_id_empty():
    """Empty input retains the existing empty validation error."""
    normalized, error = fencer_validation_service.normalize_tracked_fencer_id("")
    assert normalized is None
    assert error == "Fencer ID cannot be empty"


def test_extract_profile_slug_variants():
    """Slug extraction handles slugged, slugless, and extra segments."""
    assert (
        fencer_validation_service.extract_profile_slug(
            "https://www.fencingtracker.com/p/12345/emma-jones"
        )
        == "emma-jones"
    )
    assert (
        fencer_validation_service.extract_profile_slug("https://fencingtracker.com/p/24680")
        is None
    )
    assert (
        fencer_validation_service.extract_profile_slug("/p/13579/ryan-lee/additional")
        == "ryan-lee"
    )


@pytest.mark.parametrize(
    "slug,expected",
    [
        ("samantha-o-connor", "Samantha O Connor"),
        ("jamie_o'neil", "Jamie O'Neil"),
        ("  alex-smith  ", "Alex Smith"),
        ("", None),
        (None, None),
    ],
)
def test_derive_display_name_from_slug(slug, expected):
    """Slug-to-name conversion produces human-friendly values."""
    assert fencer_validation_service.derive_display_name_from_slug(slug) == expected


def test_normalize_weapon_filter_valid():
    """Test normalization of valid weapon filters."""
    # Single weapon
    result = fencer_validation_service.normalize_weapon_filter("foil")
    assert result == "foil"

    # Multiple weapons
    result = fencer_validation_service.normalize_weapon_filter("foil,epee")
    assert result == "epee,foil"  # Sorted

    # All three weapons
    result = fencer_validation_service.normalize_weapon_filter("saber,foil,epee")
    assert result == "epee,foil,saber"  # Sorted

    # Case insensitive
    result = fencer_validation_service.normalize_weapon_filter("FOIL,Epee")
    assert result == "epee,foil"

    # Extra whitespace
    result = fencer_validation_service.normalize_weapon_filter(" foil , epee ")
    assert result == "epee,foil"


def test_normalize_weapon_filter_deduplication():
    """Test that weapon filter normalization deduplicates entries."""
    # Duplicate weapons should be deduplicated
    result = fencer_validation_service.normalize_weapon_filter("foil,foil")
    assert result == "foil"

    # Case-insensitive deduplication
    result = fencer_validation_service.normalize_weapon_filter("Foil,foil,FOIL")
    assert result == "foil"

    # Multiple duplicates
    result = fencer_validation_service.normalize_weapon_filter("foil,epee,foil,epee")
    assert result == "epee,foil"


def test_normalize_weapon_filter_invalid():
    """Test normalization of invalid weapon filters."""
    # None returns None
    result = fencer_validation_service.normalize_weapon_filter(None)
    assert result is None

    # Empty string returns None
    result = fencer_validation_service.normalize_weapon_filter("")
    assert result is None

    # Invalid weapon name returns None
    result = fencer_validation_service.normalize_weapon_filter("sword")
    assert result is None

    # Mix of valid and invalid (invalid ones filtered out)
    result = fencer_validation_service.normalize_weapon_filter("foil,sword,epee")
    assert result == "epee,foil"

    # Only invalid weapons
    result = fencer_validation_service.normalize_weapon_filter("sword,dagger")
    assert result is None


def test_build_fencer_profile_url():
    """Test building fencer profile URLs."""
    url = fencer_validation_service.build_fencer_profile_url("12345")
    assert url == "https://www.fencingtracker.com/p/12345"

    # With optional name_slug (not used in URL construction)
    url = fencer_validation_service.build_fencer_profile_url("67890", "john-doe")
    assert url == "https://www.fencingtracker.com/p/67890"

def test_normalize_weapon_filter_edge_cases():
    """Test edge cases for weapon filter normalization."""
    # Extra commas
    result = fencer_validation_service.normalize_weapon_filter(",foil,,epee,")
    assert result == "epee,foil"

    # Mixed whitespace and commas
    result = fencer_validation_service.normalize_weapon_filter("  foil  ,  , saber ")
    assert result == "foil,saber"

    # All whitespace and commas
    result = fencer_validation_service.normalize_weapon_filter("  ,   ,  ")
    assert result is None
