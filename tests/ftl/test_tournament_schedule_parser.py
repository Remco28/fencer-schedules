"""Tests for tournament schedule parser."""
from app.ftl.parsers.tournament_schedule import parse_tournament_schedule


def test_parse_tournament_schedule_basic():
    html = """
    <html>
        <head><title>Sample Tournament</title></head>
        <body>
            <div class="tournName">Sample Tournament Name</div>
            <h5>Jan 15, 2026</h5>
            <table>
                <tr id="ev_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">
                    <td>08:00 AM</td>
                    <td><strong>Senior Men's Epee</strong></td>
                    <td>Completed</td>
                </tr>
                <tr id="ev_BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB">
                    <td>09:30 AM</td>
                    <td><strong>Senior Women's Foil</strong></td>
                    <td>In Progress</td>
                </tr>
            </table>
            <h5>Jan 16, 2026</h5>
            <table>
                <tr id="ev_CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC">
                    <td>10:00 AM</td>
                    <td><strong>Junior Mixed Saber</strong></td>
                    <td>Scheduled</td>
                </tr>
            </table>
        </body>
    </html>
    """

    parsed = parse_tournament_schedule(html)
    assert parsed["tournament_name"] == "Sample Tournament Name"
    assert len(parsed["events"]) == 3

    first = parsed["events"][0]
    assert first["event_id"] == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert first["name"] == "Senior Men's Epee"
    assert first["date"] == "Jan 15, 2026"
    assert first["start_time"] == "08:00 AM"
    assert first["weapon"] == "Epee"
    assert first["status"] == "Completed"

    second = parsed["events"][1]
    assert second["weapon"] == "Foil"

    third = parsed["events"][2]
    assert third["date"] == "Jan 16, 2026"
    assert third["weapon"] == "Saber"


def test_parse_tournament_schedule_weapon_normalization():
    html = """
    <html>
        <body>
            <h5>Jan 15, 2026</h5>
            <table>
                <tr id="ev_DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD">
                    <td>11:00 AM</td>
                    <td><strong>Women's &Eacute;p&eacute;e</strong></td>
                    <td>Scheduled</td>
                </tr>
                <tr id="ev_EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE">
                    <td>12:00 PM</td>
                    <td><strong>Men's Sabre</strong></td>
                    <td>Scheduled</td>
                </tr>
            </table>
        </body>
    </html>
    """

    parsed = parse_tournament_schedule(html)
    weapons = [event["weapon"] for event in parsed["events"]]
    assert weapons == ["Epee", "Saber"]


def test_parse_tournament_schedule_empty_events():
    html = "<html><body><h5>Jan 15, 2026</h5></body></html>"
    parsed = parse_tournament_schedule(html)
    assert parsed["events"] == []
