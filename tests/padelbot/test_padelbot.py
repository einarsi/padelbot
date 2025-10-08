from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.padelbot.padelbot import PadelBot
from src.padelbot.rules.rulebase import RuleBase
from src.padelbot.utils import Events


@pytest.fixture
def cfg():
    return {
        "auth": {"username": "user", "password": "pass", "group_id": "group-id"},
        "rules": {
            "rule1": {"rule": "DummyRule1"},
            "rule2": {"rule": "DummyRule2"},
        },
        "general": {"seconds_to_sleep": 10},
    }


@pytest.fixture
def events():
    events = Events()
    events.upcoming = [
        {
            "id": "event1-id",
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": ["carol-id", "david-id"],
            },
        },
        {
            "id": "event2-id",
            "responses": {
                "acceptedIds": ["alice-id", "bob-id"],
                "waitinglistIds": ["carol-id", "david-id"],
            },
        },
    ]

    for event in events.upcoming:
        event["recipients"] = {
            "group": {
                "members": [
                    {
                        "profile": {"id": "alice-profile-id"},
                        "id": "alice-id",
                        "firstName": "Alice",
                        "lastName": "Alison",
                    },
                    {
                        "profile": {"id": "bob-profile-id"},
                        "id": "bob-id",
                        "firstName": "Bob",
                        "lastName": "Bobson",
                    },
                ]
            }
        }
        event["heading"] = f"Padel {event['id']}!"
        event["startTimestamp"] = "2025-10-08T10:00:00+00:00"

    return events


@pytest_asyncio.fixture
async def mockbot(cfg):
    bot = PadelBot(cfg)
    with (
        patch.object(bot.spond, "change_response", new_callable=AsyncMock),
        patch.object(bot.spond, "send_message", new_callable=AsyncMock),
        patch.object(bot.spond, "get_events", new_callable=AsyncMock),
    ):
        yield bot


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_get_events_categorizes_events(self, mockbot):
        now = datetime.now().astimezone()
        events_data = [
            {  # Upcoming
                "id": "upcoming1",
                "startTimestamp": (now + timedelta(days=1)).isoformat(),
                "endTimestamp": (now + timedelta(days=1, hours=2)).isoformat(),
            },
            {  # Previous
                "id": "previous1",
                "startTimestamp": (now - timedelta(days=2)).isoformat(),
                "endTimestamp": (now - timedelta(days=2, hours=-2)).isoformat(),
            },
            {  # Upcoming
                "id": "upcoming2",
                "startTimestamp": (now + timedelta(days=2)).isoformat(),
                "endTimestamp": (now + timedelta(days=2, hours=4)).isoformat(),
            },
            {  # Ongoing
                "id": "ongoing1",
                "startTimestamp": (now - timedelta(hours=1)).isoformat(),
                "endTimestamp": (now + timedelta(hours=1)).isoformat(),
            },
        ]
        mockbot.spond.get_events.return_value = events_data
        events = await mockbot.get_events()

        assert {e["id"] for e in events.upcoming} == {"upcoming1", "upcoming2"}
        assert {e["id"] for e in events.previous} == {"previous1"}
        assert {e["id"] for e in events.ongoing} == {"ongoing1"}

    @pytest.mark.asyncio
    async def test_get_events_empty(self, mockbot):
        mockbot.spond.get_events.return_value = []
        events = await mockbot.get_events()
        assert events.upcoming == []
        assert events.previous == []
        assert events.ongoing == []


class TestGetRules:
    def dummy_create_rule(self, name, events, rule_def):
        class DummyRule:
            def expirationtimes(self):
                return []

            def evaluate(self):
                return []

        return DummyRule()

    @pytest.mark.asyncio
    async def test_get_rules(self, cfg, events):
        with patch("src.padelbot.padelbot.create_rule", new=self.dummy_create_rule):
            bot = PadelBot(cfg)
            rules = bot.get_rules(events)
        assert len(rules) == 2
        assert all(
            hasattr(r, "expirationtimes") and hasattr(r, "evaluate") for r in rules
        )

    @pytest.mark.asyncio
    async def test_get_rules_empty(self, cfg, events):
        cfg_empty = dict(cfg)
        cfg_empty["rules"] = {}
        bot = PadelBot(cfg_empty)
        rules = bot.get_rules(events)
        assert rules == []


