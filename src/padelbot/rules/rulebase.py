import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..utils import Events, memberid_to_member


@dataclass
class RemovalInfo:
    player_id: str
    event_id: str
    message: str
    enforced: bool = False


class RuleBase(ABC):
    name: str = ""
    message: str = ""
    enforced: bool = False

    @abstractmethod
    def __init__(self, rule_name: str, events: Events, *args) -> None:
        pass

    @abstractmethod
    def evaluate(self) -> list[RemovalInfo]:
        pass

    @abstractmethod
    def expirationtimes(self) -> list[datetime]:
        pass

    def schedule_removal(self, id, event) -> RemovalInfo:
        player = memberid_to_member(id, event["recipients"]["group"]["members"])

        logging.debug(
            f'[{self.name}]: Scheduling {player["firstName"]} {player["lastName"]} for removal from "{event["heading"]}"'
        )
        # Merge self.event and player, ignoring duplicate keys (player takes precedence)
        merged = {
            **event,
            **{k: v for k, v in player.items() if k not in event},
        }
        removalinfo = RemovalInfo(
            player_id=id,
            event_id=event["id"],
            message=self.message.format(**merged),
            enforced=self.enforced,
        )
        return removalinfo


RULE_REGISTRY: dict[str, type[RuleBase]] = {}


def register_rule(rule_type: str, rule_class: type[RuleBase]) -> None:
    RULE_REGISTRY[rule_type] = rule_class


def create_rule(rule_name: str, events: Events, rule_def) -> RuleBase:
    rule_cls = RULE_REGISTRY.get(rule_def["type"])
    if not rule_cls:
        raise ValueError(f'Unknown rule type "{rule_def["type"]}" for {rule_name}')
    # Pass event and any additional rule_def parameters except 'type'
    rule_params = {k: v for k, v in rule_def.items() if k not in ("type",)}
    return rule_cls(rule_name, events, **rule_params)
