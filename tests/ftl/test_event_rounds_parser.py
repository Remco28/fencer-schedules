"""Tests for event rounds parser."""
from app.ftl.parsers.event_rounds import parse_event_rounds


def test_parse_event_rounds_with_both_links():
    html = """
    <html>
        <body>
            <a href="/pools/scores/EVT/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">Pools</a>
            <a href="/tableaus/scores/EVT/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB">DE</a>
        </body>
    </html>
    """
    parsed = parse_event_rounds(html)
    assert parsed["pool_round_id"] == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert parsed["de_round_id"] == "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"


def test_parse_event_rounds_missing_pool_link():
    html = """
    <html>
        <body>
            <a href="/tableaus/scores/EVT/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB">DE</a>
        </body>
    </html>
    """
    parsed = parse_event_rounds(html)
    assert parsed["pool_round_id"] is None
    assert parsed["de_round_id"] == "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"


def test_parse_event_rounds_missing_de_link():
    html = """
    <html>
        <body>
            <a href="/pools/scores/EVT/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">Pools</a>
        </body>
    </html>
    """
    parsed = parse_event_rounds(html)
    assert parsed["pool_round_id"] == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert parsed["de_round_id"] is None


def test_parse_event_rounds_empty_html():
    html = "<html><body></body></html>"
    parsed = parse_event_rounds(html)
    assert parsed["pool_round_id"] is None
    assert parsed["de_round_id"] is None
