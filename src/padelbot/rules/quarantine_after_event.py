import logging
import re
from datetime import datetime, timedelta

from ..utils import Event, Events, get_last_event_in_series, get_registered_player_names
from .rulebase import RemovalInfo, RuleBase, register_rule


class RuleQuarantineAfterEvent(RuleBase):
    def __init__(
        self,
        rule_name: str,
        events: Events,
        header_regex: str,
        message: str,
        enforced: bool = False,
        quarantine_days: int = 1,
    ) -> None:
        self.name = rule_name
        self.events = events
        self.header_regex = header_regex
        self.message = message
        self.enforced = enforced
        self.quarantine_days = quarantine_days

    def _include(self, event: Event) -> bool:
        if not re.search(self.header_regex, event["heading"]):
            return False
        return True

    def _isactive(self, event: Event) -> bool:
        event_end = datetime.fromisoformat(event["endTimestamp"]).astimezone()
        now = datetime.now().astimezone()

        # Event is not in quarantine
        if now > event_end + timedelta(days=self.quarantine_days - 7):
            return False
        return True

    def expirationtimes(self) -> list[datetime]:
        result: list[datetime] = []
        for event in self.events.upcoming:
            # Do not include quarantine expiration if there was no previous event in series.
            if (
                self._include(event)
                and self._isactive(event)
                and get_last_event_in_series(event, self.events.previous)
            ):
                event_end = datetime.fromisoformat(event["endTimestamp"]).astimezone()
                result.append(event_end + timedelta(days=self.quarantine_days - 7))
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
