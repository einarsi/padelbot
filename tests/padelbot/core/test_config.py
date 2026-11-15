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
    "SPOND_INCLUDE_HIDDEN_EVENTS",
    "NACO_ENABLED",
    "NACO_BASE_URL",
    "NACO_API_KEY",
)
CREDENTIALS = {
    "username": "file-user",
    "password": "file-pass",
    "group_id": "file-group",
}
FILE_SPOND = {**CREDENTIALS, "include_hidden_events": False}
FILE_NACO = {"enabled": False, "base_url": "http://file.test", "api_key": "file-key"}
DEFAULT_NACO = {"enabled": False, "base_url": "http://localhost:8000", "api_key": ""}
DEFAULT_GENERAL = {"seconds_to_sleep": 600}
FILE_GENERAL = {"seconds_to_sleep": 30}


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
            _section("spond", FILE_SPOND)
            + _section("naco", FILE_NACO)
            + _section("general", FILE_GENERAL)
            + _section("logging", {"level": "WARNING"})
            + _section("rules.r1", {"type": "MaxEventsPerWeek", "max_events": 2})
            + _section("actions.a1", {"type": "NacoCreateTournament"})
        )

        assert config.readconfig() == {
            "spond": FILE_SPOND,
            "naco": FILE_NACO,
            "general": FILE_GENERAL,
            "logging": {"level": "WARNING"},
            "rules": {"r1": {"type": "MaxEventsPerWeek", "max_events": 2}},
            "actions": {"a1": {"type": "NacoCreateTournament"}},
        }

    def test_uses_defaults_for_sections_the_file_leaves_out(self, config_file):
        config_file.write_text(_section("spond", FILE_SPOND))

        assert config.readconfig() == {
            "spond": FILE_SPOND,
            "naco": DEFAULT_NACO,
            "general": DEFAULT_GENERAL,
            "logging": {"level": "INFO"},
            "rules": {},
            "actions": {},
        }

    @pytest.mark.parametrize(
        ("section", "expected"),
        [
            ("naco", DEFAULT_NACO),
            ("general", DEFAULT_GENERAL),
            ("logging", {"level": "INFO"}),
        ],
        ids=["naco", "general", "logging"],
    )
    def test_uses_defaults_for_keys_a_section_leaves_out(
        self, config_file, section, expected
    ):
        config_file.write_text(_section("spond", FILE_SPOND) + f"[{section}]\n")

        assert _readconfig()[section] == expected

    def test_includes_hidden_events_unless_the_file_says_otherwise(self, config_file):
        config_file.write_text(_section("spond", CREDENTIALS))

        assert _readconfig()["spond"] == {**CREDENTIALS, "include_hidden_events": True}

    def test_keeps_the_keys_a_partial_section_sets(self, config_file):
        config_file.write_text(
            _section("spond", FILE_SPOND) + _section("naco", {"enabled": True})
        )

        assert _readconfig()["naco"] == {**DEFAULT_NACO, "enabled": True}


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
        config_file.write_text(_section("spond", FILE_SPOND))
        monkeypatch.setenv(variable, "from-env")

        assert _readconfig()["spond"] == {**FILE_SPOND, key: "from-env"}

    @pytest.mark.parametrize(
        ("variable", "key"),
        [("NACO_BASE_URL", "base_url"), ("NACO_API_KEY", "api_key")],
    )
    def test_naco_variable_overrides_the_file(
        self, config_file, monkeypatch, variable, key
    ):
        config_file.write_text(
            _section("spond", FILE_SPOND) + _section("naco", FILE_NACO)
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
            _section("spond", FILE_SPOND) + _section("naco", file_naco)
        )
        monkeypatch.setenv("NACO_ENABLED", value)

        assert _readconfig()["naco"] == {**FILE_NACO, "enabled": enabled}

    @pytest.mark.parametrize(
        ("value", "included"),
        [("1", True), ("True", True), ("yes", True), ("0", False), ("false", False)],
    )
    def test_include_hidden_events_overrides_the_file(
        self, config_file, monkeypatch, value, included
    ):
        # The file says the opposite, so the result can only come from the variable.
        file_spond = {**FILE_SPOND, "include_hidden_events": not included}
        config_file.write_text(_section("spond", file_spond))
        monkeypatch.setenv("SPOND_INCLUDE_HIDDEN_EVENTS", value)

        assert _readconfig()["spond"] == {
            **FILE_SPOND,
            "include_hidden_events": included,
        }

    def test_empty_variables_are_ignored(self, config_file, monkeypatch):
        file_naco = {**FILE_NACO, "enabled": True}
        config_file.write_text(
            _section("spond", FILE_SPOND) + _section("naco", file_naco)
        )
        for name in ENV_VARS:
            monkeypatch.setenv(name, "")

        cfg = _readconfig()

        assert cfg["spond"] == FILE_SPOND
        assert cfg["naco"] == file_naco

    def test_naco_enabled_works_without_a_naco_section(self, config_file, monkeypatch):
        config_file.write_text(_section("spond", FILE_SPOND))
        monkeypatch.setenv("NACO_ENABLED", "true")

        assert _readconfig()["naco"] == {**DEFAULT_NACO, "enabled": True}

    def test_spond_variables_work_without_a_spond_section(
        self, config_file, monkeypatch
    ):
        monkeypatch.setenv("SPOND_USERNAME", "env-user")
        monkeypatch.setenv("SPOND_PASSWORD", "env-pass")
        monkeypatch.setenv("SPOND_GROUP_ID", "env-group")

        assert _readconfig()["spond"] == {
            "username": "env-user",
            "password": "env-pass",
            "group_id": "env-group",
            "include_hidden_events": True,
        }

    def test_an_override_does_not_leak_into_the_next_read(
        self, config_file, monkeypatch
    ):
        config_file.write_text(_section("spond", FILE_SPOND))
        monkeypatch.setenv("NACO_BASE_URL", "http://env.test")
        assert _readconfig()["naco"]["base_url"] == "http://env.test"

        monkeypatch.delenv("NACO_BASE_URL")
        assert _readconfig()["naco"] == DEFAULT_NACO


