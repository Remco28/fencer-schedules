import unittest
from unittest.mock import Mock, patch

from app.services.notification_service import (
    send_registration_notification,
    send_notification,
    get_client,
)
from app.services.mailgun_client import NotificationError


class TestNotificationService(unittest.TestCase):
    """Test suite for notification service functions."""

    def setUp(self):
        """Reset the module-level client before each test."""
        import app.services.notification_service
        app.services.notification_service._client = None

    def tearDown(self):
        """Clean up after each test."""
        import app.services.notification_service
        app.services.notification_service._client = None

    @patch('app.services.notification_service.MailgunEmailClient')
    def test_get_client_creates_new_instance(self, mock_client_class):
        """Test that get_client creates a new instance when none exists."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        client = get_client()

        self.assertEqual(client, mock_instance)
        mock_client_class.assert_called_once()

    @patch('app.services.notification_service.MailgunEmailClient')
    def test_get_client_reuses_existing_instance(self, mock_client_class):
        """Test that get_client reuses existing instance."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        # First call creates instance
        client1 = get_client()
        # Second call reuses same instance
        client2 = get_client()

        self.assertEqual(client1, client2)
        self.assertEqual(client1, mock_instance)
        mock_client_class.assert_called_once()  # Should only be called once

    @patch('app.services.notification_service.get_client')
    def test_send_registration_notification_success(self, mock_get_client):
        """Test successful registration notification."""
        mock_client = Mock()
        mock_client.send_text.return_value = 'message-id-123'
        mock_get_client.return_value = mock_client

        message_id = send_registration_notification(
            fencer_name="John Doe",
            tournament_name="Test Tournament",
            events="Épée, Foil",
            source_url="https://example.com/club"
        )

        self.assertEqual(message_id, 'message-id-123')

        expected_subject = "New fencing registration: John Doe"
        expected_body = """Fencer: John Doe
Tournament: Test Tournament
Events: Épée, Foil
Source: https://example.com/club"""

        mock_client.send_text.assert_called_once_with(
            expected_subject,
            expected_body,
            to=None
        )

    @patch('app.services.notification_service.get_client')
    def test_send_registration_notification_with_custom_recipients(self, mock_get_client):
        """Test registration notification with custom recipients."""
        mock_client = Mock()
        mock_client.send_text.return_value = 'message-id-456'
        mock_get_client.return_value = mock_client

        custom_recipients = ['admin@example.com', 'manager@example.com']

        message_id = send_registration_notification(
            fencer_name="Jane Smith",
            tournament_name="Championship",
            events="Sabre",
            source_url="https://example.com/club",
            recipients=custom_recipients
        )

        self.assertEqual(message_id, 'message-id-456')

        mock_client.send_text.assert_called_once_with(
            "New fencing registration: Jane Smith",
            """Fencer: Jane Smith
Tournament: Championship
Events: Sabre
Source: https://example.com/club""",
            to=custom_recipients
        )

    @patch('app.services.notification_service.get_client')
    def test_send_registration_notification_propagates_error(self, mock_get_client):
        """Test that registration notification propagates NotificationError."""
        mock_client = Mock()
        mock_client.send_text.side_effect = NotificationError("API Error")
        mock_get_client.return_value = mock_client

        with self.assertRaises(NotificationError):
            send_registration_notification(
                fencer_name="Test Fencer",
                tournament_name="Test Tournament",
                events="Test Event",
                source_url="https://example.com/test"
            )

    @patch('app.services.notification_service.logging.getLogger')
    @patch('app.services.notification_service.get_client')
    def test_send_notification_legacy_success(self, mock_get_client, mock_logger):
        """Test legacy send_notification function success."""
        mock_client = Mock()
        mock_client.send_text.return_value = 'legacy-message-id'
        mock_get_client.return_value = mock_client
        mock_log_instance = Mock()
        mock_logger.return_value = mock_log_instance

        send_notification("Test Subject", "Test Body")

        mock_client.send_text.assert_called_once_with("Test Subject", "Test Body")
        mock_log_instance.info.assert_called_once_with("Email sent successfully: Test Subject")

    @patch('app.services.notification_service.logging.getLogger')
    @patch('app.services.notification_service.get_client')
    def test_send_notification_legacy_notification_error(self, mock_get_client, mock_logger):
        """Test legacy send_notification handles NotificationError."""
        mock_client = Mock()
        error = NotificationError("Mailgun API Error")
        mock_client.send_text.side_effect = error
        mock_get_client.return_value = mock_client
        mock_log_instance = Mock()
        mock_logger.return_value = mock_log_instance

        # Should not raise, but should log error
        send_notification("Test Subject", "Test Body")

        mock_log_instance.error.assert_called_once_with(f"Failed to send email: {error}")

    @patch('app.services.notification_service.logging.getLogger')
    @patch('app.services.notification_service.get_client')
    def test_send_notification_legacy_unexpected_error(self, mock_get_client, mock_logger):
        """Test legacy send_notification handles unexpected errors."""
        mock_client = Mock()
        error = Exception("Unexpected error")
        mock_client.send_text.side_effect = error
        mock_get_client.return_value = mock_client
        mock_log_instance = Mock()
        mock_logger.return_value = mock_log_instance

        # Should raise unexpected errors
        with self.assertRaises(Exception):
            send_notification("Test Subject", "Test Body")

        mock_log_instance.error.assert_called_once_with(f"Unexpected error sending email: {error}")


if __name__ == '__main__':
    unittest.main()