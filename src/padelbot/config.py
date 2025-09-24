import logging
import tomllib

from dotenv import dotenv_values

defaults = {
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


def readconfig():
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    env = dotenv_values(".env")
    config["auth"].update({k.lower(): v for k, v in env.items() if v is not None})

    config = {**defaults, **config}

    if not all(config["auth"].get(k) for k in ("username", "password", "group_id")):
        logging.error("username, password or group_id is missing. Bailing.")
        return

    return config