class TestGetSleepTime:
    def create_dummy_expirationtimes(self, dt: datetime) -> tuple[list[datetime], ...]:
        now = datetime.now().astimezone()
        return (
            [now + timedelta(hours=2), dt, now + timedelta(hours=1)],
            [now + timedelta(hours=1), now + timedelta(hours=3)],
        )

    def make_dummy_bot(self, cfg, expirationtimes_lists: tuple[list[datetime], ...]):
        class DummyRule(RuleBase):
            def __init__(self, expirationtimes_list):
                self.expirationtimes_list = expirationtimes_list

            def evaluate(self):
                return []

            def expirationtimes(self):
                return self.expirationtimes_list

        class DummyPadelBot(PadelBot):
            def get_rules(self, events) -> list[RuleBase]:
                return [
                    DummyRule(expirationtimes_list)
                    for expirationtimes_list in expirationtimes_lists
                ]

        return DummyPadelBot(cfg)

    @pytest.mark.asyncio
    async def test_no_rule_end_times(self, cfg, events):
        bot = self.make_dummy_bot(cfg, ([],))
        sleep = bot.get_sleep_time(600, events)
        assert sleep == 600

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "desc,delta,expected_offset",
        [
            (
                "t > 600 seconds until next rule end time",
                timedelta(minutes=15),
                600,
            ),
            (
                "60 < t < 600 seconds until next rule end time",
                timedelta(seconds=258),
                258 - 59,
            ),
            (
                "10 < t < 60 seconds until next rule end time",
                timedelta(seconds=37),
                37 - 27,
            ),
            (
                "t < 10 seconds until next rule end time",
                timedelta(seconds=8),
                8 - 1,
            ),
        ],
    )
    async def test_next_rule_end_time_parametrized(
        self, desc, delta, expected_offset, cfg, events
    ):
        """Test get_sleep_time for various next rule end time scenarios"""
        now = datetime.now().astimezone()
        bot = self.make_dummy_bot(cfg, self.create_dummy_expirationtimes(now + delta))
        sleep = bot.get_sleep_time(600, events)
        assert abs(sleep - expected_offset) < 1, (
            f"{desc}: got {sleep}, expected {expected_offset}"
        )


class TestUpdateEventsWithRemoval:
    @pytest.mark.asyncio
    async def test_removes_from_accepted(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("alice-id", "event1-id", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["bob-id"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == [
            "carol-id",
            "david-id",
        ]

    @pytest.mark.asyncio
    async def test_removes_from_waitinglist(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("carol-id", "event1-id", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["alice-id", "bob-id"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == ["david-id"]

    @pytest.mark.asyncio
    async def test_no_removal_if_not_present(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("playerX-id", "event1-id", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["alice-id", "bob-id"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == [
            "carol-id",
            "david-id",
        ]

    @pytest.mark.asyncio
    async def test_no_removal_if_event_id_not_found(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("alice-id", "eventX-id", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["alice-id", "bob-id"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == [
            "carol-id",
            "david-id",
        ]


class TestRemovePlayerFromEvent:
    @pytest.mark.asyncio
    async def test_enforce_true_calls_spond(self, mockbot, events):
        result = await mockbot.remove_player_from_event(
            player_id="alice-id",
            event_id="event1-id",
            message="bye",
            events=events.upcoming,
            enforce=True,
        )
        assert result is True
        mockbot.spond.change_response.assert_awaited_once_with(
            "event1-id", "alice-id", {"accepted": "false"}
        )
        mockbot.spond.send_message.assert_awaited_once_with(
            text="bye", user="alice-profile-id", group_uid="group-id"
        )

    @pytest.mark.asyncio
    async def test_enforce_false_does_not_call_spond(self, mockbot, events):
        result = await mockbot.remove_player_from_event(
            player_id="alice-id",
            event_id="event1-id",
            message="bye",
            events=events.upcoming,
            enforce=False,
        )
        assert result is False
        mockbot.spond.change_response.assert_not_awaited()
        mockbot.spond.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_player_not_removed_if_event_id_not_found(self, mockbot, events):
        result = await mockbot.remove_player_from_event(
            player_id="alice-id",
            event_id="eventX-id",
            message="bye",
            events=events.upcoming,
            enforce=True,
        )
        assert result is False
        mockbot.spond.change_response.assert_not_awaited()
        mockbot.spond.send_message.assert_not_awaited()
