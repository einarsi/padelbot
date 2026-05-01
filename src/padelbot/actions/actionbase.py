from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..utils import Events


@dataclass(kw_only=True)
class ActionIntent:
    """Base class for action intents returned by actions."""

    event_id: str
    enforced: bool = False


class ActionBase(ABC):
    name: str = ""
    enforced: bool = False

    @abstractmethod
    def __init__(self, action_name: str, events: Events, *args) -> None:
        pass

    @abstractmethod
    def evaluate(self) -> list[ActionIntent]:
        pass

    @abstractmethod
    def expirationtimes(self) -> list[datetime]:
        pass


ACTION_REGISTRY: dict[str, type[ActionBase]] = {}


def register_action(action_type: str, action_class: type[ActionBase]) -> None:
    ACTION_REGISTRY[action_type] = action_class


def create_action(action_name: str, events: Events, action_def: dict) -> ActionBase:
    action_cls = ACTION_REGISTRY.get(action_def["type"])
    if not action_cls:
        raise ValueError(
            f'Unknown action type "{action_def["type"]}" for {action_name}'
        )
    action_params = {k: v for k, v in action_def.items() if k not in ("type",)}
    return action_cls(action_name, events, **action_params)
