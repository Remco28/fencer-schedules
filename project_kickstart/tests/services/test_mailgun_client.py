import unittest
import os
from unittest.mock import Mock, patch
import requests
from requests.exceptions import RequestException

from app.services.mailgun_client import MailgunEmailClient, NotificationError


class TestMailgunEmailClient(unittest.TestCase):
    """Test suite for MailgunEmailClient."""

    def setUp(self):
        """Set up test environment variables."""
        self.env_patcher = patch.dict(os.environ, {
            'MAILGUN_API_KEY': 'test-api-key',
            'MAILGUN_DOMAIN': 'test-domain.com',
            'MAILGUN_SENDER': 'test@example.com',
            'MAILGUN_DEFAULT_RECIPIENTS': 'recipient1@example.com,recipient2@example.com'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    def test_init_success(self):
        """Test successful initialization with valid environment variables."""
        client = MailgunEmailClient()

        self.assertEqual(client.api_key, 'test-api-key')
        self.assertEqual(client.domain, 'test-domain.com')
        self.assertEqual(client.sender, 'test@example.com')
        self.assertEqual(client.default_recipients, ['recipient1@example.com', 'recipient2@example.com'])
        self.assertEqual(client.base_url, 'https://api.mailgun.net/v3/test-domain.com/messages')
        self.assertEqual(client.session.auth, ('api', 'test-api-key'))

    def test_init_missing_api_key(self):
        """Test initialization failure when MAILGUN_API_KEY is missing."""
        self.env_patcher.stop()
        with patch.dict(os.environ, {
            'MAILGUN_DOMAIN': 'test-domain.com',
            'MAILGUN_SENDER': 'test@example.com',
            'MAILGUN_DEFAULT_RECIPIENTS': 'recipient@example.com'
        }, clear=True):
            with self.assertRaises(RuntimeError) as context:
                MailgunEmailClient()
            self.assertIn("MAILGUN_API_KEY environment variable is required", str(context.exception))
        self.env_patcher.start()

    def test_init_missing_domain(self):
        """Test initialization failure when MAILGUN_DOMAIN is missing."""
        self.env_patcher.stop()
        with patch.dict(os.environ, {
            'MAILGUN_API_KEY': 'test-key',
            'MAILGUN_SENDER': 'test@example.com',
            'MAILGUN_DEFAULT_RECIPIENTS': 'recipient@example.com'
        }, clear=True):
            with self.assertRaises(RuntimeError) as context:
                MailgunEmailClient()
            self.assertIn("MAILGUN_DOMAIN environment variable is required", str(context.exception))
        self.env_patcher.start()

    def test_init_missing_sender(self):
        """Test initialization failure when MAILGUN_SENDER is missing."""
        self.env_patcher.stop()
        with patch.dict(os.environ, {
            'MAILGUN_API_KEY': 'test-key',
            'MAILGUN_DOMAIN': 'test-domain.com',
            'MAILGUN_DEFAULT_RECIPIENTS': 'recipient@example.com'
        }, clear=True):
            with self.assertRaises(RuntimeError) as context:
                MailgunEmailClient()
            self.assertIn("MAILGUN_SENDER environment variable is required", str(context.exception))
        self.env_patcher.start()

    def test_init_missing_recipients(self):
        """Test initialization failure when MAILGUN_DEFAULT_RECIPIENTS is missing."""
        self.env_patcher.stop()
        with patch.dict(os.environ, {
            'MAILGUN_API_KEY': 'test-key',
            'MAILGUN_DOMAIN': 'test-domain.com',
            'MAILGUN_SENDER': 'test@example.com'
        }, clear=True):
            with self.assertRaises(RuntimeError) as context:
                MailgunEmailClient()
            self.assertIn("MAILGUN_DEFAULT_RECIPIENTS environment variable is required", str(context.exception))
        self.env_patcher.start()

    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_success(self, mock_logger):
        """Test successful email sending."""
        client = MailgunEmailClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'test-message-id-123'}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            message_id = client.send_text("Test Subject", "Test Body")

            self.assertEqual(message_id, 'test-message-id-123')

            # Verify API call
            mock_post.assert_called_once_with(
                client.base_url,
                data={
                    'from': 'test@example.com',
                    'to': ['recipient1@example.com', 'recipient2@example.com'],
                    'subject': 'Test Subject',
                    'text': 'Test Body'
                },
                timeout=10
            )

            # Verify logging
            mock_logger.return_value.info.assert_called_once()

    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_with_custom_recipients_and_tags(self, mock_logger):
        """Test sending email with custom recipients and tags."""
        client = MailgunEmailClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'test-message-id-456'}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            message_id = client.send_text(
                "Test Subject",
                "Test Body",
                to=['custom@example.com'],
                tags=['test', 'urgent']
            )

            self.assertEqual(message_id, 'test-message-id-456')

            # Verify API call with custom recipients and tags
            mock_post.assert_called_once_with(
                client.base_url,
                data={
                    'from': 'test@example.com',
                    'to': ['custom@example.com'],
                    'subject': 'Test Subject',
                    'text': 'Test Body',
                    'o:tag': ['test', 'urgent']
                },
                timeout=10
            )

    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_4xx_error_non_retryable(self, mock_logger):
        """Test that 4xx errors are non-retryable."""
        client = MailgunEmailClient()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            with self.assertRaises(NotificationError) as context:
                client.send_text("Test Subject", "Test Body")

            self.assertIn("Client error (HTTP 400)", str(context.exception))
            self.assertEqual(context.exception.status_code, 400)
            self.assertEqual(context.exception.response_text, 'Bad Request')

            # Should not retry 4xx errors
            mock_post.assert_called_once()
            mock_logger.return_value.error.assert_called_once()

    @patch('app.services.mailgun_client.time.sleep')
    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_retry_then_success(self, mock_logger, mock_sleep):
        """Test retry logic with eventual success."""
        client = MailgunEmailClient()
        # First call raises exception, second succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'test-message-id-retry'}

        with patch.object(client.session, 'post') as mock_post:
            mock_post.side_effect = [RequestException("Network error"), mock_response]

            message_id = client.send_text("Test Subject", "Test Body")

            self.assertEqual(message_id, 'test-message-id-retry')
            self.assertEqual(mock_post.call_count, 2)
            mock_sleep.assert_called_once_with(1)  # First backoff
            mock_logger.return_value.warning.assert_called_once()

    @patch('app.services.mailgun_client.time.sleep')
    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_retry_exhausted(self, mock_logger, mock_sleep):
        """Test that all retries are exhausted and error is raised."""
        client = MailgunEmailClient()

        with patch.object(client.session, 'post') as mock_post:
            mock_post.side_effect = RequestException("Persistent network error")

            with self.assertRaises(NotificationError) as context:
                client.send_text("Test Subject", "Test Body")

            self.assertIn("Failed to send email after 3 attempts", str(context.exception))
            self.assertEqual(mock_post.call_count, 3)

            # Verify backoff calls
            expected_sleep_calls = [1, 2]
            actual_sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            self.assertEqual(actual_sleep_calls, expected_sleep_calls)

            # Verify warning logs for each attempt
            self.assertEqual(mock_logger.return_value.warning.call_count, 3)

    @patch('app.services.mailgun_client.time.sleep')
    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_5xx_retry_then_success(self, mock_logger, mock_sleep):
        """Test that 5xx errors are retried."""
        client = MailgunEmailClient()
        first_response = Mock()
        first_response.status_code = 500
        first_response.text = 'Internal Server Error'

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {'id': 'test-message-id-5xx'}

        with patch.object(client.session, 'post') as mock_post:
            mock_post.side_effect = [first_response, success_response]

            message_id = client.send_text("Test Subject", "Test Body")

            self.assertEqual(message_id, 'test-message-id-5xx')
            self.assertEqual(mock_post.call_count, 2)
            mock_sleep.assert_called_once_with(1)

    @patch('app.services.mailgun_client.time.sleep')
    @patch('app.services.mailgun_client.logging.getLogger')
    def test_send_text_rate_limit_with_retry_after(self, mock_logger, mock_sleep):
        """Test rate limit handling with Retry-After header."""
        client = MailgunEmailClient()
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'Retry-After': '5'}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {'id': 'test-message-id-rate-limit'}

        with patch.object(client.session, 'post') as mock_post:
            mock_post.side_effect = [rate_limit_response, success_response]

            message_id = client.send_text("Test Subject", "Test Body")

            self.assertEqual(message_id, 'test-message-id-rate-limit')
            self.assertEqual(mock_post.call_count, 2)
            mock_sleep.assert_called_once_with(5)  # Should use Retry-After value
            mock_logger.return_value.warning.assert_called_once()

    def test_send_text_no_message_id_in_response(self):
        """Test handling response without message ID."""
        client = MailgunEmailClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No 'id' field

        with patch.object(client.session, 'post', return_value=mock_response):
            message_id = client.send_text("Test Subject", "Test Body")
            self.assertEqual(message_id, 'unknown')

    def test_timeout_is_enforced(self):
        """Test that the 10s timeout is properly passed to requests."""
        client = MailgunEmailClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'test-timeout-id'}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            client.send_text("Test Subject", "Test Body")

            # Verify timeout parameter is passed
            call_args = mock_post.call_args
            self.assertIn('timeout', call_args.kwargs)
            self.assertEqual(call_args.kwargs['timeout'], 10)


if __name__ == '__main__':
    unittest.main()