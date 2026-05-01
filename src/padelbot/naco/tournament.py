import logging
from datetime import datetime
from http import HTTPStatus
from uuid import UUID

from naco_backend_client import Client
from naco_backend_client.api.tournaments import create_tournament_from_spond
from naco_backend_client.models.spond_tournament_create import SpondTournamentCreate
from naco_backend_client.models.spond_tournament_create_response import (
    SpondTournamentCreateResponse,
)
from naco_backend_client.types import Unset


class NacoTournamentCreator:
    def __init__(self, base_url: str, api_key: str):
        self.client = Client(base_url=base_url)
        self.api_key = api_key
        self.cache_created_event_ids: set[str] = set()

    async def create_tournament(
        self,
        event_id: str,
        event_heading: str,
        tournament_type: str,
        created_by_spond_id: UUID,
        player_spond_ids: list[UUID],
        start_time: datetime,
        points_to_win: int | None = None,
        court_names: list[str] | None = None,
    ) -> bool:
        """Create a tournament in Naco for the given Spond event.

        Returns True if the tournament was created or already exists (409).
        Returns False on failure.
        """
        if event_id in self.cache_created_event_ids:
            return True

        logging.info(
            f'Creating tournament in Naco for "{event_heading}" '
            f"with {len(player_spond_ids)} players, starting at {start_time.replace(tzinfo=None)}"
        )

        body = SpondTournamentCreate(
            name=event_heading,
            type_=tournament_type,
            external_id=UUID(event_id),
            created_by_spond_id=created_by_spond_id,
            player_spond_ids=player_spond_ids if player_spond_ids else [],
            points_to_win=points_to_win,
            court_names=court_names if court_names else [],
        )

        try:
            response = await create_tournament_from_spond.asyncio_detailed(
                client=self.client,
                body=body,
                x_api_key=self.api_key,
            )
        except Exception as e:
            logging.error(f'Failed to create tournament for "{event_heading}": {e}')
            return False

        if isinstance(response.parsed, SpondTournamentCreateResponse):
            skipped = response.parsed.skipped_spond_ids
            if not isinstance(skipped, Unset) and skipped:
                logging.warning(
                    f'Tournament created for "{event_heading}", '
                    f"but {len(skipped)} player(s) were skipped (unknown Spond IDs)"
                )
            else:
                logging.info(f'Tournament created for "{event_heading}"')
            self.cache_created_event_ids.add(event_id)
            return True
        elif response.status_code == HTTPStatus.CONFLICT:
            logging.debug(f'Tournament for "{event_heading}" already exists')
            self.cache_created_event_ids.add(event_id)
            return True
        else:
            if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                logging.error(
                    f"Naco API authentication failed (HTTP {response.status_code.value}). "
                    f"Check your api_key in [naco] config."
                )
            else:
                logging.error(
                    f'Failed to create tournament for "{event_heading}": HTTP {response.status_code.value}'
                )
            return False
