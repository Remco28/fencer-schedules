import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Registration, Tournament
from app.services import scraper_service


class ScraperServiceTableTests(unittest.TestCase):
    """Unit tests for fencingtracker tournament table detection."""

    def setUp(self):
        """Create an isolated in-memory database for each test."""
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        TestingSession = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSession()

    def tearDown(self):
        """Dispose the database session."""
        self.db.close()
        self.engine.dispose()

    def test_is_registration_table_true(self):
        """Registration tables expose expected headings."""
        html = """
        <table>
            <thead>
                <tr><th>Fencer</th><th>Event</th><th>Status</th><th>Date</th></tr>
            </thead>
        </table>
        """
        table = BeautifulSoup(html, "html.parser").find("table")

        self.assertTrue(scraper_service._is_registration_table(table))

    def test_is_registration_table_false(self):
        """Non-registration tables use different headers."""
        html = """
        <table>
            <thead>
                <tr><th>Role</th><th>Coach</th><th>Email</th></tr>
            </thead>
        </table>
        """
        table = BeautifulSoup(html, "html.parser").find("table")

        self.assertFalse(scraper_service._is_registration_table(table))

    @patch("app.services.scraper_service.send_registration_notification")
    @patch("requests.Session.get")
    def test_scrape_skips_non_registration_headings(self, mock_get, mock_notify):
        """Scraper ignores headings whose tables are not registration data."""
        html = """
        <html>
            <body>
                <h3>(Elite FC)</h3>
                <table>
                    <thead>
                        <tr><th>Name</th><th>Event</th><th>Status</th><th>Date</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Dup Fencer</td><td>Dummy Event</td><td></td><td>2024-09-01</td></tr>
                    </tbody>
                </table>

                <h3>Tournaments</h3>
                <table>
                    <thead>
                        <tr><th>Name</th><th>Event</th><th>Status</th><th>Date</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Dup Fencer</td><td>Dummy Event</td><td></td><td>2024-09-01</td></tr>
                    </tbody>
                </table>

                <h3>Club Contacts</h3>
                <table>
                    <tr><th>Name</th><th>Role</th></tr>
                    <tr><td>Alex Smith</td><td>Coach</td></tr>
                </table>

                <h3>October NAC</h3>
                <table>
                    <thead>
                        <tr><th>Fencer</th><th>Event</th><th>Status</th><th>Date</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>John Doe</td><td>Senior Men's Foil</td><td></td><td>2024-10-12</td></tr>
                        <tr><td>Jane Roe</td><td>Senior Women's Foil</td><td></td><td>2024-10-13</td></tr>
                    </tbody>
                </table>
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.content = html.encode("utf-8")
        mock_get.return_value = mock_response
        mock_notify.return_value = "msg-id"

        stats = scraper_service.scrape_and_persist(
            self.db,
            "https://fencingtracker.com/club/100/example"
        )

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["new"], 2)
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(mock_notify.call_count, 2)

        tournaments = self.db.query(Tournament).all()
        self.assertEqual(len(tournaments), 1)
        self.assertEqual(tournaments[0].name, "October NAC")

        registrations = self.db.query(Registration).all()
        self.assertEqual(len(registrations), 2)
        events = sorted(reg.events for reg in registrations)
        self.assertEqual(events, ["Senior Men's Foil", "Senior Women's Foil"])


if __name__ == "__main__":
    unittest.main()
