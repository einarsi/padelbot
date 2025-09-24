import asyncio
import logging
from datetime import datetime, timedelta

from async_lru import alru_cache
from spond import spond

from .rulesets import RuleQuarantineAfterEvent, RuleResult  # noqa: F401
from .utils import Event, memberid_to_member


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
            start_time = datetime.fromisoformat(event["startTimestamp"])
            if start_time.weekday() in (0, 3) and (
                "Mondays" in event["heading"] or "Thursdays" in event["heading"]
            ):
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

    @alru_cache(ttl=3600)
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

    async def get_last_practice_in_series(self, event: dict) -> dict | None:
        events = await self.get_previous_practices()
        start_time = datetime.fromisoformat(event["startTimestamp"])

        for previous_event in events:
            # Keep it simple: If startTimestamp was exactly 7 days before, +/- 5 minutes, it is in the same series.
            # Times are timezoned, so no DST issues.
            previous_start_time = datetime.fromisoformat(
                previous_event["startTimestamp"]
            )
            if (
                abs(
                    (start_time - previous_start_time).total_seconds()
                    - 7 * 24 * 60 * 60
                )
                <= 5 * 60
            ):
                return previous_event
        return None

    def get_rule(self, rule_name: str, rule_def: dict, event: dict):
        rule_class = rule_def["class"]

        # Dynamically import and instantiate rule classes by name
        try:
            rule_class_obj = globals()[rule_class]
        except KeyError:
            return None

        # Pass event and any additional rule_def parameters except 'class'
        rule_params = {k: v for k, v in rule_def.items() if k not in ("class",)}
        rule_params["rule_name"] = rule_name
        rule = rule_class_obj(event, **rule_params)

        return rule

    async def handle_event(self, event: dict) -> list[datetime]:
        logging.debug(
            f'Handling {datetime.fromisoformat(event["startTimestamp"]).astimezone().replace(tzinfo=None)} "{event["heading"]}"'
        )

        results: list[RuleResult] = []
        for rule_name, rule_def in self.cfg["rules"].items():
            rule = self.get_rule(rule_name, rule_def, event)
            if not rule:
                logging.error(f'Skipping unsupported rule class "{rule_def["rule"]}"')
                continue

            if not rule.isactive():
                continue

            last_events = await self.get_previous_practices()
            result = rule.enforce(last_events)

            if result is not None:
                results.append(result)

        for result in results:
            for removal in result.removals:
                player = memberid_to_member(
                    removal.player_id, event["recipients"]["group"]["members"]
                )
                if player:
                    logging.info(
                        f'Removing player {removal.firstname} {removal.lastname} from event "{removal.event_heading}" ({removal.event_starttime})'
                    )
                    if removal.enforced:
                        logging.info("I'D ACTUALLY DO THIS!!!")
                    # await self.spond.change_response(
                    #     event["id"], player["id"], {"accepted": "false"}
                    # )
                    # await self.spond.send_message(
                    #     result.message.format(event=event),
                    #     user=player["profile"]["id"],
                    #     group_uid=self.cfg["auth"]["group_id"],
                    # )
        rules_end_times = [
            result.rule_end_time for result in results if result.rule_end_time
        ]
        return rules_end_times

    def get_sleep_time(self, all_rule_end_times: list[datetime]) -> float:
        # Identify next quarantine end time. Must be in the future.
        now = datetime.now().astimezone()
        next_rule_end_time = min(
            (dt for dt in all_rule_end_times if dt > now), default=None
        )
        seconds_to_sleep = self.cfg["general"]["seconds_to_sleep"]
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
                        self.cfg["general"]["seconds_to_sleep"],
                        secs_to_quarantine_end - 59,
                    ),
                )
        return seconds_to_sleep

    async def run(self):
        upcoming_events = await self.get_next_practices()

        all_rules_end_times = []
        for event in reversed(upcoming_events):
            event_rules_end_times = await self.handle_event(event)
            all_rules_end_times.extend(event_rules_end_times)

        seconds_to_sleep = self.get_sleep_time(all_rules_end_times)

        logging.debug(f"Sleeping for {seconds_to_sleep} seconds")
        await asyncio.sleep(seconds_to_sleep)
