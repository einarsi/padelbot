"""Run the real generated Naco client against a fake HTTP transport.

The other Naco tests patch the generated API functions, so the URL, the
headers, the request body and the response parsing only run here.
"""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

# The HTTP library the generated client is built on.
import httpx2 as httpx
import pytest
from attrs import evolve

from src.padelbot.naco.registrar import NacoRegistrar
from src.padelbot.naco.tournament import NacoTournamentCreator

BASE_URL = "http://naco.test"
API_KEY = "test-key"
EVENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CREATOR_ID = "11111111-1111-1111-1111-111111111111"
PLAYER_ID = "22222222-2222-2222-2222-222222222222"
SKIPPED_ID = "33333333-3333-3333-3333-333333333333"
MEMBER_ID = "AAAAAAAABBBBCCCCDDDDEEEEEEEEEEEE"
VALIDATION_ERROR = {
    "detail": [{"loc": ["body", "name"], "msg": "Field required", "type": "missing"}]
}


def _serve(naco, handler) -> list[httpx.Request]:
    """Answer the client's requests with `handler` and return the requests it sent."""
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    # Only the transport is replaced; the client still builds its own
    # httpx.AsyncClient from the configured base URL.
    naco.client = evolve(
        naco.client, httpx_args={"transport": httpx.MockTransport(record)}
    )
    return requests


def _refuse_connection(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


@pytest.fixture
def creator():
    return NacoTournamentCreator(base_url=BASE_URL, api_key=API_KEY)


@pytest.fixture
def registrar():
    return NacoRegistrar(base_url=BASE_URL, api_key=API_KEY)


async def _create_tournament(creator: NacoTournamentCreator) -> bool:
    return await creator.create_tournament(
        event_id=EVENT_ID,
        event_heading="Tuesday Americano",
        tournament_type="americano",
        created_by_spond_id=UUID(CREATOR_ID),
        player_spond_ids=[UUID(PLAYER_ID)],
        start_time=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        end_time=datetime(2026, 5, 1, 19, 30, tzinfo=UTC),
        points_to_win=24,
        court_names=["Court 1"],
    )


async def _register_alice(registrar: NacoRegistrar) -> None:
    event = {
        "responses": {
            "acceptedIds": [MEMBER_ID],
            "waitinglistIds": [],
            "declinedIds": [],
        },
        "recipients": {
            "group": {
                "members": [
                    {
                        "id": MEMBER_ID,
                        "firstName": "Alice",
                        "lastName": "Alison",
                        "profile": {"id": "AAAA0000BBBB1111CCCC2222DDDD3333"},
                    }
                ]
            }
        },
    }

    async def get_person(player_id: str) -> dict:
        return {"profile": {"email": "alice@example.com"}}

    await registrar.register_event_users([event], get_person)


class TestCreateTournamentOverHttp:
    @pytest.mark.asyncio
    async def test_sends_request_and_parses_created_response(self, creator, caplog):
        caplog.set_level(logging.INFO)
        requests = _serve(
            creator,
            lambda request: httpx.Response(
                201,
                json={
                    "tournament_id": "99999999-9999-9999-9999-999999999999",
                    "view_url": "https://naco.example.com/view/ABCD1234",
                    "edit_url": "https://naco.example.com/edit/EFGH5678",
                    "skipped_spond_ids": [SKIPPED_ID],
                },
            ),
        )

        assert await _create_tournament(creator) is True

        (request,) = requests
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL}/api/v1/tournaments/from-spond"
        assert request.headers["x-api-key"] == API_KEY
        assert json.loads(request.content) == {
            "name": "Tuesday Americano",
            "type": "americano",
            "external_id": EVENT_ID,
            "created_by_spond_id": CREATOR_ID,
            "player_spond_ids": [PLAYER_ID],
            "points_to_win": 24,
            "court_names": ["Court 1"],
            "scheduled_start": "2026-05-01T18:00:00+00:00",
            "scheduled_end": "2026-05-01T19:30:00+00:00",
        }
        assert "view_url=https://naco.example.com/view/ABCD1234" in caplog.text
        assert "1 player(s) were skipped" in caplog.text
        assert EVENT_ID in creator.cache_created_event_ids

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("response", "created"),
        [
            (httpx.Response(409, json={"detail": "Tournament already exists"}), True),
            (httpx.Response(401, json={"detail": "Invalid API key"}), False),
            (httpx.Response(422, json=VALIDATION_ERROR), False),
            (httpx.Response(500, text="Internal Server Error"), False),
        ],
        ids=["409", "401", "422", "500"],
    )
    async def test_error_statuses(self, creator, response, created):
        _serve(creator, lambda request: response)

        assert await _create_tournament(creator) is created
        assert (EVENT_ID in creator.cache_created_event_ids) is created

    @pytest.mark.asyncio
    async def test_connection_error_returns_false(self, creator):
        _serve(creator, _refuse_connection)

        assert await _create_tournament(creator) is False
        assert EVENT_ID not in creator.cache_created_event_ids


class TestRegisterUserOverHttp:
    @pytest.mark.asyncio
    async def test_sends_request_and_parses_created_response(self, registrar, caplog):
        caplog.set_level(logging.INFO)
        requests = _serve(
            registrar,
            lambda request: httpx.Response(
                201,
                json={
                    "id": "00000000-0000-0000-0000-000000000001",
                    "username": "alice.alison",
                    "first_name": "Alice",
                    "last_name": "Alison",
                    "ranking": 0.0,
                    "name": "Alice Alison",
                    "show_in_leaderboard": True,
                },
            ),
        )

        await _register_alice(registrar)

        (request,) = requests
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL}/api/v1/users"
        assert request.headers["x-api-key"] == API_KEY
        assert json.loads(request.content) == {
            "username": "alice.alison",
            "first_name": "Alice",
            "last_name": "Alison",
            "email": "alice@example.com",
            "spond_profile_id": "aaaa0000-bbbb-1111-cccc-2222dddd3333",
        }
        assert "Registered user Alice Alison" in caplog.text
        assert registrar.cache_registered_spond_member_ids == {MEMBER_ID.lower()}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("response", "cached"),
        [
            (httpx.Response(409, json={"detail": "User already exists"}), True),
            (httpx.Response(401, json={"detail": "Invalid API key"}), False),
            (httpx.Response(422, json=VALIDATION_ERROR), False),
            (httpx.Response(500, text="Internal Server Error"), False),
        ],
        ids=["409", "401", "422", "500"],
    )
    async def test_error_statuses(self, registrar, response, cached):
        _serve(registrar, lambda request: response)

        await _register_alice(registrar)

        assert bool(registrar.cache_registered_spond_member_ids) is cached

    @pytest.mark.asyncio
    async def test_connection_error_is_not_cached(self, registrar):
        requests = _serve(registrar, _refuse_connection)

        await _register_alice(registrar)

        assert len(requests) == 1
        assert not registrar.cache_registered_spond_member_ids
