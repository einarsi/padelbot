import logging
from datetime import datetime, timedelta
from typing import Any

from padelbot.utils import Event, get_last_practice_in_series, memberid_to_member

from .rulebase import RemovalInfo, RuleBase, RuleResult, register_rule


class RuleQuarantineAfterEvent(RuleBase):
    def __init__(
        self,
        event: dict[str, Any],
        quarantine_days: int,
        message: str,
        rule_name: str,
        enforced: bool = False,
    ) -> None:
        self.event = event
        self.quarantine_days = quarantine_days
        self.message = message
        self.name = rule_name
        self.enforced = enforced

    def isactive(self) -> bool:
        event_end = datetime.fromisoformat(self.event["endTimestamp"]).astimezone()
        now = datetime.now().astimezone()

        # Event is not in quarantine
        if now > event_end + timedelta(days=self.quarantine_days - 7):
            logging.debug(
                f'[{self.name}]: "{self.event["heading"]}" is not in quarantine'
            )
            return False

        logging.info(
            f'[{self.name}]: "{self.event["heading"]}" is in quarantine for players that played last time'
        )

        return True

    def enforce(self, last_events: list[Event]) -> RuleResult | None:
        player_ids: list[str] = (
            self.event["responses"]["acceptedIds"]
            + self.event["responses"]["waitinglistIds"]
        )
        registered_names = [
            f"{player['firstName']} {player['lastName']}"
            for pid in player_ids
            if (
                player := memberid_to_member(
                    pid, self.event["recipients"]["group"]["members"]
                )
            )
        ]
        logging.debug(
            f"[{self.name}]: Registered players: {', '.join(registered_names)}"
        )

        last_event = get_last_practice_in_series(self.event, last_events)

        if not last_event:
            logging.warning(
                f'[{self.name}]: No last event found for "{self.event["heading"]}". Skipping further processing.'
            )
            return None

        previous_player_ids = last_event["responses"]["acceptedIds"]

        result = RuleResult()

        for id in player_ids:
            if id in previous_player_ids:
                player = memberid_to_member(
                    id, last_event["recipients"]["group"]["members"]
                )
                if player:
                    logging.debug(
                        f'[{self.name}]: Scheduling {player["firstName"]} {player["lastName"]} for removal from "{self.event["heading"]}"'
                    )
                    # Merge self.event and player, ignoring duplicate keys (player takes precedence)
                    merged = {
                        **self.event,
                        **{k: v for k, v in player.items() if k not in self.event},
                    }
                    removalinfo = RemovalInfo(
                        player_id=id,
                        firstname=player["firstName"],
                        lastname=player["lastName"],
                        message=self.message.format(**merged),
                        event_heading=self.event["heading"],
                        event_starttime=datetime.fromisoformat(
                            self.event["startTimestamp"]
                        ).astimezone(),
                        enforced=self.enforced,
                    )
                    result.removals.append(removalinfo)

        event_end = datetime.fromisoformat(self.event["endTimestamp"]).astimezone()
        result.rule_end_time = event_end + timedelta(days=self.quarantine_days - 7)
        return result


register_rule("QuarantineAfterEvent", RuleQuarantineAfterEvent)
