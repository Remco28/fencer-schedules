"""Unit tests for API endpoint handlers (call functions directly)."""
import pytest
from unittest.mock import patch

from app.main import (
    get_pools_bundle,
    search_fencer,
    get_de_tableau,
    root,
)
from app.ftl.client import FTLHTTPError, FTLParseError, clear_cache
from app.ftl.parsers import parse_pool_html, parse_pool_results


@pytest.fixture(autouse=True)
def clear_cache_fixture():
    clear_cache()
    yield
    clear_cache()


# Fixtures
POOL_IDS = [
    "130C4C6606F342AFBD607A193F05FAB1",
    "BAB54F30F50544188F2EA794B021A72B",
    "30877432D1026706D7E805DA846A32C3",
]

POOL_HTML = """
<html><body>
<table><tr><td><h4 class="poolNum">Pool #1</h4></td></tr></table>
<span class="poolStripTime">On strip A5</span>
<table class="table table-condensed table-sm table-bordered poolTable">
    <tbody>
        <tr class="poolRow">
            <td>
                <span class="poolCompName">SMITH John</span>
                <br /><span class="poolAffil">ABC Club / USA</span>
            </td>
            <td class="poolPos">1</td>
            <td class="poolScoreFill"></td>
            <td class="poolScore poolScoreV"><span>V5</span></td>
            <td class="poolScore poolScoreD"><span>D2</span></td>
            <td class="poolSep"></td>
            <td class="poolResult">1</td>
            <td class="poolResult">1.00</td>
            <td class="poolResult">5</td>
            <td class="poolResult">2</td>
            <td class="poolResult">+3</td>
        </tr>
        <tr class="poolRow">
            <td>
                <span class="poolCompName">JONES Sarah</span>
                <br /><span class="poolAffil">XYZ Club / USA</span>
            </td>
            <td class="poolPos">2</td>
            <td class="poolScore poolScoreD"><span>D2</span></td>
            <td class="poolScoreFill"></td>
            <td class="poolSep"></td>
            <td class="poolResult">0</td>
            <td class="poolResult">0.00</td>
            <td class="poolResult">2</td>
            <td class="poolResult">5</td>
            <td class="poolResult">-3</td>
        </tr>
    </tbody>
</table>
</body></html>
"""

POOL_RESULTS_JSON = """[
  {
    "id": "425B00719E2740C18ECEC299142D3CF3",
    "v": 6,
    "m": 6,
    "vm": 1.0,
    "ts": 30,
    "tr": 9,
    "ind": 21,
    "prediction": "Advanced",
    "name": "SMITH John",
    "div": "Test Division",
    "country": "USA",
    "club1": "ABC Club",
    "club2": null,
    "search": "smith john|test division|usa|abc club",
    "place": 1,
    "tie": false
  },
  {
    "id": "511E4E00E67041D884F44F6F4EF849B7",
    "v": 4,
    "m": 6,
    "vm": 0.667,
    "ts": 22,
    "tr": 18,
    "ind": 4,
    "prediction": "Eliminated",
    "name": "JONES Sarah",
    "div": "Test Division",
    "country": "USA",
    "club1": "XYZ Club",
    "club2": null,
    "search": "jones sarah|test division|usa|xyz club",
    "place": 125,
    "tie": false
  }
]"""

DE_TABLEAU_HTML = """
<html><body>
<table class='elimTableau w-100'>
    <tr>
        <th>Table of 64</th>
        <th>Table of 32</th>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td class='tbb'>
            <span class='tseed'>(1)&nbsp;</span>
            <span class='tcln'>SMITH</span>
            <span class='tcfn'>John</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td class='tbr tscoref'>
            <span class='tsco'>15 - 8<br/><span class='tref'>Strip A1</span></span>
        </td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td class='tbbr'>
            <span class='tseed'>(64)&nbsp;</span>
            <span class='tcln'>JONES</span>
            <span class='tcfn'>Sarah</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
    </tr>
</table>
</body></html>
"""


