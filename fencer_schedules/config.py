from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO = Path(__file__).resolve().parents[1]

DEFAULT_ALERT_RECIPIENT = "frankcng@gmail.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_prefix="FENCER_SCHEDULES_UNUSED_")

    club_name: str = "Elite Fencers Club"
    club_aliases: list[str] = Field(default_factory=list)
    # All tournament data comes from fencing-api (see fencing_api.py).
    fencing_api_url: str = "http://127.0.0.1:8780"
    fencing_api_key: str = ""
    agentmail_api_key: str = ""
    agentmail_inbox: str = ""
    database_path: Path = _REPO / "fencer_schedules.db"

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        env_path: Path | None = None,
    ) -> Settings:
        config_path = config_path or (_REPO / "config.yaml")
        env_path = env_path or (_REPO / ".env")
        club_name = "Elite Fencers Club"
        club_aliases: list[str] = []
        if config_path.is_file():
            raw = yaml.safe_load(config_path.read_text()) or {}
            club = raw.get("club") or {}
            club_name = club.get("name") or club_name
            club_aliases = list(club.get("aliases") or [])
        env: dict[str, str] = {}
        if env_path.is_file():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
        return cls(
            club_name=club_name,
            club_aliases=club_aliases,
            fencing_api_url=env.get("FENCING_API_URL", "http://127.0.0.1:8780"),
            fencing_api_key=env.get("FENCING_API_KEY", ""),
            agentmail_api_key=env.get("AGENTMAIL_API_KEY", ""),
            agentmail_inbox=env.get("AGENTMAIL_INBOX", ""),
        )

    def fencing_api(self, wait_s: float = 20.0):
        from fencer_schedules.fencing_api import FencingApi

        return FencingApi(self.fencing_api_url, self.fencing_api_key, wait_s=wait_s)
