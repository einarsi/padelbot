import asyncio
import logging
from datetime import datetime, timedelta

from dotenv import dotenv_values
from logger import start_logger
from spond import spond


async def _get_practices(
    s: spond.Spond,
    group_id: str,
    min_start: datetime | None = None,
    max_start: datetime | None = None,
):
    events = await s.get_events(group_id=group_id, min_start=min_start, max_start=max_start) or []
    retval = []
    for event in events:
        start_time = datetime.strptime(event["startTimestamp"], "%Y-%m-%dT%H:%M:%SZ")
        if start_time.weekday() in (0, 3) and (
            "Mondays" in event["heading"] or "Thursdays" in event["heading"]
        ):
            retval.append(event)
    return retval


async def get_next_practices(s: spond.Spond, group_id: str):
    events = await _get_practices(s, group_id=group_id, min_start=datetime.now())
    return events


async def get_previous_practices(s: spond.Spond, group_id: str):
    events = await _get_practices(
        s, group_id=group_id, min_start=datetime.now() - timedelta(days=7), max_start=datetime.now()
    )
    return events

async def main():
    await start_logger()
    logging.info("Starting main")
    cfg = dotenv_values(".env")
    username = cfg.get("USERNAME")
    password = cfg.get("PASSWORD")
    group_id = cfg.get("GROUP_ID")
    if username is None or password is None or group_id is None:
        logging.error("USERNAME, PASSWORD or GROUP_ID is None. Bailing.")
        return
    
    s = spond.Spond(username, password)
    next_practices = await get_next_practices(s, group_id)
    previous_practices = await get_previous_practices(s, group_id)

    for event in previous_practices:
        logging.info(f"Upcoming: {event['heading']}, {event['startTimestamp']}")
    for event in next_practices:
        logging.info(f"Previous: {event['heading']}, {event['startTimestamp']}")

    await s.clientsession.close()
    logging.info("Main complete")

if __name__ == "__main__":
    asyncio.run(main())
