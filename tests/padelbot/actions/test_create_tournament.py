from datetime import datetime, timedelta
from uuid import UUID

import pytest

from src.padelbot.actions.create_tournament import (
    ActionCreateTournament,
    CreateTournamentIntent,
)
from src.padelbot.utils import Events

ALICE_PROFILE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
BOB_PROFILE_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
CAROL_PROFILE_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
DAVE_PROFILE_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"
CREATOR_SPOND_ID = "11111111-1111-1111-1111-111111111111"

EVENT_ID_1 = "00000000-0000-0000-0000-000000000001"
EVENT_ID_2 = "00000000-0000-0000-0000-000000000002"
EVENT_ID_3 = "00000000-0000-0000-0000-000000000003"

MEMBERS = [
    {
        "id": "alice-id",
        "firstName": "Alice",
        "lastName": "Alison",
        "profile": {"id": ALICE_PROFILE_ID},
    },
    {
        "id": "bob-id",
        "firstName": "Bob",
        "lastName": "Bobson",
        "profile": {"id": BOB_PROFILE_ID},
    },
    {
        "id": "carol-id",
        "firstName": "Carol",
        "lastName": "Carolson",
        "profile": {"id": CAROL_PROFILE_ID},
    },
    {
        "id": "dave-id",
        "firstName": "Dave",
        "lastName": "Davison",
        "profile": {"id": DAVE_PROFILE_ID},
    },
    {"id": "eve-id", "firstName": "Eve", "lastName": "Eveson", "profile": {}},
]


@pytest.fixture
def sample_events():
    now = datetime.now().astimezone()
    events = Events()
    events.upcoming = [
        {
            "id": EVENT_ID_1,
            "heading": "Tuesday Americano",
            "startTimestamp": (now + timedelta(minutes=3)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": [],
            },
            "recipients": {"group": {"members": MEMBERS}},
        },
        {
            "id": EVENT_ID_2,
            "heading": "Thursday Americano",
            "startTimestamp": (now + timedelta(hours=2)).isoformat(),
            "responses": {
                "acceptedIds": ["carol-id", "dave-id"],
                "waitinglistIds": ["eve-id"],
            },
            "recipients": {"group": {"members": MEMBERS}},
        },
        {
            "id": EVENT_ID_3,
            "heading": "Friday Social",
            "startTimestamp": (now + timedelta(minutes=4)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id"],
                "waitinglistIds": [],
            },
            "recipients": {"group": {"members": MEMBERS}},
        },
    ]
    return events


def test_evaluate_returns_intent_for_matching_event_within_window(sample_events):
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Americano.*",
        tournament_type="americano",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=5,
    )
    intents = action.evaluate()
    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, CreateTournamentIntent)
    assert intent.event_id == EVENT_ID_1
    assert intent.event_heading == "Tuesday Americano"
    assert intent.tournament_type == "americano"
    assert intent.created_by_spond_id == UUID(CREATOR_SPOND_ID)
    assert intent.player_spond_ids == [UUID(ALICE_PROFILE_ID), UUID(BOB_PROFILE_ID)]
    assert intent.enforced is True


def test_evaluate_returns_empty_for_non_matching_header(sample_events):
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Mexicano.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=5,
    )
    intents = action.evaluate()
    assert intents == []


def test_evaluate_returns_empty_for_event_too_far_in_future(sample_events):
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Americano.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=1,  # Only 1 minute window, e1 is 3 min away
    )
    intents = action.evaluate()
    assert intents == []


def test_evaluate_does_not_include_non_matching_event_in_window(sample_events):
    """e3 'Friday Social' is within the time window but doesn't match the regex."""
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Americano.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=5,
    )
    intents = action.evaluate()
    event_ids = [i.event_id for i in intents]
    assert EVENT_ID_3 not in event_ids


def test_expirationtimes_returns_trigger_times(sample_events):
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Americano.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=5,
    )
    times = action.expirationtimes()
    # Should return trigger times for e1 and e2 (both match regex)
    assert len(times) == 2
    for t, event in zip(times, [sample_events.upcoming[0], sample_events.upcoming[1]]):
        expected = datetime.fromisoformat(event["startTimestamp"]) - timedelta(
            minutes=5
        )
        assert abs((t - expected).total_seconds()) < 1


def test_expirationtimes_excludes_non_matching(sample_events):
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Social.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=5,
    )
    times = action.expirationtimes()
    assert len(times) == 1  # Only e3 matches


def test_evaluate_not_enforced(sample_events):
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Americano.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=False,
        minutes_before_start=5,
    )
    intents = action.evaluate()
    assert len(intents) == 1
    assert intents[0].enforced is False


def test_evaluate_skips_event_with_invalid_uuid_id(sample_events):
    """Events with non-UUID IDs should be skipped with a warning."""
    sample_events.upcoming[0]["id"] = "not-a-valid-uuid"
    action = ActionCreateTournament(
        action_name="create_tournament",
        events=sample_events,
        header_regex=".*Americano.*",
        spond_profile_id=CREATOR_SPOND_ID,
        enforced=True,
        minutes_before_start=5,
    )
    intents = action.evaluate()
    assert all(i.event_id != "not-a-valid-uuid" for i in intents)
