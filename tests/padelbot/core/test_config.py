import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.padelbot.core import config

REPO_ROOT = Path(__file__).parents[3]
ENV_VARS = (
    "SPOND_USERNAME",
    "SPOND_PASSWORD",
    "SPOND_GROUP_ID",
    "NACO_ENABLED",
    "NACO_BASE_URL",
    "NACO_API_KEY",
)
FILE_AUTH = {"username": "file-user", "password": "file-pass", "group_id": "file-group"}
FILE_NACO = {"enabled": False, "base_url": "http://file.test", "api_key": "file-key"}


def _section(name, values):
    """A TOML table. JSON and TOML write these strings, numbers and booleans alike."""
    lines = [f"{key} = {json.dumps(value)}" for key, value in values.items()]
    return "\n".join([f"[{name}]", *lines]) + "\n"


def _readconfig() -> dict[str, Any]:
    cfg = config.readconfig()
    assert cfg is not None
    return cfg


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """An empty config.toml in the working directory, with no .env or env vars."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "config.toml"
    path.write_text("")
    return path


class TestFileAndDefaults:
    def test_returns_the_values_in_the_file(self, config_file):
        config_file.write_text(
            _section("auth", FILE_AUTH)
            + _section("naco", FILE_NACO)
            + _section("general", {"seconds_to_sleep": 30})
            + _section("logging", {"level": "WARNING"})
            + _section("rules.r1", {"type": "MaxEventsPerWeek", "max_events": 2})
            + _section("actions.a1", {"type": "NacoCreateTournament"})
        )

        assert config.readconfig() == {
            "auth": FILE_AUTH,
            "naco": FILE_NACO,
            "general": {"seconds_to_sleep": 30},
            "logging": {"level": "WARNING"},
            "rules": {"r1": {"type": "MaxEventsPerWeek", "max_events": 2}},
            "actions": {"a1": {"type": "NacoCreateTournament"}},
        }

    def test_uses_defaults_for_sections_the_file_leaves_out(self, config_file):
        config_file.write_text(_section("auth", FILE_AUTH))

        assert config.readconfig() == {
            "auth": FILE_AUTH,
            "naco": {
                "enabled": False,
                "base_url": "http://localhost:8000",
                "api_key": "",
            },
            "general": {"seconds_to_sleep": 600},
            "logging": {"level": "INFO"},
            "rules": {},
            "actions": {},
        }


class TestEnvironmentOverrides:
    @pytest.mark.parametrize(
        ("variable", "key"),
        [
            ("SPOND_USERNAME", "username"),
            ("SPOND_PASSWORD", "password"),
            ("SPOND_GROUP_ID", "group_id"),
        ],
    )
    def test_spond_variable_overrides_the_file(
        self, config_file, monkeypatch, variable, key
    ):
        config_file.write_text(_section("auth", FILE_AUTH))
        monkeypatch.setenv(variable, "from-env")

        assert _readconfig()["auth"] == {**FILE_AUTH, key: "from-env"}

    @pytest.mark.parametrize(
        ("variable", "key"),
        [("NACO_BASE_URL", "base_url"), ("NACO_API_KEY", "api_key")],
    )
    def test_naco_variable_overrides_the_file(
        self, config_file, monkeypatch, variable, key
    ):
        config_file.write_text(
            _section("auth", FILE_AUTH) + _section("naco", FILE_NACO)
        )
        monkeypatch.setenv(variable, "from-env")

        assert _readconfig()["naco"] == {**FILE_NACO, key: "from-env"}

    @pytest.mark.parametrize(
        ("value", "enabled"),
        [
            ("1", True),
            ("true", True),
            ("TRUE", True),
            ("Yes", True),
            ("0", False),
            ("false", False),
            ("no", False),
            ("on", False),
        ],
    )
    def test_naco_enabled_overrides_the_file(
        self, config_file, monkeypatch, value, enabled
    ):
        # The file says the opposite, so the result can only come from the variable.
        file_naco = {**FILE_NACO, "enabled": not enabled}
        config_file.write_text(
            _section("auth", FILE_AUTH) + _section("naco", file_naco)
        )
        monkeypatch.setenv("NACO_ENABLED", value)

        assert _readconfig()["naco"] == {**FILE_NACO, "enabled": enabled}

    def test_empty_variables_are_ignored(self, config_file, monkeypatch):
        file_naco = {**FILE_NACO, "enabled": True}
        config_file.write_text(
            _section("auth", FILE_AUTH) + _section("naco", file_naco)
        )
        for name in ENV_VARS:
            monkeypatch.setenv(name, "")

        cfg = _readconfig()

        assert cfg["auth"] == FILE_AUTH
        assert cfg["naco"] == file_naco


class TestMissingCredentials:
    @pytest.mark.parametrize("key", ["username", "password", "group_id"])
    @pytest.mark.parametrize("how", ["empty", "absent"])
    def test_returns_none_and_logs_an_error(self, config_file, caplog, key, how):
        auth = {**FILE_AUTH, key: ""}
        if how == "absent":
            del auth[key]
        config_file.write_text(_section("auth", auth))

        with caplog.at_level(logging.ERROR):
            assert config.readconfig() is None
        assert "username, password or group_id is missing" in caplog.text

    def test_variable_supplies_a_credential_the_file_leaves_empty(
        self, config_file, monkeypatch
    ):
        config_file.write_text(_section("auth", {**FILE_AUTH, "password": ""}))
        monkeypatch.setenv("SPOND_PASSWORD", "from-env")

        assert _readconfig()["auth"] == {**FILE_AUTH, "password": "from-env"}


class TestShippedConfig:
    def test_works_with_credentials_from_the_environment(
        self, config_file, monkeypatch
    ):
        """The `docker run` in the README: shipped config.toml plus SPOND_* variables."""
        shutil.copy(REPO_ROOT / "config.toml", config_file)
        monkeypatch.setenv("SPOND_USERNAME", "env-user")
        monkeypatch.setenv("SPOND_PASSWORD", "env-pass")
        monkeypatch.setenv("SPOND_GROUP_ID", "env-group")

        cfg = _readconfig()

        assert cfg["auth"] == {
            "username": "env-user",
            "password": "env-pass",
            "group_id": "env-group",
        }
        # Everything the bot reads without a fallback at startup or in a cycle.
        assert isinstance(logging.getLevelNamesMapping()[cfg["logging"]["level"]], int)
        assert cfg["general"]["seconds_to_sleep"] > 0
        assert isinstance(cfg["naco"]["enabled"], bool)
        assert cfg["naco"]["base_url"]
