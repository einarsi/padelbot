import asyncio
import logging
from datetime import datetime, timedelta
from logging import StreamHandler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

from dotenv import dotenv_values
from spond import spond


async def init_logger():
    log = logging.getLogger()
    que = Queue()
    log.addHandler(QueueHandler(que))
    log.setLevel(logging.DEBUG)
    listener = QueueListener(que, StreamHandler())
    try:
        listener.start()
        logging.debug("Logger initialized")
        while True:
            await asyncio.sleep(60)
    finally:
        logging.debug("Stopping logger")
        listener.stop()

LOGGER_TASK = None

async def start_logger():
    LOGGER_TASK = asyncio.create_task(init_logger())
    await asyncio.sleep(0)

async def _get_practices(
    s: spond.Spond,
    cfg: dict[str, str],
    min_start: datetime | None = None,
    max_start: datetime | None = None,
):
    events = await s.get_events(
        cfg["GROUP_ID"], min_start=min_start, max_start=max_start
    )
    retval = []
    for event in events:
        start_time = datetime.strptime(event["startTimestamp"], "%Y-%m-%dT%H:%M:%SZ")
        if start_time.weekday() in (0, 3) and (
            "Mondays" in event["heading"] or "Thursdays" in event["heading"]
        ):
            retval.append(event)
    return retval


async def get_next_practices(s: spond.Spond, cfg: dict[str, str]):
    events = await _get_practices(s, cfg, min_start=datetime.now())
    return events


async def get_previous_practices(s: spond.Spond, cfg: dict[str, str]):
    events = await _get_practices(
        s, cfg, min_start=datetime.now() - timedelta(days=7), max_start=datetime.now()
    )
    return events

async def main():
    await start_logger()
    logging.info("Starting main")
    cfg = dotenv_values(".env")
    s = spond.Spond(cfg["USERNAME"], cfg["PASSWORD"])
    next_practices = await get_next_practices(s, cfg)
    previous_practices = await get_previous_practices(s, cfg)

    for event in previous_practices:
        logging.info(f"Upcoming: {event['heading']}, {event['startTimestamp']}")
    for event in next_practices:
        logging.info(f"Previous: {event['heading']}, {event['startTimestamp']}")

    await s.clientsession.close()
    logging.info("Main complete")

if __name__ == "__main__":
    asyncio.run(main())

