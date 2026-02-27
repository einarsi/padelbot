import logging
import re
from datetime import datetime, timedelta

from ..utils import (
    Event,
    Events,
    get_last_event_from_timestamp_and_title,
    get_last_event_in_series,
    get_registered_player_names,
)
from .rulebase import RemovalInfo, RuleBase, register_rule


class RuleQuarantineAfterEvent(RuleBase):
    def __init__(
        self,
        rule_name: str,
        events: Events,
        header_regex: str,
        message: str,
        enforced: bool = False,
        quarantine_hours: int = 24,
    ) -> None:
        self.name = rule_name
        self.events = events
        self.header_regex = header_regex
        self.message = message
        self.enforced = enforced
        self.quarantine_hours = quarantine_hours

    def _include(self, event: Event) -> bool:
        if not re.search(self.header_regex, event["heading"]):
            return False
        return True

    def _get_last_similar_event(self, event: Event) -> Event | None:
        last_event = get_last_event_in_series(event, self.events.previous)
        if not last_event:
            last_event = get_last_event_from_timestamp_and_title(
                event, self.events.previous
            )
        return last_event

    def _get_last_event_endtime(self, event: Event) -> datetime | None:
        last_event = self._get_last_similar_event(event)
        if not last_event:
            return None
        return datetime.fromisoformat(last_event["endTimestamp"]).astimezone()

    def _isactive(self, event: Event) -> bool:
        if not self._include(event):
            return False
        last_event_end = self._get_last_event_endtime(event)
        if not last_event_end:
            return False

        if datetime.now().astimezone() > last_event_end + timedelta(
            hours=self.quarantine_hours
        ):
            return False
        return True

    def expirationtimes(self) -> list[datetime]:
        result: list[datetime] = []
        for event in self.events.upcoming:
            if (
                self._include(event)
                and self._isactive(event)
                and (last_event_end := self._get_last_event_endtime(event))
            ):
                result.append(last_event_end + timedelta(hours=self.quarantine_hours))
        return result

    def evaluate(self) -> list[RemovalInfo]:
        removals: list[RemovalInfo] = []

        for event in self.events.upcoming:
            if not self._include(event):
                continue

            logging.debug(f'[{self.name}]: Processing event "{event["heading"]}"')

            if not self._isactive(event):
                continue

            logging.info(
                f'[{self.name}]: "{event["heading"]}" is in quarantine for players that played last time'
            )

            player_ids: list[str] = (
                event["responses"]["acceptedIds"] + event["responses"]["waitinglistIds"]
            )

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                registered_names = get_registered_player_names(event)
                logging.debug(
                    f"[{self.name}]: Registered players: {', '.join(registered_names)}"
                )

            last_event = get_last_event_in_series(event, self.events.previous)
            if not last_event:
                last_event = get_last_event_from_timestamp_and_title(
                    event, self.events.previous
                )
                if last_event:
                    logging.warning(
                        f"[{self.name}]: Found last similar event by timestamp and title: {last_event['heading']} at {last_event['startTimestamp']}"
                    )
            if not last_event:
                logging.warning(
                    f'[{self.name}]: No last event found for "{event["heading"]}". Skipping further processing.'
                )
                continue
            logging.debug(
                f"[{self.name}]: Last event in series was {datetime.fromisoformat(last_event['startTimestamp']).astimezone()}"
            )

            previous_player_ids = last_event["responses"]["acceptedIds"]

            for id in player_ids:
                if id in previous_player_ids:
                    removalinfo = self.schedule_removal(id, event)
                    removals.append(removalinfo)
        return removals


register_rule("QuarantineAfterEvent", RuleQuarantineAfterEvent)
