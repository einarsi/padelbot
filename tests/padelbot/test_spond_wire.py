"""Run the bot against the real spond library and a local fake Spond server.

The other tests replace the Spond client with mocks. Here the requests the
library sends on the bot's behalf, and the replies it can handle, are real HTTP.
The event and group in `tests/test_data` are anonymised copies of real Spond
data, made with `tools/anonymise_dumps.py`.
"""

import copy
import json
import logging
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

# The HTTP library the generated Naco client is built on.
import httpx2
import pytest
import pytest_asyncio
from aiohttp import test_utils, web
from attrs import evolve
from spond import spond

from src.padelbot.padelbot import PadelBot

REPO_ROOT = Path(__file__).parents[2]
TEST_DATA = REPO_ROOT / "tests" / "test_data"
PROFILE_ID = "0000000000000000000000000000AAAA"
SPOND_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"


@dataclass
class Received:
    route: str
    query: dict[str, str]
    json: Any
    headers: dict[str, str]


class FakeSpond:
    """Answers like the Spond API and records every request it receives."""

    def __init__(self, event: dict, group: dict) -> None:
        self.events = [event]
        self.groups = [group]
        self.profile: dict = {"id": PROFILE_ID}
        self.requests: list[Received] = []
        self._scripted: dict[str, list[tuple[int, Any]]] = {}
        self._logins = 0

        self.app = web.Application(middlewares=[self._record])
        self.app.router.add_post("/auth2/login", self._login)
        self.app.router.add_get("/profile", self._reply(lambda: self.profile))
        self.app.router.add_get("/sponds/", self._reply(lambda: self.events))
        self.app.router.add_get("/groups/", self._reply(lambda: self.groups))
        self.app.router.add_put(
            "/sponds/{event_id}/responses/{member_id}",
            self._reply(lambda: self.events[0]["responses"]),
        )
        self.app.router.add_post("/chat", self._chat_login)
        self.app.router.add_post("/chat-api/messages", self._reply(dict))

    def script(self, route: str, status: int, body: Any) -> None:
        """Answer the next request to `route` with this reply instead of the usual one."""
        self._scripted.setdefault(route, []).append((status, body))

    def received(self, route: str) -> list[Received]:
        return [r for r in self.requests if r.route == route]

    @web.middleware
    async def _record(self, request: web.Request, handler) -> web.StreamResponse:
        route = f"{request.method} {request.path}"
        body = await request.json() if request.can_read_body else None
        self.requests.append(
            Received(route, dict(request.query), body, dict(request.headers))
        )
        if self._scripted.get(route):
            status, reply = self._scripted[route].pop(0)
            if isinstance(reply, str):
                return web.Response(status=status, text=reply)
            return web.json_response(reply, status=status)
        return await handler(request)

    @staticmethod
    def _reply(data):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response(data())

        return handler

    async def _login(self, request: web.Request) -> web.Response:
        self._logins += 1
        return web.json_response({"accessToken": {"token": f"token-{self._logins}"}})

    async def _chat_login(self, request: web.Request) -> web.Response:
        chat_url = f"{request.scheme}://{request.host}/chat-api"
        return web.json_response({"url": chat_url, "auth": "chat-auth"})


def _schedule(event: dict, start: datetime) -> None:
    event["startTimestamp"] = start.strftime(SPOND_TIMESTAMP)
    event["endTimestamp"] = (start + timedelta(minutes=90)).strftime(SPOND_TIMESTAMP)


@pytest.fixture
def event() -> dict:
    """A real-shaped upcoming event, two days from now."""
    event = json.loads((TEST_DATA / "spond_event.json").read_text())
    _schedule(event, datetime.now(UTC) + timedelta(days=2))
    return event


@pytest.fixture
def group() -> dict:
    return json.loads((TEST_DATA / "spond_group.json").read_text())


