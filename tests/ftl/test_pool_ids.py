"""Tests for pool ID extractor parser."""
from pathlib import Path
import pytest
from app.ftl.parsers.pool_ids import parse_pool_ids


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = ROOT / "comms" / "ftl_research_human_pool_ids.md"

SAMPLE_HTML_DUPLICATES = """
<html>
<script>
var ids = [
    "130C4C6606F342AFBD607A193F05FAB1",
    "BAB54F30F50544188F2EA794B021A72B",
    "130C4C6606F342AFBD607A193F05FAB1"
];
var url = "pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7";
</script>
</html>
"""

SAMPLE_HTML_MISSING_IDS = """
<html>
<script>
var foo = "bar";
</script>
</html>
"""

SAMPLE_HTML_EMPTY_ARRAY = """
<html>
<script>
var ids = [];
var url = "pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7";
</script>
</html>
"""

SAMPLE_HTML_LOWERCASE = """
<html>
<script>
var ids = [
    "130c4c6606f342afbd607a193f05fab1",
    "bab54f30f50544188f2ea794b021a72b"
];
var url = "pools/scores/54b9ef9a9707492e93f1d1f46cf715a2/d6890ca440324d9e8d594d5682cc33b7";
</script>
</html>
"""


def _load_sample_html() -> str:
    return SAMPLE_PATH.read_text(encoding="utf-8")


def test_parse_pool_ids_basic():
    """Test basic pool ID extraction from sample HTML."""
    html = _load_sample_html()
    result = parse_pool_ids(html)

    assert result["pool_round_id"] == "D6890CA440324D9E8D594D5682CC33B7"
    assert len(result["pool_ids"]) == 45
    assert "130C4C6606F342AFBD607A193F05FAB1" in result["pool_ids"]
    assert "BAB54F30F50544188F2EA794B021A72B" in result["pool_ids"]


def test_parse_pool_ids_expected_round_id():
    """Test that pool round ID matches the known November NAC value."""
    html = _load_sample_html()
    result = parse_pool_ids(html)
    assert result["pool_round_id"] == "D6890CA440324D9E8D594D5682CC33B7"


def test_parse_pool_ids_deduplication():
    """Test that duplicate pool IDs are removed while preserving order."""
    result = parse_pool_ids(SAMPLE_HTML_DUPLICATES)
    assert len(result["pool_ids"]) == 2
    assert result["pool_ids"][0] == "130C4C6606F342AFBD607A193F05FAB1"
    assert result["pool_ids"][1] == "BAB54F30F50544188F2EA794B021A72B"


def test_parse_pool_ids_normalization_uppercase():
    """Test that pool IDs are normalized to uppercase."""
    result = parse_pool_ids(SAMPLE_HTML_LOWERCASE)
    assert all(pid == pid.upper() for pid in result["pool_ids"])
    assert result["pool_ids"][0] == "130C4C6606F342AFBD607A193F05FAB1"
    assert result["pool_round_id"] == "D6890CA440324D9E8D594D5682CC33B7"


def test_parse_pool_ids_missing_array_raises_error():
    """Test that missing pool IDs array raises ValueError."""
    with pytest.raises(ValueError, match="Could not find pool IDs array"):
        parse_pool_ids(SAMPLE_HTML_MISSING_IDS)


def test_parse_pool_ids_empty_array_raises_error():
    """Test that empty pool IDs array raises ValueError."""
    with pytest.raises(ValueError, match="No pool IDs found"):
        parse_pool_ids(SAMPLE_HTML_EMPTY_ARRAY)


def test_parse_pool_ids_all_ids_present():
    """Test that all expected pool IDs are extracted."""
    html = _load_sample_html()
    result = parse_pool_ids(html)
    expected_ids = [
        "130C4C6606F342AFBD607A193F05FAB1",
        "BAB54F30F50544188F2EA794B021A72B",
        "30877432D1026706D7E805DA846A32C3",
        "BB81E3C29B62179273C8EB5BB682575E",
        "81FB339258E4D27EB0D1CB7C2B70A3A4",
    ]
    for expected in expected_ids:
        assert expected in result["pool_ids"]


def test_parse_pool_ids_return_structure():
    """Test that the return value has the correct structure."""
    html = _load_sample_html()
    result = parse_pool_ids(html)
    assert isinstance(result, dict)
    assert "pool_round_id" in result
    assert "pool_ids" in result
    assert isinstance(result["pool_round_id"], str)
    assert isinstance(result["pool_ids"], list)
    assert all(isinstance(pid, str) for pid in result["pool_ids"])
