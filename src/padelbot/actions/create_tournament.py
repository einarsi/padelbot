import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from ..utils import Event, Events, memberid_to_member
from .actionbase import ActionBase, ActionIntent, register_action


@dataclass
class CreateTournamentIntent(ActionIntent):
    """Intent to create a tournament in Naco for a matching event."""

    event_heading: str = ""
    tournament_type: str = "americano"
    points_to_win: int | None = None
    created_by_spond_id: UUID | None = None
    player_spond_ids: list[UUID] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now().astimezone())


class ActionCreateTournament(ActionBase):
    def __init__(
        self,
        action_name: str,
        events: Events,
        header_regex: str,
        tournament_type: str = "americano",
        created_by_spond_id: str = "",
        enforced: bool = False,
        minutes_before_start: int = 5,
        points_to_win: int | None = None,
    ) -> None:
        self.name = action_name
        self.events = events
        self.header_regex = header_regex
        self.tournament_type = tournament_type
        self.created_by_spond_id = (
            UUID(created_by_spond_id) if created_by_spond_id else None
        )
        self.enforced = enforced
        self.minutes_before_start = minutes_before_start
        self.points_to_win = points_to_win

    def _include(self, event: Event) -> bool:
        return bool(re.search(self.header_regex, event["heading"]))

    def _is_within_window(self, event: Event) -> bool:
        """Check if event starts within the configured minutes_before_start window."""
        start_time = datetime.fromisoformat(event["startTimestamp"])
        now = datetime.now().astimezone()
        time_until_start = start_time - now
        return (
            timedelta(0)
            < time_until_start
            <= timedelta(minutes=self.minutes_before_start)
        )

    def evaluate(self) -> list[ActionIntent]:
        intents: list[ActionIntent] = []
        for event in self.events.upcoming:
            if not self._include(event):
                continue
            if not self._is_within_window(event):
                continue

            try:
                UUID(event["id"])
            except ValueError:
                logging.warning(
                    f'[{self.name}]: Skipping event "{event["heading"]}" — '
                    f'invalid event ID "{event["id"]}" (not a valid UUID)'
                )
                continue

            # Resolve Spond profile IDs from accepted players
            members = event["recipients"]["group"]["members"]
            player_spond_ids: list[UUID] = []
            for player_id in event["responses"]["acceptedIds"]:
                try:
                    member = memberid_to_member(player_id, members)
                    profile_id = member.get("profile", {}).get("id")
                    if profile_id:
                        player_spond_ids.append(UUID(profile_id))
                except (ValueError, KeyError):
                    logging.warning(
                        f"[{self.name}]: Could not resolve profile ID for player {player_id}"
                    )

            start_time = datetime.fromisoformat(event["startTimestamp"])

            logging.info(
                f'[{self.name}]: Scheduling tournament creation for "{event["heading"]}" '
                f"starting at {start_time.replace(tzinfo=None)}"
            )

            intents.append(
                CreateTournamentIntent(
                    event_id=event["id"],
                    enforced=self.enforced,
                    event_heading=event["heading"],
                    tournament_type=self.tournament_type,
                    points_to_win=self.points_to_win,
                    created_by_spond_id=self.created_by_spond_id,
                    player_spond_ids=player_spond_ids,
                    start_time=start_time,
                )
            )
        return intents

    def expirationtimes(self) -> list[datetime]:
        """Return the times at which this action should trigger (start - minutes_before_start)."""
        times: list[datetime] = []
        for event in self.events.upcoming:
            if not self._include(event):
                continue
            start_time = datetime.fromisoformat(event["startTimestamp"])
            trigger_time = start_time - timedelta(minutes=self.minutes_before_start)
            times.append(trigger_time)
        return times


register_action("CreateTournament", ActionCreateTournament)
