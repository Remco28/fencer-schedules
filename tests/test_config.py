from pathlib import Path

from fencer_schedules.config import Settings


def test_club_names_come_from_yaml(tmp_path: Path) -> None:
    p = tmp_path / "config.yaml"
    p.write_text('club:\n  name: "Elite Fencers Club"\n  aliases: ["Elite FC"]\n')
    settings = Settings.load(config_path=p, env_path=tmp_path / "missing.env")
    assert settings.club_name == "Elite Fencers Club"
    assert "Elite FC" in settings.club_aliases
    assert "EFC" not in settings.club_aliases


def test_token_comes_from_env_file(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text('club:\n  name: "Elite Fencers Club"\n  aliases: []\n')
    env = tmp_path / ".env"
    env.write_text("ASKFRED_API_TOKEN=test-token-value\n")
    settings = Settings.load(config_path=cfg, env_path=env)
    assert settings.askfred_api_token == "test-token-value"
