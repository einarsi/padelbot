"""Read-only checks against the real Spond and Naco, with the bot's own configuration.

These are not part of the default test run. Run them before a deploy with:

    uv run pytest -m live

The configuration is read the way the bot reads it: `config.toml`, overridden by
`.env` and the environment. Nothing is changed in Spond or Naco.

Spond rate-limits logins (HTTP 429), so the whole run shares one bot and logs in
once. Avoid running it many times in a row.
"""

from http import HTTPStatus
from uuid import UUID

import aiohttp

# The HTTP library the generated Naco client is built on.
import httpx2
import pytest
import pytest_asyncio
from naco_backend_client.api.users import list_users
from naco_backend_client.models.paginated_response_user import PaginatedResponseUser
from spond import AuthenticationError

from src.padelbot.core import config
from src.padelbot.padelbot import PadelBot
from src.padelbot.utils import memberid_to_member

pytestmark = [pytest.mark.live, pytest.mark.asyncio(loop_scope="module")]


@pytest.fixture(scope="module")
def cfg():
    cfg = config.readconfig()
    if cfg is None or cfg["auth"]["username"] == "your_username":
        pytest.fail(
            "No Spond credentials. Set SPOND_USERNAME, SPOND_PASSWORD and "
            "SPOND_GROUP_ID in .env or the environment."
        )
    return cfg


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def bot(cfg):
    bot = PadelBot(cfg)
    yield bot
    await bot.spond.clientsession.close()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def spond_bot(bot):
    """The bot, logged in to Spond. A failed login is not retried by later tests."""
    try:
        await bot.spond.login()
    except (AuthenticationError, aiohttp.ClientError) as e:
        reason = f"{type(e).__name__}: {e}"
        if isinstance(e, aiohttp.ClientResponseError) and e.status == 429:
            headers = {k.lower(): v for k, v in dict(e.headers or {}).items()}
            reason = "Spond is rate-limiting logins (HTTP 429)."
            if retry_after := headers.get("retry-after"):
                reason += f" It asks you to wait {retry_after} seconds."
        pytest.fail(f"Spond login failed. {reason}", pytrace=False)
    return bot


async def _fetch_events(bot, caplog):
    events = await bot.get_events()
    assert "Failed to fetch events" not in caplog.text, caplog.text
    if not (events.previous or events.ongoing or events.upcoming):
        pytest.skip("Spond returned no events for the group, so nothing was checked")
    return events


async def test_spond_profile_has_a_usable_id(spond_bot, caplog):
    await spond_bot.resolve_spond_profile_id()

    assert spond_bot.spond_profile_id, caplog.text
    # Tournaments are created in Naco on behalf of this ID.
    UUID(spond_bot.spond_profile_id)


async def test_spond_events_have_the_fields_the_bot_reads(spond_bot, caplog):
    events = await _fetch_events(spond_bot, caplog)

    for event in events.previous + events.ongoing + events.upcoming:
        assert isinstance(event["id"], str)
        assert isinstance(event["heading"], str)
        for key in ("acceptedIds", "waitinglistIds", "declinedIds"):
            assert isinstance(event["responses"][key], list), key
        for member in event["recipients"]["group"]["members"]:
            for key in ("id", "firstName", "lastName"):
                assert isinstance(member[key], str), key

    # The rules look up everyone who is signed up for an upcoming event.
    for event in events.upcoming:
        members = event["recipients"]["group"]["members"]
        responses = event["responses"]
        for member_id in responses["acceptedIds"] + responses["waitinglistIds"]:
            memberid_to_member(member_id, members)


async def test_spond_member_lookup_returns_a_profile(spond_bot, caplog):
    events = await _fetch_events(spond_bot, caplog)
    accepted = [
        member_id
        for event in events.upcoming + events.ongoing + events.previous
        for member_id in event["responses"]["acceptedIds"]
    ]
    if not accepted:
        pytest.skip("Nobody has accepted an event, so there is no member to look up")

    person = await spond_bot._get_person_with_refresh(accepted[0])

    # Messages are sent to this ID, and it identifies the player in Naco.
    UUID(person["profile"]["id"])


async def test_naco_answers_with_the_configured_url_and_key(bot):
    if not bot.naco_enabled:
        pytest.skip("Naco is disabled in the configuration")

    base_url = bot.cfg["naco"]["base_url"]
    try:
        async with bot.naco_registrar.client as client:
            response = await list_users.asyncio_detailed(
                client=client, limit=1, x_api_key=bot.naco_registrar.api_key
            )
    except httpx2.HTTPError as e:
        pytest.fail(f"Could not reach Naco at {base_url}: {e!r}")

    assert response.status_code == HTTPStatus.OK, (
        f"Naco at {base_url} answered HTTP {response.status_code.value}"
    )
    assert isinstance(response.parsed, PaginatedResponseUser)
