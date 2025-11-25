"""HTTP client for fetching FTL data."""
import requests


def fetch_html(url: str, timeout: int = 10) -> str:
    """
    Fetch HTML content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 10)

    Returns:
        The HTML content as a string

    Raises:
        ValueError: If the request fails or returns empty content
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch URL: {exc}") from exc

    if not response.text:
        raise ValueError("Empty response body")

    return response.text
