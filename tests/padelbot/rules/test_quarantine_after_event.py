from datetime import datetime, timedelta

import pytest

from src.padelbot.rules.quarantine_after_event import RuleQuarantineAfterEvent
from src.padelbot.utils import Events


@pytest.fixture
def sample_events():
    now = datetime.now().astimezone()
    events = Events()
    events.previous = [
        {
            "id": "ep1",
            "heading": "Mexicano series 1",
            "seriesId": "series-mexicano",
            "startTimestamp": (now - timedelta(days=6, hours=13)).isoformat(),
            "endTimestamp": (now - timedelta(days=6, hours=12)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": ["carol-id"],
            },
        },
        {
            "id": "ep2",
            "heading": "Americano series 1",
            "seriesId": "series-americano",
            "startTimestamp": (now - timedelta(hours=13)).isoformat(),
            "endTimestamp": (now - timedelta(hours=12)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": ["carol-id"],
            },
        },
    ]
    events.upcoming = [
        {
            "id": "eu1",
            "heading": "Mexicano series 2",
            "seriesId": "series-mexicano",
            "startTimestamp": (now + timedelta(days=1, hours=11)).isoformat(),
            "endTimestamp": (now + timedelta(days=1, hours=12)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": ["carol-id"],
            },
        },
        {
            "id": "eu2",
            "heading": "Americano series 2",
            "seriesId": "series-americano",
            "startTimestamp": (now + timedelta(days=6, hours=11)).isoformat(),
            "endTimestamp": (now + timedelta(days=6, hours=12)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "carol-id"],
                "waitinglistIds": ["bob-id"],
            },
        },
        {
            "id": "eu3",
            "heading": "Open Play",
            "seriesId": "series-openplay",
            "startTimestamp": (now + timedelta(days=2, hours=11)).isoformat(),
            "endTimestamp": (now + timedelta(days=2, hours=12)).isoformat(),
            "responses": {
                "acceptedIds": ["alice-id", "bob-id", "carol-id"],
                "waitinglistIds": [],
            },
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


def test_removal_when_inside_quarantine(sample_events):
    rule = RuleQuarantineAfterEvent(
        rule_name="quarantine1",
        events=sample_events,
        header_regex="Americano",
        message="msg",
        enforced=True,
        quarantine_hours=24,
    )
    removals = rule.evaluate()
    assert len(removals) == 2
    assert {r.player_id for r in removals} == {"alice-id", "bob-id"}


def test_no_removal_when_outside_quarantine(sample_events):
    rule = RuleQuarantineAfterEvent(
        rule_name="quarantine1",
        events=sample_events,
        header_regex="Americano",
        message="msg",
        enforced=True,
        quarantine_hours=11,
    )
    removals = rule.evaluate()
    assert removals == []


def test_no_removal_when_no_previous_event(sample_events):
    rule = RuleQuarantineAfterEvent(
        rule_name="quarantine1",
        events=sample_events,
        header_regex="Nonexistent Event",
        message="msg",
        enforced=True,
        quarantine_hours=24,
    )
    removals = rule.evaluate()
    assert removals == []


def test_isactive_within_quarantine_time(sample_events):
    rule = RuleQuarantineAfterEvent(
        rule_name="quarantine1",
        events=sample_events,
        header_regex="Americano|Mexicano",
        message="msg",
        enforced=True,
        quarantine_hours=24,
    )
    assert rule._isactive(sample_events.upcoming[0]) is False
    assert rule._isactive(sample_events.upcoming[1]) is True


def test_expirationtimes(sample_events):
    rule = RuleQuarantineAfterEvent(
        rule_name="quarantine1",
        events=sample_events,
        header_regex="Americano|Mexicano",
        message="msg",
        enforced=True,
        quarantine_hours=24,
    )
    expirations = rule.expirationtimes()
    assert len(expirations) == 1
    expected_expiration = datetime.fromisoformat(
        sample_events.previous[1]["endTimestamp"]
    ).astimezone() + timedelta(hours=24)
    assert expirations[0] == expected_expiration
    assert expirations[0] > datetime.now().astimezone()


def test_include(sample_events):
    rule = RuleQuarantineAfterEvent(
        rule_name="quarantine1",
        events=sample_events,
        header_regex="Americano",
        message="msg",
        enforced=True,
        quarantine_hours=24,
    )
    assert rule._include(sample_events.upcoming[0]) is False
    assert rule._include(sample_events.upcoming[1]) is True
    rule.header_regex = "Americano|Mexicano"
    assert rule._include(sample_events.upcoming[0]) is True
    assert rule._include(sample_events.upcoming[1]) is True
