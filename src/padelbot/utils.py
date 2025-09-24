from datetime import datetime
from typing import Any

Event = dict[str, Any]


def memberid_to_member(
    member_id: str, members: list[dict[str, Any]]
) -> dict[str, Any] | None:
    for member in members:
        if member["id"] == member_id:
            return member
    return None


def get_last_practice_in_series(event: Event, events: list[Event]) -> Event | None:
    start = datetime.fromisoformat(event["startTimestamp"])
    for previous_event in events:
        # Keep it simple: If startTimestamp was exactly 7 days before, +/- 5 minutes, it is in the same series.
        # Times are timezoned, so no DST issues.
        previous_start = datetime.fromisoformat(previous_event["startTimestamp"])
        if abs((start - previous_start).total_seconds() - 7 * 24 * 60 * 60) <= 5 * 60:
            return previous_event
    return None
