from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import respx

from fencer_schedules.config import Settings
from fencer_schedules.load import load_tournament
from fencer_schedules.models import Fencer
from fencer_schedules.sources.askfred import AskFredClient

FIXTURES = Path(__file__).parent / "fixtures"
LOCAL_ID = "07060a1f-1e22-4db1-b6f6-a7f0d956d877"


class FakeSite:
    def fetch_preregistrations(self, tournament_id: str):
        assert tournament_id == LOCAL_ID
        return {
            "Y14 Mixed Epee": [Fencer(name="Anderson, Connor", club="Elite Fencers Club")],
            "Senior Mixed Epee": [Fencer(name="Sun, Kang", club="Elite Fencers Club")],
        }

    def fetch_preregistration_clocks(self, tournament_id: str):
        return {}


@respx.mock
def test_local_load_uses_prereg_names() -> None:
    respx.get(f"https://www.askfred.net/api/v1/tournaments/{LOCAL_ID}").mock(
        return_value=httpx.Response(
            200, json=json.loads((FIXTURES / "askfred_tournament_wanglei.json").read_text())
        )
    )
    respx.get(f"https://www.askfred.net/api/v1/tournaments/{LOCAL_ID}/events").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "e1",
                        "type": "event",
                        "attributes": {
                            "full_name": "Y14 Mixed Epee",
                            "close_of_registration": "2026-08-29T09:30:00.000-04:00",
                        },
                    },
                    {
                        "id": "e2",
                        "type": "event",
                        "attributes": {
                            "full_name": "Senior Mixed Epee",
                            "close_of_registration": "2026-08-29T14:00:00.000-04:00",
                        },
                    },
                ],
                "metadata": {"page": 1, "per_page": 50, "last_page": 1},
            },
        )
    )
    settings = Settings(club_name="Elite Fencers Club", club_aliases=["Elite FC"], askfred_api_token="x")
    tournament = load_tournament(
        LOCAL_ID,
        settings,
        askfred=AskFredClient(token="x", today=date(2026, 8, 19)),
        askfred_site=FakeSite(),
    )
    assert tournament.names_available
    y14 = next(e for e in tournament.events if e.name == "Y14 Mixed Epee")
    assert y14.fencers[0].name == "Anderson, Connor"
