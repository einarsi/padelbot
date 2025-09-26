from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from padelbot.utils import Event


@dataclass
class RemovalInfo:
    player_id: str
    firstname: str
    lastname: str
    message: str
    event_heading: str
    event_starttime: datetime
    enforced: bool = False


@dataclass
class RuleResult:
    removals: list[RemovalInfo] = field(default_factory=list)
    rule_end_time: datetime | None = None


class RuleBase(ABC):
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

    @abstractmethod
    def isactive(self) -> bool:
        pass

    @abstractmethod
    def enforce(self, last_events: list[Event]) -> RuleResult | None:
        pass


RULE_REGISTRY: dict[str, type[RuleBase]] = {}


def register_rule(rule_type: str, rule_class: type[RuleBase]) -> None:
    RULE_REGISTRY[rule_type] = rule_class


def create_rule(rule_name, event, rule_def) -> RuleBase:
    rule_cls = RULE_REGISTRY.get(rule_def["type"])
    if not rule_cls:
        raise ValueError(f"Unknown rule type: {rule_name}")
    # Pass event and any additional rule_def parameters except 'type'
    rule_params = {k: v for k, v in rule_def.items() if k not in ("type",)}
    rule_params["rule_name"] = rule_name
    return rule_cls(event, **rule_params)
