import asyncio
import logging
import tomllib

import aiofiles

from padelbot.core.config import readconfig
from padelbot.core.logger import start_logger
from padelbot.padelbot import PadelBot

logger = logging.getLogger(__name__)


async def main():
    await start_logger()

    async with aiofiles.open("pyproject.toml", "rb") as f:
        data = tomllib.loads((await f.read()).decode())
    version = data["project"]["version"]

    logger.info(f"Starting padelbot v{version}")

    cfg = readconfig()
    if cfg is None:
        logger.error("Missing configuration")
        return

    logging.getLogger().setLevel(cfg["logging"]["level"])

    padelbot = PadelBot(cfg)

    while True:
        await padelbot.run()

    await padelbot.spond.clientsession.close()
    logger.info("Main complete")


if __name__ == "__main__":
    asyncio.run(main())
