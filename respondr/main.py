import asyncio
import logging
from datetime import datetime, timedelta
from datetime import timezone as tz

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
        start_time = datetime.strptime(event["startTimestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)
        if start_time.weekday() in (0, 3) and (
            "Mondays" in event["heading"] or "Thursdays" in event["heading"]
        ):
            retval.append(event)
    return retval


async def get_next_practices(s: spond.Spond, group_id: str):
    logging.debug("Getting next practices")
    timestamp_now = datetime.now(tz.utc)
    events = await _get_practices(s, group_id=group_id, min_start=timestamp_now)
    # Events that have already completed but are in the same calendar day are included
    # Filter them out based on start time
    retval = []
    for event in events:
        startTimestamp = datetime.strptime(event["startTimestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)
        if startTimestamp > datetime.now(tz.utc):
            retval.append(event)
    return retval


async def get_previous_practices(s: spond.Spond, group_id: str):
    timestamp_now = datetime.now(tz.utc)
    # Events that have already completed but are in the same calendar day are not included
    # unless we include tomorrow in the search. Then filter out any future events based
    # on end time.
    events = await _get_practices(
        s, group_id=group_id, min_start=timestamp_now - timedelta(days=7), max_start=timestamp_now+timedelta(days=1)
    )
    retval = []
    for event in events:
        endTimestamp = datetime.strptime(event["endTimestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)
        if endTimestamp < datetime.now(tz.utc):
            retval.append(event)
    return retval   

async def periodic(interval: int, coro, result_queue: asyncio.Queue, *args, **kwargs):
    while True:
        res = await coro(*args, **kwargs)
        await result_queue.put(res)
        await asyncio.sleep(interval)

async def main():
    await start_logger()
    upcoming_queue = asyncio.Queue()

    logging.info("Starting main")
    cfg = dotenv_values(".env")
    username = cfg.get("USERNAME")
    password = cfg.get("PASSWORD")
    group_id = cfg.get("GROUP_ID")
    if username is None or password is None or group_id is None:
        logging.error("USERNAME, PASSWORD or GROUP_ID is None. Bailing.")
        return
    
    s = spond.Spond(username, password)
    _task_upcoming = asyncio.create_task(periodic(10, get_next_practices, upcoming_queue, s, group_id))
    while True:
            try:
                upcoming_events = await asyncio.wait_for(upcoming_queue.get(), timeout=1)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logging.error(f"Error occurred while fetching upcoming events: {e}")
            else:
                logging.debug(f"Found {len(upcoming_events)} upcoming events")
                for event in upcoming_events:
                    logging.debug(f"-> {event['startTimestamp']} \"{event['heading']}\"")
                upcoming_queue.task_done()          

    await s.clientsession.close()
    logging.info("Main complete")

if __name__ == "__main__":
    asyncio.run(main())
