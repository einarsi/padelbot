import logging
import os
import tomllib
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

defaults: dict[str, Any] = {
    "spond": {
        "username": "",
        "password": "",
        "group_id": "",
        "include_hidden_events": True,
    },
    "logging": {
        "level": "INFO",
    },
    "general": {
        "seconds_to_sleep": 600,
    },
    "naco": {
        "enabled": False,
        "base_url": "http://localhost:8000",
        "api_key": "",
    },
    "rules": {},
    "actions": {},
}


def _is_true(value: str) -> bool:
    return value.lower() in ("1", "true", "yes")


def readconfig() -> dict[str, Any] | None:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    # Fill in defaults per key, so a section that sets only some keys keeps the rest
    for name, section in defaults.items():
        config[name] = {**section, **config.get(name, {})}

    # Load .env file into os.environ (won't override existing env vars)
    load_dotenv()

    # SPOND_<KEY> and NACO_<KEY> override <key> in the [spond] and [naco] sections
    for key in ("USERNAME", "PASSWORD", "GROUP_ID"):
        if value := os.environ.get(f"SPOND_{key}"):
            config["spond"][key.lower()] = value

    if value := os.environ.get("SPOND_INCLUDE_HIDDEN_EVENTS"):
        config["spond"]["include_hidden_events"] = _is_true(value)

    for key in ("BASE_URL", "API_KEY"):
        if value := os.environ.get(f"NACO_{key}"):
            config["naco"][key.lower()] = value

    if value := os.environ.get("NACO_ENABLED"):
        config["naco"]["enabled"] = _is_true(value)

    if not all(config["spond"].get(k) for k in ("username", "password", "group_id")):
        logger.error("username, password or group_id is missing. Bailing.")
        return None

    return config
