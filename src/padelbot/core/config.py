import logging
import os
import tomllib
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

defaults: dict[str, Any] = {
    "auth": {
        "username": "",
        "password": "",
        "group_id": "",
    },
    "logging": {
        "level": "INFO",
    },
    "general": {
        "seconds_to_sleep": 600,
        "include_hidden_events": True,
    },
    "naco": {
        "enabled": False,
        "base_url": "http://localhost:8000",
        "api_key": "",
    },
    "rules": {},
    "actions": {},
}


def readconfig() -> dict[str, Any] | None:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    # Fill in defaults per key, so a section that sets only some keys keeps the rest
    for name, section in defaults.items():
        config[name] = {**section, **config.get(name, {})}

    # Load .env file into os.environ (won't override existing env vars)
    load_dotenv()

    for key in ("USERNAME", "PASSWORD", "GROUP_ID"):
        if value := os.environ.get(f"SPOND_{key}"):
            config["auth"][key.lower()] = value

    for key in ("BASE_URL", "API_KEY"):
        if value := os.environ.get(f"NACO_{key}"):
            config["naco"][key.lower()] = value

    if value := os.environ.get("NACO_ENABLED"):
        config["naco"]["enabled"] = value.lower() in ("1", "true", "yes")

    if not all(config["auth"].get(k) for k in ("username", "password", "group_id")):
        logger.error("username, password or group_id is missing. Bailing.")
        return None

    return config