class TestMissingCredentials:
    @pytest.mark.parametrize("key", ["username", "password", "group_id"])
    @pytest.mark.parametrize("how", ["empty", "absent"])
    def test_returns_none_and_logs_an_error(self, config_file, caplog, key, how):
        section = {**FILE_SPOND, key: ""}
        if how == "absent":
            del section[key]
        config_file.write_text(_section("spond", section))

        with caplog.at_level(logging.ERROR):
            assert config.readconfig() is None
        assert "username, password or group_id is missing" in caplog.text

    def test_returns_none_without_a_spond_section_or_variables(self, config_file):
        assert config.readconfig() is None

    def test_does_not_read_credentials_from_the_old_auth_section(self, config_file):
        config_file.write_text(_section("auth", CREDENTIALS))

        assert config.readconfig() is None

    def test_variable_supplies_a_credential_the_file_leaves_empty(
        self, config_file, monkeypatch
    ):
        config_file.write_text(_section("spond", {**FILE_SPOND, "password": ""}))
        monkeypatch.setenv("SPOND_PASSWORD", "from-env")

        assert _readconfig()["spond"] == {**FILE_SPOND, "password": "from-env"}


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

        assert cfg["spond"] == {
            "username": "env-user",
            "password": "env-pass",
            "group_id": "env-group",
            "include_hidden_events": True,
        }
        # Everything the bot reads without a fallback at startup or in a cycle.
        assert isinstance(logging.getLevelNamesMapping()[cfg["logging"]["level"]], int)
        assert cfg["general"]["seconds_to_sleep"] > 0
        assert isinstance(cfg["naco"]["enabled"], bool)
        assert cfg["naco"]["base_url"]
