from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO = Path(__file__).resolve().parents[1]

DEFAULT_ALERT_RECIPIENT = "frankcng@gmail.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    club_name: str = "Elite Fencers Club"
    club_aliases: list[str] = Field(default_factory=list)
    askfred_api_token: str = ""
    askfred_email: str = ""
    askfred_password: str = ""
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
            askfred_api_token=env.get("ASKFRED_API_TOKEN", ""),
            askfred_email=env.get("ASKFRED_EMAIL", ""),
            askfred_password=env.get("ASKFRED_PASSWORD", ""),
            agentmail_api_key=env.get("AGENTMAIL_API_KEY", ""),
            agentmail_inbox=env.get("AGENTMAIL_INBOX", ""),
        )
