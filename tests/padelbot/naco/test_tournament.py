from datetime import datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from naco_backend_client.models.spond_tournament_create_response import (
    SpondTournamentCreateResponse,
)
from naco_backend_client.types import UNSET, Response

from src.padelbot.naco.tournament import NacoTournamentCreator

EVENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CREATOR_ID = UUID("11111111-1111-1111-1111-111111111111")
TOURNAMENT_ID = UUID("99999999-9999-9999-9999-999999999999")
PLAYER_IDS = [
    UUID("22222222-2222-2222-2222-222222222222"),
    UUID("33333333-3333-3333-3333-333333333333"),
]
START_TIME = datetime(2026, 5, 1, 18, 0, tzinfo=datetime.now().astimezone().tzinfo)


@pytest.fixture
def creator():
    return NacoTournamentCreator(base_url="http://localhost:8000", api_key="test-key")


def _make_response(status_code, parsed=None):
    return Response(
        status_code=status_code,
        content=b"",
        headers={},
        parsed=parsed,
    )


class TestCreateTournament:
    @pytest.mark.asyncio
    async def test_success(self, creator):
        parsed = SpondTournamentCreateResponse(
            tournament_id=TOURNAMENT_ID,
            view_url="https://naco.example.com/view/ABCD1234",
            edit_url="https://naco.example.com/edit/EFGH5678",
            skipped_spond_ids=UNSET,
        )
        response = _make_response(HTTPStatus.CREATED, parsed)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_success_with_skipped_players(self, creator):
        skipped = [UUID("44444444-4444-4444-4444-444444444444")]
        parsed = SpondTournamentCreateResponse(
            tournament_id=TOURNAMENT_ID,
            view_url="https://naco.example.com/view/ABCD1234",
            edit_url="https://naco.example.com/edit/EFGH5678",
            skipped_spond_ids=skipped,
        )
        response = _make_response(HTTPStatus.CREATED, parsed)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is True
        assert EVENT_ID in creator.cache_created_event_ids

    @pytest.mark.asyncio
    async def test_conflict_409_returns_true(self, creator):
        response = _make_response(HTTPStatus.CONFLICT, None)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is True
        assert EVENT_ID in creator.cache_created_event_ids

    @pytest.mark.asyncio
    async def test_auth_failure_returns_false(self, creator):
        response = _make_response(HTTPStatus.UNAUTHORIZED, None)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is False
        assert EVENT_ID not in creator.cache_created_event_ids

    @pytest.mark.asyncio
    async def test_forbidden_returns_false(self, creator):
        response = _make_response(HTTPStatus.FORBIDDEN, None)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_server_error_returns_false(self, creator):
        response = _make_response(HTTPStatus.INTERNAL_SERVER_ERROR, None)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_network_error_returns_false(self, creator):
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            side_effect=Exception("connection refused"),
        ):
            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
        assert result is False
        assert EVENT_ID not in creator.cache_created_event_ids

    @pytest.mark.asyncio
    async def test_cache_skips_second_call(self, creator):
        parsed = SpondTournamentCreateResponse(
            tournament_id=TOURNAMENT_ID,
            view_url="https://naco.example.com/view/ABCD1234",
            edit_url="https://naco.example.com/edit/EFGH5678",
            skipped_spond_ids=UNSET,
        )
        response = _make_response(HTTPStatus.CREATED, parsed)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ) as mock_api:
            await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
            assert mock_api.await_count == 1

            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
            assert result is True
            assert mock_api.await_count == 1  # No second API call

    @pytest.mark.asyncio
    async def test_cache_populated_on_409(self, creator):
        response = _make_response(HTTPStatus.CONFLICT, None)
        with patch(
            "src.padelbot.naco.tournament.create_tournament_from_spond.asyncio_detailed",
            new_callable=AsyncMock,
            return_value=response,
        ) as mock_api:
            await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
            mock_api.reset_mock()

            result = await creator.create_tournament(
                event_id=EVENT_ID,
                event_heading="Tuesday Americano",
                tournament_name="Tuesday 2026-05-01 18:00-19:30",
                tournament_type="americano",
                created_by_spond_id=CREATOR_ID,
                player_spond_ids=PLAYER_IDS,
                start_time=START_TIME,
            )
            assert result is True
            mock_api.assert_not_awaited()
