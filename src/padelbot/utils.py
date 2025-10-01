from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

Event = dict[str, Any]


@dataclass
class Events:
    previous: list[Event] = field(default_factory=list)
    ongoing: list[Event] = field(default_factory=list)
    upcoming: list[Event] = field(default_factory=list)


def memberid_to_member(member_id: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    for member in members:
        if member["id"] == member_id:
            return member
    raise ValueError(f"Member ID {member_id} not found in members list")


def eventid_to_event(event_id: str, events: list[Event]) -> Event:
    for event in events:
        if event["id"] == event_id:
            return event
    raise ValueError(f"Event ID {event_id} not found in events list")


# Return the event with the highest startTimestamp from the list `events` that is
# also part of the same series of events as `event`. If no such event exists, return None.
def get_last_event_in_series(event: Event, events: list[Event]) -> Event | None:
    result = None
    for previous_event in events:
        if previous_event["seriesId"] == event["seriesId"]:
            if (result is None) or (
                datetime.fromisoformat(previous_event["startTimestamp"])
                > datetime.fromisoformat(result["startTimestamp"])
            ):
                result = previous_event
    return result


def get_registered_player_names(event: Event) -> list[str]:
    player_ids: list[str] = (
        event["responses"]["acceptedIds"] + event["responses"]["waitinglistIds"]
    )
    registered_names = [
        f"{player['firstName']} {player['lastName']}"
        for pid in player_ids
        if (player := memberid_to_member(pid, event["recipients"]["group"]["members"]))
    ]
    return registered_names
