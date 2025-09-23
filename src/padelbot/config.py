import logging
import tomllib

from dotenv import dotenv_values

defaults = {
    "AUTH": {
        "USERNAME": "your_username",
        "PASSWORD": "your_password",
        "GROUP_ID": "your_group_id",
    },
    "LOGGING": {
        "LEVEL": "INFO",
    },
    "GENERAL": {
        "SECONDS_TO_SLEEP": 600,
    },
    "RULES": {
        "QUARANTINE_DAYS": 1,
    },
}


def readconfig():
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    env = dotenv_values(".env")
    config["AUTH"].update({k: v for k, v in env.items() if v is not None})

    config = {**defaults, **config}

    if not all(config["AUTH"].get(k) for k in ("USERNAME", "PASSWORD", "GROUP_ID")):
        logging.error("USERNAME, PASSWORD or GROUP_ID is missing. Bailing.")
        return

    return config