PREPARSED_BUNDLE = {
    "event_id": "54B9EF9A9707492E93F1D1F46CF715A2",
    "pool_round_id": "D6890CA440324D9E8D594D5682CC33B7",
    "pool_ids": POOL_IDS,
    "pools": [parse_pool_html(POOL_HTML, pool_id=POOL_IDS[0])],
    "results": parse_pool_results(
        POOL_RESULTS_JSON,
        event_id="54B9EF9A9707492E93F1D1F46CF715A2",
        pool_round_id="D6890CA440324D9E8D594D5682CC33B7",
    ),
}


def test_root_health_check():
    data = root()
    assert data["status"] == "ok"
    assert "service" in data


@patch("app.main.fetch_pools_bundle", return_value=PREPARSED_BUNDLE)
def test_pools_bundle_success(mock_bundle):
    data = get_pools_bundle("54B9EF9A9707492E93F1D1F46CF715A2", "D6890CA440324D9E8D594D5682CC33B7")
    assert data["event_id"] == PREPARSED_BUNDLE["event_id"]
    assert len(data["pool_ids"]) == 3
    assert "fencers" in data["results"]


@patch("app.main.fetch_pools_bundle", side_effect=FTLHTTPError("Connection timeout"))
def test_pools_bundle_http_error(mock_bundle):
    with pytest.raises(Exception):
        get_pools_bundle("event", "round")


@patch("app.main.fetch_pools_bundle", side_effect=FTLParseError("Invalid HTML"))
def test_pools_bundle_parse_error(mock_bundle):
    with pytest.raises(Exception):
        get_pools_bundle("event", "round")


@patch("app.main.fetch_pools_bundle", return_value=PREPARSED_BUNDLE)
def test_fencer_search_success(mock_bundle):
    data = search_fencer("54B9EF9A9707492E93F1D1F46CF715A2", "D6890CA440324D9E8D594D5682CC33B7", "smith")
    assert data["query"] == "smith"
    assert len(data["matches"]) >= 1


@patch("app.main.fetch_pools_bundle", return_value=PREPARSED_BUNDLE)
def test_fencer_search_case_insensitive(mock_bundle):
    for q in ["SMITH", "smith", "Smith"]:
        data = search_fencer("54B9EF9A9707492E93F1D1F46CF715A2", "D6890CA440324D9E8D594D5682CC33B7", q)
        assert len(data["matches"]) > 0


@patch("app.main.fetch_pools_bundle", return_value=PREPARSED_BUNDLE)
def test_fencer_search_multiple_matches(mock_bundle):
    data = search_fencer("54B9EF9A9707492E93F1D1F46CF715A2", "D6890CA440324D9E8D594D5682CC33B7", "o")
    assert len(data["matches"]) >= 2


@patch("app.main.fetch_pools_bundle", return_value=PREPARSED_BUNDLE)
def test_fencer_search_no_matches(mock_bundle):
    data = search_fencer("54B9EF9A9707492E93F1D1F46CF715A2", "D6890CA440324D9E8D594D5682CC33B7", "NONEXISTENT")
    assert data["matches"] == []


@patch("app.main.fetch_tableau_raw", return_value=DE_TABLEAU_HTML)
def test_de_tableau_success(mock_tableau):
    data = get_de_tableau("EVENT123", "DEROUND789")
    assert data["event_id"] == "EVENT123"
    assert data["round_id"] == "DEROUND789"
    assert len(data["matches"]) >= 1


@patch("app.main.fetch_tableau_raw", side_effect=FTLHTTPError("timeout"))
def test_de_tableau_http_error(mock_tableau):
    with pytest.raises(Exception):
        get_de_tableau("EVENT123", "DEROUND789")


@patch("app.main.fetch_tableau_raw", side_effect=FTLParseError("Invalid tableau"))
def test_de_tableau_parse_error(mock_tableau):
    with pytest.raises(Exception):
        get_de_tableau("EVENT123", "DEROUND789")
