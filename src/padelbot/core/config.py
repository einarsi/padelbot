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
    "rules": {},
}


def readconfig() -> dict[str, Any] | None:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    # Load .env file into os.environ (won't override existing env vars)
    load_dotenv()

    for key in ("USERNAME", "PASSWORD", "GROUP_ID"):
        if value := os.environ.get(f"SPOND_{key}"):
            config["auth"][key.lower()] = value

    config = {**defaults, **config}

    if not all(config["auth"].get(k) for k in ("username", "password", "group_id")):
        logging.error("username, password or group_id is missing. Bailing.")
        return None

    return config
