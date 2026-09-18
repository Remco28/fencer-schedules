from __future__ import annotations

from datetime import time
from pathlib import Path

import httpx

from fencer_schedules.sources.askfred_prereg import (
    AskFredSite,
    parse_preregistration_clocks,
    parse_preregistrations,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_preregistrations_groups_by_event() -> None:
    html = (FIXTURES / "askfred_prereg_wanglei.html").read_text()
    by_event = parse_preregistrations(html)
    assert "Anderson, Connor" in [f.name for f in by_event["Y14 Mixed Epee"]]
    assert any(f.club == "Elite Fencers Club" for f in by_event["Y14 Mixed Epee"])
    assert [f.name for f in by_event["Senior Mixed Epee"]] == ["Sun, Kang"]


def test_parse_checkin_clocks() -> None:
    html = (FIXTURES / "askfred_prereg_wanglei.html").read_text()
    clocks = parse_preregistration_clocks(html)
    assert clocks["Y14 Mixed Epee"] == time(9, 30)
    assert clocks["Senior Mixed Epee"] == time(14, 0)


class _Resp:
    def __init__(self, status: int, url: str, text: str, content_type: str = "text/html"):
        self.status_code = status
        self.url = url
        self.text = text
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


def test_login_retries_cloudflare_then_succeeds(monkeypatch) -> None:
    blocked = _Resp(
        403,
        "https://www.askfred.net/users/sign_in",
        "<!DOCTYPE html><title>Just a moment...</title>",
    )
    sign_in = _Resp(
        200,
        "https://www.askfred.net/users/sign_in",
        '<form action="/users/sign_in"><input name="authenticity_token" value="tok"></form>',
    )
    home = _Resp(200, "https://www.askfred.net/", "ok")

    class BlockedClient:
        def get(self, url, **kwargs):
            return blocked

        def post(self, url, **kwargs):
            raise AssertionError("must not post through the blocked client")

        def close(self) -> None:
            return None

    class Browser:
        def get(self, url, **kwargs):
            assert url.endswith("/users/sign_in")
            return sign_in

        def post(self, url, **kwargs):
            assert kwargs["data"]["authenticity_token"] == "tok"
            return home

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "fencer_schedules.sources.askfred_prereg.impersonated_session",
        lambda: Browser(),
    )
    site = AskFredSite("user@example.com", "secret", client=BlockedClient())
    site.login()
    assert site._authed


def test_login_blocked_httpx_is_not_raised_as_status() -> None:
    """A Cloudflare 403 must be classified before raise_for_status."""
    class BlockedClient:
        def get(self, url, **kwargs):
            request = httpx.Request("GET", url)
            return httpx.Response(
                403,
                request=request,
                headers={"content-type": "text/html; charset=UTF-8"},
                text="<!DOCTYPE html><title>Just a moment...</title>",
            )

        def close(self) -> None:
            return None

    site = AskFredSite("user@example.com", "secret", client=BlockedClient())
    site._impersonating = True
    try:
        site.login()
    except RuntimeError as exc:
        assert "bot challenge" in str(exc)
    else:
        raise AssertionError("expected bot-challenge error")
