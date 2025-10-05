import asyncio
import logging
import tomllib

from padelbot.core.config import readconfig
from padelbot.core.logger import start_logger
from padelbot.padelbot import PadelBot


async def main():
    await start_logger()

    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]

    logging.info(f"Starting padelbot v{version}")

    cfg = readconfig()
    if cfg is None:
        logging.error("Missing configuration")
        return

    logging.getLogger().setLevel(cfg["logging"]["level"])

    padelbot = PadelBot(cfg)

    while True:
        await padelbot.run()

    await padelbot.spond.clientsession.close()
    logging.info("Main complete")


if __name__ == "__main__":
    asyncio.run(main())
