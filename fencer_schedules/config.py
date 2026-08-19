from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    club_name: str = "Elite Fencers Club"
    club_aliases: list[str] = Field(default_factory=list)
    askfred_api_token: str = ""
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
        token = ""
        if env_path.is_file():
            for line in env_path.read_text().splitlines():
                if line.startswith("ASKFRED_API_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
        return cls(
            club_name=club_name,
            club_aliases=club_aliases,
            askfred_api_token=token,
        )
