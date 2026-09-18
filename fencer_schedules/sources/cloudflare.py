from __future__ import annotations

from typing import Any

_CHALLENGE_MARKERS = (
    "just a moment",
    "challenge-platform",
    "cf-chl",
    "enable javascript and cookies",
    "verify you are human",
)


def is_cloudflare_challenge(resp: Any) -> bool:
    """True when the body is a Cloudflare interstitial, not an API error."""
    ctype = str(resp.headers.get("content-type") or "").lower()
    if "json" in ctype:
        return False
    try:
        body = (resp.text or "")[:4000].casefold()
    except Exception:
        return False
    if any(marker in body for marker in _CHALLENGE_MARKERS):
        return True
    return resp.status_code in (403, 503) and "html" in ctype


def impersonated_session():
    from curl_cffi.requests import Session

    return Session(impersonate="chrome", timeout=30)
