import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from ..utils import Event, Events, memberid_to_member
from .actionbase import ActionBase, ActionIntent, register_action


@dataclass(kw_only=True)
class CreateTournamentIntent(ActionIntent):
    """Intent to create a tournament in Naco for a matching event."""

    event_heading: str
    start_time: datetime
    end_time: datetime | None = None
    created_by_spond_id: UUID
    tournament_type: str = "americano"
    points_to_win: int | None = None
    player_spond_ids: list[UUID] = field(default_factory=list)
    court_names: list[str] = field(default_factory=list)


MAX_COURT_NAME_LENGTH = 30


class ActionNacoCreateTournament(ActionBase):
    def __init__(
        self,
        action_name: str,
        events: Events,
        header_regex: str,
        spond_profile_id: str,
        tournament_type: str = "americano",
        enforced: bool = False,
        minutes_before_start: int = 5,
        points_to_win: int | None = None,
    ) -> None:
        self.name = action_name
        self.events = events
        self.header_regex = header_regex
        self.tournament_type = tournament_type
        self.enforced = enforced
        self.minutes_before_start = minutes_before_start
        self.points_to_win = points_to_win
        self.spond_profile_id = UUID(spond_profile_id)

    def _include(self, event: Event) -> bool:
        return bool(re.search(self.header_regex, event["heading"], re.IGNORECASE))

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

    def _extract_court_names(self, event: Event) -> list[str]:
        """Extract court names from event description lines matching 'Court: <name>'."""
        description = event.get("description", "") or ""
        match = re.search(r"^Court:\s*(.+)$", description, re.MULTILINE | re.IGNORECASE)
        if not match:
            return []
        name = match.group(1).strip()
        if re.fullmatch(r"#?\d+", name):
            name = f"Court {name}"
        return [name[:MAX_COURT_NAME_LENGTH]]

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
            end_timestamp = event.get("endTimestamp")
            end_time = datetime.fromisoformat(end_timestamp) if end_timestamp else None

            logging.info(
                f'[{self.name}]: Scheduling tournament creation for "{event["heading"]}" '
                f"starting at {start_time.replace(tzinfo=None)}"
            )

            court_names = self._extract_court_names(event)

            intents.append(
                CreateTournamentIntent(
                    event_id=event["id"],
                    enforced=self.enforced,
                    event_heading=event["heading"],
                    start_time=start_time,
                    end_time=end_time,
                    tournament_type=self.tournament_type,
                    points_to_win=self.points_to_win,
                    created_by_spond_id=self.spond_profile_id,
                    player_spond_ids=player_spond_ids,
                    court_names=court_names,
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


register_action("NacoCreateTournament", ActionNacoCreateTournament)
