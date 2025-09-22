import configparser
import logging

from dotenv import dotenv_values


def readconfig():
    config = configparser.ConfigParser()
    config.read("config.ini")
    env = dotenv_values(".env")
    config["AUTH"].update({k: v for k, v in env.items() if v is not None})

    if not all(config["AUTH"].get(k) for k in ("USERNAME", "PASSWORD", "GROUP_ID")):
        logging.error("USERNAME, PASSWORD or GROUP_ID is missing. Bailing.")
        return

    return config
