import asyncio
import logging
from datetime import datetime, timedelta

from spond import spond

from .rules.rulebase import RuleBase, create_rule
from .utils import Event, Events, eventid_to_event, memberid_to_member


class PadelBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.spond = spond.Spond(cfg["auth"]["username"], cfg["auth"]["password"])

    async def _get_practices(
        self,
        min_start: datetime | None = None,
        max_start: datetime | None = None,
    ) -> list[Event]:
        events = (
            await self.spond.get_events(
                group_id=self.cfg["auth"]["group_id"],
                min_start=min_start,
                max_start=max_start,
            )
            or []
        )
        retval: list[Event] = []
        for event in events:
            if "practice" in event["heading"].lower():
                retval.append(event)
        return retval

    async def get_next_practices(self) -> list[Event]:
        logging.debug("Getting next practices")
        timestamp_now = datetime.now().astimezone()
        events = await self._get_practices(min_start=timestamp_now)
        # Events that have already completed but are in the same calendar day are included
        # Filter them out based on start time
        retval = []
        for event in events:
            startTimestamp = datetime.fromisoformat(event["startTimestamp"])
            if startTimestamp > datetime.now().astimezone():
                retval.append(event)
        logging.debug(f" -> Found {len(retval)} upcoming practices")
        return retval

    async def get_previous_practices(self) -> list[Event]:
        logging.debug("Getting previous practices")
        timestamp_now = datetime.now().astimezone()
        # Events that have already completed but are in the same calendar day are not included
        # unless we include tomorrow in the search. Then filter out any future events based
        # on end time.
        events = await self._get_practices(
            min_start=timestamp_now - timedelta(days=7),
            max_start=timestamp_now + timedelta(days=1),
        )
        retval = []
        for event in events:
            endTimestamp = datetime.fromisoformat(event["endTimestamp"])
            if endTimestamp < datetime.now().astimezone():
                retval.append(event)
        logging.debug(f" -> Found {len(retval)} previous practices")
        return retval

    def get_sleep_time(self, default_sleep_time: float, events: Events) -> float:
        # Identify next rule/quarantine end time. Must be in the future.
        all_rule_end_times = [
            dt for rule in self.get_rules(events) for dt in rule.expirationtimes()
        ]
        now = datetime.now().astimezone()
        next_rule_end_time = min(
            (dt for dt in all_rule_end_times if dt > now), default=None
        )
        seconds_to_sleep = default_sleep_time
        if next_rule_end_time:
            secs_to_quarantine_end = (next_rule_end_time - now).total_seconds()
            logging.debug(
                f"Next quarantine ends in {secs_to_quarantine_end} seconds (at {next_rule_end_time.astimezone().replace(tzinfo=None)})"
            )

            if (
                1 < secs_to_quarantine_end <= 60
            ):  # Aim for 1 second before, every 10 secs until then
                seconds_to_sleep = max(1, min(10, secs_to_quarantine_end - 1))
            else:  # Aim for 59 seconds before to enter interval above
                seconds_to_sleep = max(
                    1,
                    min(
                        default_sleep_time,
                        secs_to_quarantine_end - 59,
                    ),
                )
        return seconds_to_sleep

    async def remove_player_from_event(
        self,
        player_id: str,
        event_id: str,
        message: str,
        events: list[Event],
        enforced: bool = False,
    ) -> list[Event]:
        logging.info(f"Removing player ID {player_id} from event ID {event_id}")
        event = eventid_to_event(event_id, events)
        if not event:
            logging.error(f"Event ID {event_id} not found")
            return events

        player = memberid_to_member(
            player_id,
            event["recipients"]["group"]["members"],
        )
        if not player:
            logging.error(f"Player ID {player_id} not found in event ID {event_id}")
            return events

        logging.info(
            f'Removing player {player["firstName"]} {player["lastName"]} from event "{event["heading"]}" ({event["starttime"]})'
        )
        if enforced:
            await self.spond.change_response(event_id, player_id, {"accepted": "false"})
            await self.spond.send_message(
                text=message,
                user=player["profile"]["id"],
                group_uid=self.cfg["auth"]["group_id"],
            )
        return events

    def get_rules(self, events: Events) -> list[RuleBase]:
        rules = []
        for rule_name, rule_def in self.cfg["rules"].items():
            rule = create_rule(rule_name, events, rule_def)
            if not rule:
                logging.error(f'Skipping unsupported rule class "{rule_def["rule"]}"')
                continue
            rules.append(rule)
        return rules

    def update_events_with_removal(
        self, player_id: str, event_id: str, events: Events
    ) -> Events:
        updated_events = []
        for event in events.upcoming:
            if event["id"] == event_id:
                # Remove player_id from whichever group they are in
                for key in ("waitinglistIds", "acceptedIds"):
                    if player_id in event["responses"][key]:
                        event["responses"][key].remove(player_id)
                        break  # Player can only be in one group, so stop after removal
            updated_events.append(event)
        events.upcoming = updated_events
        return events

    async def run(self):
        upcoming_events = await self.get_next_practices()
        previous_events = await self.get_previous_practices()

        events = Events(previous=previous_events, ongoing=[], upcoming=upcoming_events)

        all_removals = []
        for rule in self.get_rules(events):
            removals = rule.evaluate()
            for removal in removals:
                # Update events so that subsequent rules see the to-be-updated state
                if removal.enforced:
                    events = self.update_events_with_removal(
                        removal.player_id, removal.event_id, events
                    )
            all_removals.extend(removals)

        for removal in all_removals:
            if removal.enforced:
                await self.remove_player_from_event(
                    player_id=removal.player_id,
                    event_id=removal.event_id,
                    message=removal.message,
                    events=upcoming_events,
                    enforced=removal.enforced,
                )

        seconds_to_sleep = self.get_sleep_time(
            self.cfg["general"]["seconds_to_sleep"], events
        )

        logging.debug(f"Sleeping for {seconds_to_sleep} seconds")
        await asyncio.sleep(seconds_to_sleep)