@pytest.fixture
def cfg(group) -> dict:
    return {
        "auth": {
            "username": "bot@example.com",
            "password": "secret",
            "group_id": group["id"],
        },
        "general": {"seconds_to_sleep": 600},
        "naco": {"enabled": False},
        "rules": {},
        "actions": {},
    }


@pytest_asyncio.fixture
async def fake_spond(event, group):
    fake = FakeSpond(event, group)
    async with test_utils.TestServer(fake.app) as server:
        with patch.object(spond.Spond, "_API_BASE_URL", str(server.make_url("/"))):
            yield fake


@pytest_asyncio.fixture
async def bot(fake_spond, cfg):
    bot = PadelBot(cfg)
    yield bot
    await bot.spond.clientsession.close()


def _min_start(now: datetime) -> str:
    return (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_logs_in_and_asks_for_the_groups_events(
        self, bot, fake_spond, event, cfg
    ):
        before = datetime.now().astimezone()
        events = await bot.get_events()
        after = datetime.now().astimezone()

        login, sponds = fake_spond.requests
        assert login.route == "POST /auth2/login"
        assert login.json == {"email": "bot@example.com", "password": "secret"}
        assert sponds.route == "GET /sponds/"
        assert sponds.headers["Authorization"] == "Bearer token-1"
        assert sponds.query.pop("minStartTimestamp") in {
            _min_start(before),
            _min_start(after),
        }
        assert sponds.query == {
            "groupId": cfg["auth"]["group_id"],
            "max": "100",
            "scheduled": "False",
        }
        assert [e["id"] for e in events.upcoming] == [event["id"]]
        assert events.previous == events.ongoing == []

    @pytest.mark.asyncio
    async def test_logs_in_again_when_the_token_has_expired(
        self, bot, fake_spond, event
    ):
        fake_spond.script("GET /sponds/", 401, {"message": "Unauthorized"})

        events = await bot.get_events()

        assert [e["id"] for e in events.upcoming] == [event["id"]]
        assert len(fake_spond.received("POST /auth2/login")) == 2
        assert [
            r.headers["Authorization"] for r in fake_spond.received("GET /sponds/")
        ] == ["Bearer token-1", "Bearer token-2"]

    @pytest.mark.asyncio
    async def test_server_error_gives_no_events_and_is_not_retried(
        self, bot, fake_spond
    ):
        fake_spond.script("GET /sponds/", 500, "Internal Server Error")

        events = await bot.get_events()

        assert events.upcoming == events.previous == events.ongoing == []
        assert len(fake_spond.received("GET /sponds/")) == 1
        assert len(fake_spond.received("POST /auth2/login")) == 1


class TestRemovePlayerFromEvent:
    @pytest.mark.asyncio
    async def test_declines_for_the_player_and_sends_the_message(
        self, bot, fake_spond, event, cfg
    ):
        player_id = event["responses"]["acceptedIds"][0]
        (player,) = [
            m for m in event["recipients"]["group"]["members"] if m["id"] == player_id
        ]

        removed = await bot.remove_player_from_event(
            player_id, event["id"], "You were removed", [event], enforce=True
        )

        assert removed is True
        (change,) = fake_spond.received(
            f"PUT /sponds/{event['id']}/responses/{player_id}"
        )
        assert change.json == {"accepted": "false"}
        assert change.headers["Authorization"] == "Bearer token-1"
        (message,) = fake_spond.received("POST /chat-api/messages")
        assert message.json == {
            "text": "You were removed",
            "type": "TEXT",
            "recipient": player["profile"]["id"],
            "groupId": cfg["auth"]["group_id"],
        }
        assert message.headers["auth"] == "chat-auth"

    @pytest.mark.asyncio
    async def test_sends_nothing_when_not_enforced(self, bot, fake_spond, event):
        player_id = event["responses"]["acceptedIds"][0]

        removed = await bot.remove_player_from_event(
            player_id, event["id"], "You were removed", [event], enforce=False
        )

        assert removed is False
        assert fake_spond.requests == []


class TestResolveSpondProfileId:
    @pytest.mark.asyncio
    async def test_reads_the_id_from_the_profile(self, bot, fake_spond):
        await bot.resolve_spond_profile_id()

        assert bot.spond_profile_id == PROFILE_ID
        (profile,) = fake_spond.received("GET /profile")
        assert profile.headers["Authorization"] == "Bearer token-1"

    @pytest.mark.asyncio
    async def test_stays_unresolved_when_the_profile_has_no_id(
        self, bot, fake_spond, caplog
    ):
        fake_spond.profile = {"message": "Unauthorized"}

        await bot.resolve_spond_profile_id()

        assert bot.spond_profile_id is None
        assert "did not contain an 'id' field" in caplog.text

    @pytest.mark.asyncio
    async def test_is_resolved_on_a_later_call_after_a_failure(
        self, bot, fake_spond, caplog
    ):
        fake_spond.script("GET /profile", 500, "Internal Server Error")

        await bot.resolve_spond_profile_id()
        assert bot.spond_profile_id is None
        assert "Failed to fetch Spond profile" in caplog.text

        await bot.resolve_spond_profile_id()
        assert bot.spond_profile_id == PROFILE_ID


class TestGetPersonWithRefresh:
    @pytest.mark.asyncio
    async def test_fetches_groups_again_for_a_member_who_joined_later(
        self, bot, fake_spond, group
    ):
        newcomer = group["members"].pop()
        existing = group["members"][0]

        person = await bot._get_person_with_refresh(existing["id"])
        assert person["profile"]["email"] == existing["profile"]["email"]
        assert len(fake_spond.received("GET /groups/")) == 1

        group["members"].append(newcomer)
        person = await bot._get_person_with_refresh(newcomer["id"])

        assert person["profile"]["email"] == newcomer["profile"]["email"]
        assert len(fake_spond.received("GET /groups/")) == 2

    @pytest.mark.asyncio
    async def test_raises_for_a_member_who_is_in_no_group(self, bot, fake_spond):
        with pytest.raises(KeyError):
            await bot._get_person_with_refresh("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")


async def _run_cycle(bot) -> None:
    # Only the bot's own sleep is replaced, not asyncio.sleep everywhere.
    with patch("src.padelbot.padelbot.asyncio") as bot_asyncio:
        bot_asyncio.sleep = AsyncMock()
        await bot.run()


class TestLoginAttemptsPerCycle:
    """Spond rate-limits logins, so a cycle must not log in more than once."""

    REJECTIONS = pytest.mark.parametrize(
        ("status", "body"),
        [
            (401, {"message": "Invalid credentials"}),
            (429, "<html>Too many requests</html>"),
        ],
        ids=["wrong-credentials", "rate-limited"],
    )

    @staticmethod
    def _logins(fake_spond) -> int:
        return len(fake_spond.received("POST /auth2/login"))

    @pytest.mark.asyncio
    @REJECTIONS
    async def test_logs_in_once_per_cycle_while_login_keeps_failing(
        self, bot, fake_spond, status, body
    ):
        for _ in range(10):
            fake_spond.script("POST /auth2/login", status, body)

        logins = []
        for _ in range(3):
            await _run_cycle(bot)
            logins.append(self._logins(fake_spond))

        assert logins == [1, 2, 3]
        assert fake_spond.received("GET /sponds/") == []

    @pytest.mark.asyncio
    @REJECTIONS
    async def test_fetches_events_in_the_cycle_after_a_failed_login(
        self, bot, fake_spond, event, status, body
    ):
        fake_spond.script("POST /auth2/login", status, body)

        await _run_cycle(bot)
        assert bot.events.upcoming == []

        await _run_cycle(bot)
        assert [e["id"] for e in bot.events.upcoming] == [event["id"]]
        assert bot.spond_profile_id == PROFILE_ID
        assert self._logins(fake_spond) == 2

    @pytest.mark.asyncio
    @REJECTIONS
    async def test_recovers_from_a_failed_login_after_the_token_expired(
        self, bot, fake_spond, event, status, body
    ):
        await _run_cycle(bot)
        assert self._logins(fake_spond) == 1

        # The token expires, and the new login is rejected.
        fake_spond.script("GET /sponds/", 401, {"message": "Unauthorized"})
        fake_spond.script("POST /auth2/login", status, body)
        await _run_cycle(bot)
        assert bot.events.upcoming == []
        assert self._logins(fake_spond) == 2

        await _run_cycle(bot)
        assert [e["id"] for e in bot.events.upcoming] == [event["id"]]
        assert self._logins(fake_spond) == 3


class TestFirstCycle:
    """One `run()` with the shipped rules and actions, real Spond and Naco clients."""

    @pytest.fixture
    def cfg(self, cfg) -> dict:
        shipped = tomllib.loads((REPO_ROOT / "config.toml").read_text())
        return {
            **cfg,
            "rules": shipped["rules"],
            "actions": shipped["actions"],
            "naco": {
                "enabled": True,
                "base_url": "http://naco.test",
                "api_key": "test-key",
            },
        }

    @pytest.mark.asyncio
    async def test_registers_players_in_naco_and_changes_nothing_in_spond(
        self, bot, fake_spond, event, group, caplog
    ):
        caplog.set_level(logging.INFO)
        # Last week's event ended 12 hours ago, so everyone who played it is in
        # quarantine for this week's event and the shipped rule wants them removed.
        start = datetime.now(UTC) + timedelta(days=6, hours=12)
        _schedule(event, start)
        last_week = {**copy.deepcopy(event), "id": "0000000000000000000000000000BBBB"}
        _schedule(last_week, start - timedelta(days=7))
        fake_spond.events.append(last_week)

        registered = []

        def naco(request: httpx2.Request) -> httpx2.Response:
            user = json.loads(request.content)
            registered.append(user)
            reply = {
                "id": str(UUID(int=len(registered))),
                "username": user["username"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "ranking": 0.0,
                "name": f"{user['first_name']} {user['last_name']}",
            }
            return httpx2.Response(201, json=reply)

        bot.naco_registrar.client = evolve(
            bot.naco_registrar.client,
            httpx_args={"transport": httpx2.MockTransport(naco)},
        )

        # Only the bot's own sleep is replaced, not asyncio.sleep everywhere.
        sleep = AsyncMock()
        with patch("src.padelbot.padelbot.asyncio") as bot_asyncio:
            bot_asyncio.sleep = sleep
            await bot.run()

        responses = event["responses"]
        answered = (
            responses["acceptedIds"]
            + responses["waitinglistIds"]
            + responses["declinedIds"]
        )
        members = {m["id"]: m for m in group["members"]}
        assert registered == [
            {
                "username": f"{members[i]['firstName']}.{members[i]['lastName']}".lower(),
                "first_name": members[i]["firstName"],
                "last_name": members[i]["lastName"],
                "email": members[i]["profile"]["email"],
                "spond_profile_id": str(UUID(members[i]["profile"]["id"])),
            }
            for i in answered
        ]

        assert bot.spond_profile_id == PROFILE_ID
        assert [e["id"] for e in bot.events.upcoming] == [event["id"]]
        assert [e["id"] for e in bot.events.previous] == [last_week["id"]]
        assert bot.first_run is False
        assert "Skipping" not in caplog.text
        assert caplog.text.count("Not enforcing removal of player") == len(
            responses["acceptedIds"]
        )
        assert {r.route for r in fake_spond.requests} == {
            "POST /auth2/login",
            "GET /profile",
            "GET /sponds/",
            "GET /groups/",
        }
        (slept,) = sleep.await_args_list
        (seconds,) = slept.args
        assert 0 < seconds <= 600
