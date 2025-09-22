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
        start_time = datetime.fromisoformat(event["startTimestamp"])
        if start_time.weekday() in (0, 3) and (
            "Mondays" in event["heading"] or "Thursdays" in event["heading"]
        ):
            retval.append(event)
    return retval


async def get_next_practices(s: spond.Spond, group_id: str):
    logging.debug("Getting next practices")
    timestamp_now = datetime.now().astimezone()
    events = await _get_practices(s, group_id=group_id, min_start=timestamp_now)
    # Events that have already completed but are in the same calendar day are included
    # Filter them out based on start time
    retval = []
    for event in events:
        startTimestamp = datetime.fromisoformat(event["startTimestamp"])
        if startTimestamp > datetime.now().astimezone():
            retval.append(event)
    logging.debug(f" -> Found {len(retval)} upcoming practices")
    return retval

@alru_cache(ttl=3600)
async def get_previous_practices(s: spond.Spond, group_id: str):
    logging.debug("Getting previous practices")
    timestamp_now = datetime.now().astimezone()
    # Events that have already completed but are in the same calendar day are not included
    # unless we include tomorrow in the search. Then filter out any future events based
    # on end time.
    events = await _get_practices(
        s, group_id=group_id, min_start=timestamp_now - timedelta(days=7), max_start=timestamp_now+timedelta(days=1)
    )
    retval = []
    for event in events:
        endTimestamp = datetime.fromisoformat(event["endTimestamp"])
        if endTimestamp < datetime.now().astimezone():
            retval.append(event)
    logging.debug(f" -> Found {len(retval)} previous practices")
    return retval   

async def get_last_practice_in_series(s: spond.Spond, group_id: str, event: dict) -> dict | None:
    events = await get_previous_practices(s, group_id)
    start_time = datetime.fromisoformat(event["startTimestamp"])

    for previous_event in events:
        # Keep it simple: If startTimestamp was exactly 7 days before, +/- 5 minutes, it is in the same series.
        # Times are timezoned, so no DST issues.
        previous_start_time = datetime.fromisoformat(previous_event["startTimestamp"])
        if abs((start_time - previous_start_time).total_seconds() - 7*24*60*60) <= 5*60:
            return previous_event
    return None

def memberid_to_member(member_id: str, members: list[dict]) -> dict | None:
    for member in members:
        if member["id"] == member_id:
            return member
    return None

async def quarantine_players_from_last_event(s: spond.Spond, group_id: str, event: dict, quarantine_days: int = 1) -> datetime | None:
        event_end = datetime.fromisoformat(event["endTimestamp"]).astimezone()
        now = datetime.now().astimezone()
        logging.debug(f"Event ends at {event_end.replace(tzinfo=None)}, now is {now.replace(tzinfo=None)}")

        # Event is not in quarantine
        if now > event_end + timedelta(days=quarantine_days-7):
            return None

        # In case fetching the event information was initiated shortly before quarantine expiry, but took too long
        if now > event_end:
            logging.info(f" -> Quarantine is already over ({now}). Skipping further processing.")
            return None

        logging.info(f"\"{event['heading']}\" is in quarantine for players that played last time")

        player_ids = event["responses"]["acceptedIds"] + event["responses"]["waitinglistIds"]
        registered_names = [
            f"{player['firstName']} {player['lastName']}"
            for pid in player_ids
            if (player := memberid_to_member(pid, event["recipients"]["group"]["members"]))
        ]
        logging.debug(f" -> Registered players: {', '.join(registered_names)}")

        last_event = await get_last_practice_in_series(s, group_id, event)
        if not last_event:
            logging.warning(f" -> No last event found for \"{event['heading']}\". Skipping further processing.")
            return None

        previous_player_ids = last_event["responses"]["acceptedIds"]
        for id in player_ids:
            if id in previous_player_ids:
                player = memberid_to_member(id, last_event["recipients"]["group"]["members"])
                if player:
                    logging.info(f"Player {player['firstName']} {player['lastName']} played last time, removing from this event")
                    # await s.change_response(event["id"], player["id"], {"accepted": "false"})
                    # await s.send_message(f"You were removed from the event \"{event['heading']}\" because you played last time. Please wait for at least 24 hours after the event ended before signing up.", user=player["profile"]["id"], group_uid=group_id)
        return event_end + timedelta(days=quarantine_days-7)

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
        upcoming_events = await get_next_practices(s, group_id)

        quarantine_end_times = []
        if upcoming_events:
            for event in reversed(upcoming_events):
                logging.debug(f"Handling {datetime.fromisoformat(event['startTimestamp']).astimezone().replace(tzinfo=None)} \"{event['heading']}\"")
                quarantine_end_time = await quarantine_players_from_last_event(s, group_id, event)
                if quarantine_end_time is not None:
                    quarantine_end_times.append(quarantine_end_time)

        # Identify next quarantine end time. Must be in the future.
        now = datetime.now().astimezone()
        next_quarantine_end_time = min((dt for dt in quarantine_end_times if dt > now), default=None)

        seconds_to_sleep = 600
        if next_quarantine_end_time:
            seconds_to_next_quarantine_end_time = (next_quarantine_end_time - now).total_seconds()
            logging.debug(f"Next quarantine ends in {seconds_to_next_quarantine_end_time} seconds (at {next_quarantine_end_time.astimezone().replace(tzinfo=None)})")

            if 1 < seconds_to_next_quarantine_end_time <= 60: # Aim for 1 second before, every 10 secs until then
                seconds_to_sleep = min(10, seconds_to_next_quarantine_end_time - 1)
            else: # Aim for 59 seconds before to enter interval above
                seconds_to_sleep = min(600, seconds_to_next_quarantine_end_time - 59)
            
        logging.debug(f"Sleeping for {seconds_to_sleep} seconds")
        await asyncio.sleep(seconds_to_sleep)

    await s.clientsession.close()
    logging.info("Main complete")

if __name__ == "__main__":
    asyncio.run(main())
