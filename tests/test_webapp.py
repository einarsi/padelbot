import logging
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from logging.handlers import QueueHandler
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from spond import spond
from starlette.testclient import TestClient

import webapp
from padelbot.padelbot import HEALTH_GRACE_SECONDS

REPO_ROOT = Path(__file__).parents[1]
CONFIG_ENV_VARS = (
    "SPOND_USERNAME",
    "SPOND_PASSWORD",
    "SPOND_GROUP_ID",
    "NACO_ENABLED",
    "NACO_BASE_URL",
    "NACO_API_KEY",
)
MEMBERS = [
    {"id": "alice-id", "firstName": "Alice", "lastName": "Alison"},
    {"id": "bob-id", "firstName": "Bob", "lastName": "Bobson"},
]
NOW = datetime.now().astimezone()


def _event(event_id: str, heading: str, start: datetime, **responses: list[str]):
    return {
        "id": event_id,
        "heading": heading,
        "startTimestamp": start.isoformat(),
        "endTimestamp": (start + timedelta(minutes=90)).isoformat(),
        "recipients": {"group": {"members": MEMBERS}},
        "responses": {
            "acceptedIds": [],
            "unconfirmedIds": [],
            "waitinglistIds": [],
            "declinedIds": [],
            "unansweredIds": [],
            **responses,
        },
    }


THURSDAY = _event("e3", "Thursday Social", NOW + timedelta(days=4))
TUESDAY = _event(
    "e2",
    "Tuesday Americano",
    NOW + timedelta(days=2),
    acceptedIds=["alice-id"],
    waitinglistIds=["bob-id"],
    unansweredIds=["not-a-member-id"],
)
LAST_TUESDAY = _event(
    "e1", "Tuesday Americano", NOW - timedelta(days=5), acceptedIds=["alice-id"]
)


def _wait_for(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


@pytest.fixture
def fake_spond():
    # Any Spond method the bot awaits succeeds without touching the network.
    fake = AsyncMock()
    fake.get_profile.return_value = {"id": "11111111-1111-1111-1111-111111111111"}
    fake.get_events.return_value = [THURSDAY, LAST_TUESDAY, TUESDAY]
    return fake


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    """A working directory like the container's: the shipped config and no credentials."""
    # The app reads these from the working directory, as it does in the container.
    for name in ("pyproject.toml", "config.toml"):
        shutil.copy(REPO_ROOT / name, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Never pick up a developer's .env or exported credentials.
    monkeypatch.setattr("padelbot.core.config.load_dotenv", lambda: None)
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@contextmanager
def _started(fake_spond):
    """Start the real app with a fake Spond client, and undo its logging setup after."""
    root = logging.getLogger()
    level = root.level
    try:
        with (
            patch.object(spond, "Spond", return_value=fake_spond),
            TestClient(webapp.app) as client,
        ):
            yield client
    finally:
        # The app object is shared between tests; do not leave a bot behind on it.
        if hasattr(webapp.app.state, "padelbot"):
            del webapp.app.state.padelbot
        for handler in root.handlers[:]:
            if isinstance(handler, QueueHandler):
                root.removeHandler(handler)
        root.setLevel(level)


@pytest.fixture
def client(app_dir, fake_spond, monkeypatch, caplog):
    """The real app, started with the shipped config, credentials and a fake Spond."""
    for name in ("SPOND_USERNAME", "SPOND_PASSWORD", "SPOND_GROUP_ID"):
        monkeypatch.setenv(name, "dummy")

    with _started(fake_spond) as client:
        # The bot loop runs in the background; wait for its first cycle to end.
        _wait_for(lambda: "Sleeping for" in caplog.text or "Run failed" in caplog.text)
        yield client


def test_starts_without_credentials_but_runs_no_bot(app_dir, fake_spond, caplog):
    with _started(fake_spond) as client:
        assert client.get("/").status_code == 200
        assert client.get("/logs").status_code == 200
        assert client.get("/events").status_code == 500
        assert client.get("/health").status_code == 503

    assert "Missing configuration" in caplog.text
    fake_spond.get_profile.assert_not_awaited()
    fake_spond.get_events.assert_not_awaited()


def test_serves_all_routes(client):
    for path in ("/", "/logs", "/events", "/health"):
        assert client.get(path).status_code == 200, path


@pytest.fixture
def unreadable_events(fake_spond):
    """Spond returns an event the bot cannot handle, so every cycle fails."""
    fake_spond.get_events.return_value = [{"id": "e1", "heading": "Broken"}]


def test_health_fails_while_the_bot_loop_keeps_failing(
    unreadable_events, client, caplog
):
    startup_log = "\n".join(r.getMessage() for r in caplog.get_records("setup"))

    assert "Run failed" in startup_log
    assert client.get("/health").status_code == 503
    assert client.get("/").status_code == 200


def test_health_fails_when_the_next_cycle_is_overdue(client):
    bot = webapp.app.state.padelbot
    now = datetime.now().astimezone()

    # One failed cycle is retried after 60 seconds, which is within the grace period.
    bot.next_cycle_due = now - timedelta(seconds=HEALTH_GRACE_SECONDS - 5)
    assert client.get("/health").status_code == 200

    bot.next_cycle_due = now - timedelta(seconds=HEALTH_GRACE_SECONDS + 1)
    assert client.get("/health").status_code == 503


def test_first_cycle_completes_without_changing_spond(client, fake_spond, caplog):
    startup_log = "\n".join(r.getMessage() for r in caplog.get_records("setup"))

    assert "Starting padelbot v" in startup_log
    assert "Sleeping for" in startup_log
    assert "Run failed" not in startup_log
    assert "Skipping rule" not in startup_log
    fake_spond.change_response.assert_not_awaited()
    fake_spond.send_message.assert_not_awaited()


def test_events_lists_upcoming_events_with_member_names(client):
    assert client.get("/events").json() == {
        "events": [
            {
                "heading": "Tuesday Americano",
                "startTimestamp": TUESDAY["startTimestamp"],
                "endTimestamp": TUESDAY["endTimestamp"],
                "accepted": ["Alice Alison"],
                "unconfirmed": [],
                "waitinglist": ["Bob Bobson"],
                "declined": [],
                "unanswered": ["not-a-member-id"],
            },
            {
                "heading": "Thursday Social",
                "startTimestamp": THURSDAY["startTimestamp"],
                "endTimestamp": THURSDAY["endTimestamp"],
                "accepted": [],
                "unconfirmed": [],
                "waitinglist": [],
                "declined": [],
                "unanswered": [],
            },
        ]
    }
