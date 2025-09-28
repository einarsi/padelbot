import logging
from datetime import datetime, timedelta

from padelbot.utils import (
    Event,
    Events,
    get_registered_player_names,
    memberid_to_member,
)

from .rulebase import RemovalInfo, RuleBase, register_rule


class RuleMaxEventsPerWeek(RuleBase):
    def __init__(
        self,
        rule_name: str,
        events: Events,
        message: str,
        enforced: bool = False,
        max_events: int = 1,
        grace_hours: int = 24,
    ) -> None:
        self.name = rule_name
        self.events = events
        self.message = message
        self.enforced = enforced
        self.max_events = max(0, max_events)
        self.grace_hours = grace_hours

    def _include(self, event: Event) -> bool:
        event_start = datetime.fromisoformat(event["startTimestamp"]).astimezone()
        now = datetime.now().astimezone()

        # Event is not in grace period
        if now > event_start - timedelta(hours=self.grace_hours):
            return False
        return True

    def expirationtimes(self) -> list[datetime]:
        result: list[datetime] = []
        for event in self.events.upcoming:
            event_start = datetime.fromisoformat(event["startTimestamp"]).astimezone()
            result.append(event_start - timedelta(hours=self.grace_hours))
        return result

    def evaluate(self) -> list[RemovalInfo]:
        player_events: dict[str, list[Event]] = {}

        for event in self.events.upcoming:
            if not self._include(event):
                continue

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'[{self.name}]: Processing "{event["heading"]}"')
                registered_names = get_registered_player_names(event)
                logging.debug(
                    f"[{self.name}]: -> Registered players: {', '.join(registered_names)}"
                )

            for player_id in (
                event["responses"]["acceptedIds"] + event["responses"]["waitinglistIds"]
            ):
                if player_id not in player_events:
                    player_events[player_id] = []
                player_events[player_id].append(event)

        for player_id, events in player_events.items():
            if len(events) > self.max_events:
                player = memberid_to_member(
                    player_id, events[0]["recipients"]["group"]["members"]
                )
                if player:
                    logging.debug(
                        f"[{self.name}]: {player['firstName']} {player['lastName']} is signed up for {len(events)} > {self.max_events} events."
                    )

        removals: list[RemovalInfo] = []
        for player_id, events in player_events.items():
            events.sort(
                key=lambda e: datetime.fromisoformat(e["startTimestamp"]).astimezone(),
                reverse=True,
            )
            num_events = len(events)
            # Remove from waitinglists first, then accepted, until max_events is reached
            for key in ("waitinglistIds", "acceptedIds"):
                for event in events:
                    if num_events <= self.max_events:
                        break
                    if player_id in event["responses"][key]:
                        removalinfo = self.schedule_removal(player_id, event)
                        removals.append(removalinfo)
                        num_events -= 1
                if num_events <= self.max_events:
                    break
        return removals


register_rule("MaxEventsPerWeek", RuleMaxEventsPerWeek)
