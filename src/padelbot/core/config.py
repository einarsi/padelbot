import logging
import os
import tomllib
from typing import Any

from dotenv import load_dotenv

defaults: dict[str, Any] = {
    "auth": {
        "username": "your_username",
        "password": "your_password",
        "group_id": "your_group_id",
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


def readconfig() -> dict[str, Any] | None:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    # Load .env file into os.environ (won't override existing env vars)
    load_dotenv()

    for key in ("USERNAME", "PASSWORD", "GROUP_ID"):
        if value := os.environ.get(f"SPOND_{key}"):
            config["auth"][key.lower()] = value

    for key in ("BASE_URL", "API_KEY"):
        if value := os.environ.get(f"NACO_{key}"):
            config.setdefault("naco", {})[key.lower()] = value

    if value := os.environ.get("NACO_ENABLED"):
        config.setdefault("naco", {})["enabled"] = value.lower() in ("1", "true", "yes")

    config = {**defaults, **config}

    if not all(config["auth"].get(k) for k in ("username", "password", "group_id")):
        logging.error("username, password or group_id is missing. Bailing.")
        return None

    return config
