from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

import src.padelbot.padelbot as padelbot_mod
from src.padelbot.padelbot import PadelBot
from src.padelbot.rules.rulebase import RuleBase
from src.padelbot.utils import Events


@pytest.fixture
def cfg():
    return {
        "auth": {"username": "u", "password": "p", "group_id": "g"},
        "rules": {
            "rule1": {"rule": "DummyRule"},
            "rule2": {"rule": "DummyRule"},
        },
        "general": {"seconds_to_sleep": 10},
    }


@pytest.fixture
def events():
    events = Events()
    events.upcoming = [
        {
            "id": "e1",
            "responses": {
                "acceptedIds": ["p1", "p2"],
                "waitinglistIds": ["p3", "p4"],
            },
        },
        {
            "id": "e2",
            "responses": {
                "acceptedIds": ["p1", "p2"],
                "waitinglistIds": ["p3", "p4"],
            },
        },
    ]
    return events


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_get_events_categorizes_events(self, cfg):
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
        with patch.object(
            padelbot_mod.spond.Spond, "get_events", new_callable=AsyncMock
        ) as mock_get_events:
            mock_get_events.return_value = events_data
            bot = PadelBot(cfg)
            events = await bot.get_events()

        def get_ids(events):
            return {e["id"] for e in events}

        assert get_ids(events.upcoming) == {"upcoming1", "upcoming2"}
        assert get_ids(events.previous) == {"previous1"}
        assert get_ids(events.ongoing) == {"ongoing1"}

    @pytest.mark.asyncio
    async def test_get_events_empty(self, cfg):
        with patch.object(
            padelbot_mod.spond.Spond, "get_events", new_callable=AsyncMock
        ) as mock_get_events:
            mock_get_events.return_value = []
            bot = PadelBot(cfg)
            events = await bot.get_events()
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
        print(rules)
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
        # Patch get_rules to return rules with specified expirationtimes
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
        updated = bot.update_events_with_removal("p1", "e1", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["p2"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == ["p3", "p4"]

    @pytest.mark.asyncio
    async def test_removes_from_waitinglist(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("p3", "e1", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["p1", "p2"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == ["p4"]

    @pytest.mark.asyncio
    async def test_no_removal_if_not_present(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("pX", "e1", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["p1", "p2"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == ["p3", "p4"]

    @pytest.mark.asyncio
    async def test_no_removal_if_event_id_not_found(self, cfg, events):
        bot = PadelBot(cfg)
        updated = bot.update_events_with_removal("p1", "eX", events)
        assert updated.upcoming[0]["responses"]["acceptedIds"] == ["p1", "p2"]
        assert updated.upcoming[0]["responses"]["waitinglistIds"] == ["p3", "p4"]
