from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from app.services import fencer_scraper_service as scraper_service


class DummyResponse:
    def __init__(self, status_code: int, content: str, reason: str = "OK"):
        self.status_code = status_code
        self.content = content.encode("utf-8")
        self.reason = reason


class DummySession:
    def __init__(self, responses):
        self._responses = responses
        self._index = 0

    def get(self, *args, **kwargs):
        response = self._responses[self._index]
        self._index = min(self._index + 1, len(self._responses) - 1)
        return response


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.flush = MagicMock()
    return db


def test_scrape_all_tracked_fencers_skips_when_hash_matches(monkeypatch, mock_db):
    html = """
    <html>
      <body>
        <table>
          <tr><th>Tournament</th><th>Event</th><th>Date</th></tr>
          <tr><td>Autumn Open</td><td>Senior Men's Foil</td><td>2025-10-01</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    cached_hash = scraper_service._compute_registration_hash(soup.find_all("table"))

    tracked = SimpleNamespace(
        fencer_id="12345",
        display_name="Cached Fencer",
        last_registration_hash=cached_hash,
        failure_count=0,
        last_failure_at=None,
    )

    monkeypatch.setattr(
        scraper_service.requests,
        "Session",
        lambda: DummySession([DummyResponse(200, html)]),
    )
    monkeypatch.setattr(scraper_service, "get_all_active_tracked_fencers", lambda db: [tracked])
    get_fencer_mock = MagicMock()
    monkeypatch.setattr(scraper_service, "get_fencer_by_fencingtracker_id", get_fencer_mock)
    create_fencer_mock = MagicMock()
    monkeypatch.setattr(scraper_service, "get_or_create_fencer", create_fencer_mock)
    create_tournament_mock = MagicMock()
    monkeypatch.setattr(scraper_service, "get_or_create_tournament", create_tournament_mock)
    update_registration_mock = MagicMock()
    monkeypatch.setattr(scraper_service, "update_or_create_registration", update_registration_mock)
    update_status = MagicMock()
    monkeypatch.setattr(scraper_service, "update_fencer_check_status", update_status)

    result = scraper_service.scrape_all_tracked_fencers(mock_db)

    assert result["fencers_scraped"] == 1
    assert result["total_registrations"] == 0
    update_status.assert_called_once()
    get_fencer_mock.assert_not_called()
    create_fencer_mock.assert_not_called()
    create_tournament_mock.assert_not_called()
    update_registration_mock.assert_not_called()
    assert tracked.last_registration_hash == cached_hash


def test_scrape_all_tracked_fencers_applies_delay_between_requests(monkeypatch, mock_db):
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(scraper_service.time, "sleep", fake_sleep)
    monkeypatch.setattr(scraper_service.random, "uniform", lambda a, b: 0)

    tracked_fencers = [
        SimpleNamespace(
            fencer_id="1",
            display_name="First",
            last_registration_hash=None,
            failure_count=0,
            last_failure_at=None,
        ),
        SimpleNamespace(
            fencer_id="2",
            display_name="Second",
            last_registration_hash=None,
            failure_count=0,
            last_failure_at=None,
        ),
    ]

    monkeypatch.setattr(scraper_service, "get_all_active_tracked_fencers", lambda db: tracked_fencers)

    def fake_scrape(db, fencer_id, display_name, cached_hash=None):
        return {"new": 0, "updated": 0, "total": 0, "hash": "next", "skipped": False}

    monkeypatch.setattr(scraper_service, "scrape_fencer_profile", fake_scrape)
    monkeypatch.setattr(scraper_service, "update_fencer_check_status", lambda *args, **kwargs: None)

    result = scraper_service.scrape_all_tracked_fencers(mock_db)

    assert sleep_calls == [scraper_service.FENCER_SCRAPE_DELAY_SEC]
    assert result["fencers_scraped"] == 2


def test_scrape_all_tracked_fencers_retries_with_exponential_backoff(monkeypatch, mock_db):
    html = """
    <html>
      <body>
        <table>
          <tr><th>Tournament</th><th>Event</th><th>Date</th></tr>
          <tr><td>Autumn Open</td><td>Senior Women's Foil</td><td>2025-10-02</td></tr>
        </table>
      </body>
    </html>
    """

    responses = [
        DummyResponse(500, "error", reason="Server Error"),
        DummyResponse(500, "error", reason="Server Error"),
        DummyResponse(200, html),
    ]

    monkeypatch.setattr(
        scraper_service.requests,
        "Session",
        lambda: DummySession(responses),
    )

    sleep_calls = []
    monkeypatch.setattr(scraper_service.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    tracked = SimpleNamespace(
        fencer_id="98765",
        display_name="Retry Fencer",
        last_registration_hash=None,
        failure_count=0,
        last_failure_at=None,
    )

    monkeypatch.setattr(scraper_service, "get_all_active_tracked_fencers", lambda db: [tracked])
    monkeypatch.setattr(
        scraper_service,
        "get_fencer_by_fencingtracker_id",
        lambda db, fid: SimpleNamespace(id=1, name="Jane Doe", fencingtracker_id=fid),
    )
    monkeypatch.setattr(scraper_service, "get_or_create_fencer", MagicMock())
    monkeypatch.setattr(
        scraper_service,
        "get_or_create_tournament",
        lambda db, name, date: SimpleNamespace(id=1, name=name),
    )
    monkeypatch.setattr(
        scraper_service,
        "update_or_create_registration",
        lambda db, fencer, tournament, event_name, source_url: (SimpleNamespace(id=1), True),
    )
    monkeypatch.setattr(scraper_service, "update_fencer_check_status", lambda *args, **kwargs: None)

    result = scraper_service.scrape_all_tracked_fencers(mock_db)

    assert sleep_calls == [1, 2]
    assert result["fencers_scraped"] == 1
    assert result["fencers_failed"] == 0


def test_scrape_all_tracked_fencers_respects_failure_cooldown(monkeypatch, mock_db):
    tracked = SimpleNamespace(
        fencer_id="55555",
        display_name="Cooldown Fencer",
        last_registration_hash=None,
        failure_count=scraper_service.FENCER_MAX_FAILURES,
        last_failure_at=datetime.now(UTC),
    )

    monkeypatch.setattr(scraper_service, "get_all_active_tracked_fencers", lambda db: [tracked])

    scrape_mock = MagicMock()
    monkeypatch.setattr(scraper_service, "scrape_fencer_profile", scrape_mock)
    update_status = MagicMock()
    monkeypatch.setattr(scraper_service, "update_fencer_check_status", update_status)

    result = scraper_service.scrape_all_tracked_fencers(mock_db)

    assert result["fencers_skipped"] == 1
    assert result["fencers_scraped"] == 0
    scrape_mock.assert_not_called()
    update_status.assert_not_called()


from datetime import timedelta

def test_scrape_all_tracked_fencers_resumes_after_cooldown(monkeypatch, mock_db):
    future_time = datetime.now(UTC) + timedelta(minutes=scraper_service.FENCER_FAILURE_COOLDOWN_MIN + 1)
    tracked = SimpleNamespace(
        fencer_id="55555",
        display_name="Cooldown Fencer",
        last_registration_hash=None,
        failure_count=scraper_service.FENCER_MAX_FAILURES,
        last_failure_at=datetime.now(UTC),
    )

    monkeypatch.setattr(scraper_service, "get_all_active_tracked_fencers", lambda db: [tracked])
    monkeypatch.setattr(scraper_service, "scrape_fencer_profile", MagicMock(return_value={"new": 0, "updated": 0, "total": 0, "hash": "next", "skipped": False}))
    monkeypatch.setattr(scraper_service, "update_fencer_check_status", MagicMock())
    monkeypatch.setattr("app.services.fencer_scraper_service.datetime", MagicMock(utcnow=lambda: future_time))


    result = scraper_service.scrape_all_tracked_fencers(mock_db)

    assert result["fencers_skipped"] == 0
    assert result["fencers_scraped"] == 1

def test_scrape_all_tracked_fencers_logs_retries(monkeypatch, mock_db, caplog):
    responses = [
        DummyResponse(500, "error", reason="Server Error"),
        DummyResponse(200, "<html></html>"),
    ]
    monkeypatch.setattr(scraper_service.requests, "Session", lambda: DummySession(responses))
    monkeypatch.setattr(scraper_service.time, "sleep", lambda x: None)

    tracked = SimpleNamespace(
        fencer_id="logging_fencer",
        display_name="Logging Fencer",
        last_registration_hash=None,
        failure_count=0,
        last_failure_at=None,
    )
    monkeypatch.setattr(scraper_service, "get_all_active_tracked_fencers", lambda db: [tracked])
    monkeypatch.setattr(scraper_service, "update_fencer_check_status", MagicMock())

    scraper_service.scrape_all_tracked_fencers(mock_db)

    assert "Request failed for fencer logging_fencer (1/3), retrying in 1s" in caplog.text

