from datetime import datetime, timedelta

import pytest

from src.padelbot.rules.max_events_per_week import RuleMaxEventsPerWeek
from src.padelbot.utils import Events


@pytest.fixture
def sample_events():
    now = datetime.now().astimezone()
    events = Events()
    events.upcoming = [
        {
            "id": "e1",
            "heading": "Padel Match 1",
            "startTimestamp": (now + timedelta(hours=12)).isoformat(),
            "responses": {"acceptedIds": ["alice-id"], "waitinglistIds": ["bob-id"]},
        },
        {
            "id": "e2",
            "heading": "Padel Match 2",
            "startTimestamp": (now + timedelta(hours=24 + 13)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": ["carol-id"],
            },
        },
        {
            "id": "e3",
            "heading": "Padel Match 3",
            "startTimestamp": (now + timedelta(hours=48 + 14)).isoformat(),
            "responses": {"acceptedIds": ["alice-id"], "waitinglistIds": ["carol-id"]},
        },
    ]
    for event in events.upcoming:
        event["recipients"] = {
            "group": {
                "members": [
                    {
                        "id": "alice-id",
                        "profile": {"id": "alice-profile-id"},
                        "firstName": "Alice",
                        "lastName": "Alison",
                    },
                    {
                        "id": "bob-id",
                        "profile": {"id": "bob-profile-id"},
                        "firstName": "Bob",
                        "lastName": "Bobson",
                    },
                    {
                        "id": "carol-id",
                        "profile": {"id": "carol-profile-id"},
                        "firstName": "Carol",
                        "lastName": "Carolson",
                    },
                ]
            }
        }

    return events


def test_no_removal_when_under_limit(sample_events):
    rule = RuleMaxEventsPerWeek(
        rule_name="max3",
        events=sample_events,
        header_regex="Padel",
        message="Too many events",
        enforced=True,
        max_events=3,
        grace_hours=0,
    )
    removals = rule.evaluate()
    assert removals == []


def test_removal_when_over_limit(sample_events):
    rule = RuleMaxEventsPerWeek(
        rule_name="max2",
        events=sample_events,
        header_regex="Padel",
        message="Too many events",
        enforced=True,
        max_events=2,
        grace_hours=0,
    )
    removals = rule.evaluate()
    assert len(removals) == 1
    player_ids = {r.player_id for r in removals}
    assert player_ids == {"alice-id"}
    event_ids = {r.event_id for r in removals}
    assert event_ids <= {"e3"}


def test_grace_period_excludes_event(sample_events):
    rule = RuleMaxEventsPerWeek(
        rule_name="max2grace24",
        events=sample_events,
        header_regex="Padel",
        message="Too many events",
        enforced=True,
        max_events=2,
        grace_hours=24,
    )
    removals = rule.evaluate()
    assert len(removals) == 0


def test_expirationtimes(sample_events):
    rule = RuleMaxEventsPerWeek(
        rule_name="max1grace24",
        events=sample_events,
        header_regex="Padel",
        message="msg",
        enforced=True,
        max_events=1,
        grace_hours=24,
    )
    expirations = rule.expirationtimes()
    assert len(expirations) == 2
    for t, event in zip(expirations, sample_events.upcoming[1:]):
        expected = datetime.fromisoformat(
            event["startTimestamp"]
        ).astimezone() - timedelta(hours=24)
        assert abs((t - expected).total_seconds()) < 1


def test_include(sample_events):
    rule = RuleMaxEventsPerWeek(
        rule_name="max1grace24",
        events=sample_events,
        header_regex="Padel",
        message="msg",
        enforced=True,
        max_events=1,
        grace_hours=24,
    )
    assert rule._include(sample_events.upcoming[0]) is False
    assert rule._include(sample_events.upcoming[1]) is True
    assert rule._include(sample_events.upcoming[2]) is True

    sample_events.upcoming[1]["heading"] = "Tennis"
    assert rule._include(sample_events.upcoming[0]) is False
    assert rule._include(sample_events.upcoming[1]) is False
    assert rule._include(sample_events.upcoming[2]) is True
