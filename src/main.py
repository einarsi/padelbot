import asyncio
import logging
from datetime import datetime, timedelta
from datetime import timezone as tz

from async_lru import alru_cache
from spond import spond

from padelbot.config import readconfig
from padelbot.logger import start_logger


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
    logging.debug(f" -> Found {len(retval)} upcoming practices")
    return retval

@alru_cache(ttl=3600)
async def get_previous_practices(s: spond.Spond, group_id: str):
    logging.debug("Getting previous practices")
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
    logging.debug(f" -> Found {len(retval)} previous practices")
    return retval   

async def periodic(interval: int, coro, result_queue: asyncio.Queue, *args, **kwargs):
    while True:
        res = await coro(*args, **kwargs)
        await result_queue.put(res)
        await asyncio.sleep(interval)

async def get_last_practice_in_series(s: spond.Spond, group_id: str, event: dict) -> dict | None:
    events = await get_previous_practices(s, group_id)
    start_time = datetime.strptime(event["startTimestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)

    for previous_event in events:
        # Keep it simple: If startTimestamp was exactly 7 days before, it is in the same series
        previous_start_time = datetime.strptime(previous_event["startTimestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)
        if (start_time- previous_start_time).days == 7 and (start_time-previous_start_time).seconds == 0:
            return previous_event
    return None

def memberid_to_member(member_id: str, members: list[dict]) -> dict | None:
    for member in members:
        if member["id"] == member_id:
            return member
    return None

async def quarantine_players_from_last_event(s: spond.Spond, group_id: str, event: dict, quarantine_days: int = 1) -> datetime | None:
        event_end = datetime.strptime(event["endTimestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)
        now = datetime.now(tz.utc)
        logging.debug(f"Event ends at {event_end}, now is {now}")
        if (event_end - now).days < (7 - quarantine_days):
            return None
        logging.info(f"\"{event['heading']}\" is in quarantine for players that played last time")
        last_event = await get_last_practice_in_series(s, group_id, event)
        if not last_event:
            logging.info(f" -> No last event found for \"{event['heading']}\". Skipping further processing.")
            return None
        previous_player_ids = last_event["responses"]["acceptedIds"]
        player_ids = event["responses"]["acceptedIds"]
        for id in player_ids:
            if id in previous_player_ids:
                player = memberid_to_member(id, last_event["recipients"]["group"]["members"])
                if player:
                    logging.info(f"Player {player['firstName']} {player['lastName']} played last time, removing from this event")
                    # await s.change_response(event["id"], player["id"], {"accepted": "false"})
                    # await s.send_message(f"You were removed from the event \"{event['heading']}\" because you played last time. Please wait for at least 24 hours after the event ended before signing up.", user=player["profile"]["id"], group_uid=group_id)
        return event_end - timedelta(days=7-quarantine_days)

async def main():
    await start_logger()

    logging.info("Starting main")
    
    cfg = readconfig()
    if cfg is None:
        logging.error("Missing configuration")
        return
    username = cfg["AUTH"]["USERNAME"]
    password = cfg["AUTH"]["PASSWORD"]
    group_id = cfg["AUTH"]["GROUP_ID"]

    if cfg["LOGGING"]["LEVEL"] is None:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(cfg["LOGGING"]["LEVEL"])

    s = spond.Spond(username, password)

    while True:
        next_quarantine_end_time = None
        upcoming_events = await get_next_practices(s, group_id)
        if upcoming_events:
            for event in reversed(upcoming_events):
                logging.debug(f"Handling {event['startTimestamp']} \"{event['heading']}\"")
                quarantine_ends = await quarantine_players_from_last_event(s, group_id, event)
                if quarantine_ends is not None and (next_quarantine_end_time is None or quarantine_ends < next_quarantine_end_time):
                    next_quarantine_end_time = quarantine_ends

        seconds_to_sleep = 900
        
        if next_quarantine_end_time is not None:
            seconds_to_next_quarantine_end = (next_quarantine_end_time - datetime.now(tz.utc)).seconds
            seconds_to_sleep = min(max(1, seconds_to_next_quarantine_end-2), seconds_to_sleep)
            logging.debug(f"Next quarantine ends at {next_quarantine_end_time}.")
        logging.debug(f"Sleeping for {seconds_to_sleep} seconds")
        await asyncio.sleep(seconds_to_sleep)

    await s.clientsession.close()
    logging.info("Main complete")

if __name__ == "__main__":
    asyncio.run(main())
