import logging
from typing import Any
from uuid import UUID

from naco_backend_client import Client
from naco_backend_client.api.users import create_user
from naco_backend_client.models.user import User
from naco_backend_client.models.user_create import UserCreate

from ..utils import Event, memberid_to_member


class NacoRegistrar:
    def __init__(self, base_url: str, api_key: str):
        self.client = Client(base_url=base_url)
        self.api_key = api_key
        self.cache_registered_spond_member_ids: set[str] = set()

    async def register_event_users(self, events: list[Event], get_person: Any) -> None:
        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.WARNING)
        try:
            await self._register_event_users(events, get_person)
        finally:
            httpx_logger.setLevel(original_level)

    async def _register_event_users(self, events: list[Event], get_person: Any) -> None:
        # Collect all unique player_id -> member mappings across all events
        members_by_id: dict[str, dict] = {}
        for event in events:
            player_ids: list[str] = (
                event["responses"]["acceptedIds"]
                + event["responses"]["waitinglistIds"]
                + event["responses"]["declinedIds"]
            )
            members = event["recipients"]["group"]["members"]
            for player_id in player_ids:
                if player_id not in members_by_id:
                    try:
                        members_by_id[player_id] = memberid_to_member(
                            player_id, members
                        )
                    except ValueError:
                        pass

        for player_id, member in members_by_id.items():
            if (
                player_id.replace("-", "").lower()
                in self.cache_registered_spond_member_ids
            ):
                continue

            first_name = member["firstName"]
            last_name = member["lastName"]
            profile_id = member.get("profile", {}).get("id")

            try:
                person = await get_person(player_id)
            except Exception as e:
                logging.warning(
                    f"Failed to get person details for {first_name} {last_name}: {e}"
                )
                continue

            email = person.get("profile", {}).get("email", "")
            if not email:
                logging.warning(
                    f"No email found for {first_name} {last_name}, skipping registration"
                )
                continue

            user_create = UserCreate(
                username=f"{first_name}.{last_name}".lower(),
                first_name=first_name,
                last_name=last_name,
                email=email,
                spond_profile_id=UUID(profile_id) if profile_id else None,
            )

            try:
                response = await create_user.asyncio_detailed(
                    client=self.client,
                    body=user_create,
                    x_api_key=self.api_key,
                )
            except Exception as e:
                logging.error(f"Failed to register user {first_name} {last_name}: {e}")
                continue

            if isinstance(response.parsed, User):
                logging.info(
                    f"Registered user {first_name} {last_name} in Naco database"
                )
            elif response.status_code.value == 409:
                logging.debug(
                    f"User {first_name} {last_name} already exists in Naco database"
                )
            else:
                status = response.status_code.value
                if status in (401, 403):
                    logging.error(
                        f"Naco API authentication failed (HTTP {status}). "
                        f"Check your api_key in [naco] config."
                    )
                else:
                    logging.error(
                        f"Failed to register user {first_name} {last_name}: "
                        f"HTTP {status}"
                    )
                continue

            self.cache_registered_spond_member_ids.add(
                player_id.replace("-", "").lower()
            )
