
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from app import crud, models
from app.database import SessionLocal, engine
from app.services import digest_service
from app.main import _run_scrape_job, _run_fencer_scrape_job

@pytest.fixture(scope="module")
def db_session():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        models.Base.metadata.drop_all(bind=engine)

def test_e2e_tracked_fencer_flow(db_session, monkeypatch):
    # 1. Seed data
    user = crud.create_user(db_session, "e2e_user", "e2e@example.com", "password")
    tracked_club = crud.create_tracked_club(db_session, user.id, "https://fencingtracker.com/club/1", "Test Club")
    tracked_fencer = crud.create_tracked_fencer(db_session, user.id, "12345", "Test Fencer")
    db_session.commit()

    club_html = """
    <html><body>
        <h3>Some Tournament</h3>
        <table>
            <tr><th>Name</th><th>Event</th><th>Reg. Date</th></tr>
            <tr><td>Test Fencer</td><td>Senior Men's Epee</td><td>2025-10-03</td></tr>
        </table>
    </body></html>
    """

    fencer_html = """
    <html><body>
        <h2>Test Fencer's Profile</h2>
        <table>
            <tr><th>Tournament</th><th>Event</th><th>Date</th></tr>
            <tr><td>Some Tournament</td><td>Senior Men's Epee</td><td>2025-10-03</td></tr>
        </table>
    </body></html>
    """

    # Mock external calls
    def mock_scrape(url, **kwargs):
        if "club" in url:
            return SimpleNamespace(status_code=200, text=club_html)
        return SimpleNamespace(status_code=200, text=fencer_html)

    monkeypatch.setattr("app.services.scraper_service.requests.get", mock_scrape)
    monkeypatch.setattr("app.services.fencer_scraper_service.requests.Session.get", mock_scrape)
    monkeypatch.setattr("app.services.fencer_scraper_service.time.sleep", lambda x: None)


    # 2. Run scrapers
    _run_scrape_job(tracked_club.club_url)
    _run_fencer_scrape_job()

    # 3. Run digest and assert
    with patch("app.services.digest_service.send_registration_notification") as mock_send:
        sent = digest_service.send_user_digest(db_session, user)

    assert sent is True
    mock_send.assert_called_once()
    
    email_body = mock_send.call_args.kwargs['body']
    assert "TRACKED CLUBS" in email_body
    assert "TRACKED FENCERS" not in email_body # Deduplicated
    assert email_body.count("Senior Men's Epee") == 1

    # 4. Cleanup
    crud.delete_user(db_session, user.id)
    db_session.commit()
