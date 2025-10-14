import os
import time
import logging
from typing import Optional, List
import requests
from requests.exceptions import RequestException


class NotificationError(Exception):
    """Raised when email notification fails after retries."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class MailgunEmailClient:
    """Mailgun email client with retry logic and proper error handling."""

    def __init__(self):
        """Initialize the Mailgun client with environment configuration."""
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.timeout = 10

        # Load and validate configuration
        self.api_key = os.getenv('MAILGUN_API_KEY')
        if not self.api_key:
            raise RuntimeError("MAILGUN_API_KEY environment variable is required")

        self.domain = os.getenv('MAILGUN_DOMAIN')
        if not self.domain:
            raise RuntimeError("MAILGUN_DOMAIN environment variable is required")

        self.sender = os.getenv('MAILGUN_SENDER')
        if not self.sender:
            raise RuntimeError("MAILGUN_SENDER environment variable is required")

        default_recipients = os.getenv('MAILGUN_DEFAULT_RECIPIENTS')
        if not default_recipients:
            raise RuntimeError("MAILGUN_DEFAULT_RECIPIENTS environment variable is required")

        self.default_recipients = [email.strip() for email in default_recipients.split(',')]

        # Set up authentication
        self.session.auth = ('api', self.api_key)

        self.base_url = f"https://api.mailgun.net/v3/{self.domain}/messages"

    def send_text(
        self,
        subject: str,
        body: str,
        to: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Send a plain text email via Mailgun.

        Args:
            subject: Email subject line
            body: Email body content (plain text)
            to: List of recipient email addresses (defaults to configured recipients)
            tags: Optional tags for tracking

        Returns:
            Mailgun message ID on success

        Raises:
            NotificationError: When sending fails after retries
        """
        recipients = to or self.default_recipients

        # Prepare the payload
        data = {
            'from': self.sender,
            'to': recipients,
            'subject': subject,
            'text': body
        }

        # Add tags if provided
        if tags:
            for tag in tags:
                data.setdefault('o:tag', []).append(tag)

        # Retry policy: up to 3 attempts with exponential backoff
        max_attempts = 3
        backoff_times = [1, 2]  # Sleep times between retries

        last_exception = None

        for attempt in range(max_attempts):
            try:
                response = self.session.post(self.base_url, data=data, timeout=self.timeout)

                # Handle rate limiting with Retry-After
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after and attempt < max_attempts - 1:
                        sleep_time = int(retry_after)
                        self.logger.warning(f"Rate limited, sleeping for {sleep_time} seconds")
                        time.sleep(sleep_time)
                        continue

                # Check if response indicates success
                if response.status_code == 200:
                    response_data = response.json()
                    message_id = response_data.get('id', 'unknown')
                    self.logger.info(f"Email sent successfully: message_id={message_id}, recipients={recipients}")
                    return message_id

                # 4xx errors are non-retryable (except 429 handled above)
                if 400 <= response.status_code < 500:
                    error_msg = f"Client error (HTTP {response.status_code}): {response.text}"
                    self.logger.error(error_msg)
                    raise NotificationError(error_msg, response.status_code, response.text)

                # 5xx errors are retryable
                if response.status_code >= 500:
                    error_msg = f"Server error (HTTP {response.status_code}): {response.text}"
                    self.logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {error_msg}")
                    if attempt < max_attempts - 1:
                        sleep_time = backoff_times[attempt]
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise NotificationError(error_msg, response.status_code, response.text)

            except RequestException as e:
                error_msg = f"Network error: {str(e)}"
                self.logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {error_msg}")
                last_exception = e

                if attempt < max_attempts - 1:
                    sleep_time = backoff_times[attempt]
                    time.sleep(sleep_time)
                    continue

        # If we get here, all attempts failed
        final_error = f"Failed to send email after {max_attempts} attempts"
        if last_exception:
            final_error += f": {str(last_exception)}"

        self.logger.error(final_error)
        raise NotificationError(final_error)