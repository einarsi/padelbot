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
        self.first_run = True

    async def get_events(self) -> Events:
        timestamp_now = datetime.now().astimezone()
        min_start = timestamp_now - timedelta(days=7)
        events = (
            await self.spond.get_events(
                group_id=self.cfg["auth"]["group_id"],
                min_start=min_start,
                max_start=None,
            )
            or []
        )
        timestamp_now = datetime.now().astimezone()
        retval = Events()
        for event in events:
            startTimestamp = datetime.fromisoformat(event["startTimestamp"])
            endTimestamp = datetime.fromisoformat(event["endTimestamp"])
            if startTimestamp > datetime.now().astimezone():
                retval.upcoming.append(event)
            elif endTimestamp < datetime.now().astimezone():
                retval.previous.append(event)
            else:
                retval.ongoing.append(event)

        logging.debug(
            f"Found {len(retval.upcoming)} upcoming, {len(retval.previous)} previous and {len(retval.ongoing)} ongoing events"
        )
        return retval

    def get_rules(self, events: Events) -> list[RuleBase]:
        rules = []
        for rule_name, rule_def in self.cfg["rules"].items():
            rule = create_rule(rule_name, events, rule_def)
            if not rule:
                logging.error(f'Skipping unsupported rule class "{rule_def["rule"]}"')
                continue
            rules.append(rule)
        return rules

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

    async def remove_player_from_event(
        self,
        player_id: str,
        event_id: str,
        message: str,
        events: list[Event],
        enforce: bool = False,
    ) -> bool:
        event = eventid_to_event(event_id, events)
        if not event:
            logging.error(f"Event ID {event_id} not found")
            return False

        player = memberid_to_member(
            player_id,
            event["recipients"]["group"]["members"],
        )

        logging.info(
            f'{"Removing" if enforce else "Not enforcing removal of"} player {player["firstName"]} {player["lastName"]} from event "{event["heading"]}" ({event["startTimestamp"]})'
        )
        if enforce:
            await self.spond.change_response(event_id, player_id, {"accepted": "false"})
            await self.spond.send_message(
                text=message,
                user=player["profile"]["id"],
                group_uid=self.cfg["auth"]["group_id"],
            )
        return True

    async def run(self):
        events = await self.get_events()

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
            await self.remove_player_from_event(
                player_id=removal.player_id,
                event_id=removal.event_id,
                message=removal.message,
                events=events.upcoming,
                enforce=removal.enforced and not self.first_run,
            )

        self.first_run = False

        seconds_to_sleep = self.get_sleep_time(
            self.cfg["general"]["seconds_to_sleep"], events
        )

        logging.debug(f"Sleeping for {seconds_to_sleep} seconds")
        await asyncio.sleep(seconds_to_sleep)
