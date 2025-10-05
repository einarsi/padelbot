import pytest

import src.padelbot.padelbot as padelbot_mod
from src.padelbot.padelbot import PadelBot
from src.padelbot.utils import Events


class TestGetEvents:
    @pytest.fixture
    def cfg(self):
        return {
            "auth": {"username": "u", "password": "p", "group_id": "g"},
            "rules": {},
            "general": {"seconds_to_sleep": 10},
        }

    @pytest.mark.asyncio
    async def test_get_events_categorizes_events(self, monkeypatch, cfg):
        from datetime import datetime, timedelta

        dt_now = datetime.now().astimezone()

        events_data = [
            {  # Upcoming
                "id": "upcoming1",
                "startTimestamp": (dt_now + timedelta(days=1)).isoformat(),
                "endTimestamp": (dt_now + timedelta(days=1, hours=2)).isoformat(),
            },
            {  # Previous
                "id": "previous1",
                "startTimestamp": (dt_now - timedelta(days=2)).isoformat(),
                "endTimestamp": (dt_now - timedelta(days=2, hours=-2)).isoformat(),
            },
            {  # Upcoming
                "id": "upcoming2",
                "startTimestamp": (dt_now + timedelta(days=2)).isoformat(),
                "endTimestamp": (dt_now + timedelta(days=2, hours=4)).isoformat(),
            },
            {  # Ongoing
                "id": "ongoing1",
                "startTimestamp": (dt_now - timedelta(hours=1)).isoformat(),
                "endTimestamp": (dt_now + timedelta(hours=1)).isoformat(),
            },
        ]

        # Patch Spond.get_events to return a mix of previous, ongoing, and upcoming events
        class DummySpond:
            def __init__(self, *a, **kw):
                pass

            async def get_events(self, *a, **kw):
                return events_data

        monkeypatch.setattr(padelbot_mod.spond, "Spond", DummySpond)
        bot = PadelBot(cfg)
        events = await bot.get_events()

        def get_ids(events):
            return {e["id"] for e in events}

        assert get_ids(events.upcoming) == {"upcoming1", "upcoming2"}
        assert get_ids(events.previous) == {"previous1"}
        assert get_ids(events.ongoing) == {"ongoing1"}

    @pytest.mark.asyncio
    async def test_get_events_empty(self, monkeypatch, cfg):
        class DummySpond:
            def __init__(self, *a, **kw):
                pass

            async def get_events(self, *a, **kw):
                return []

        monkeypatch.setattr(padelbot_mod.spond, "Spond", DummySpond)
        bot = PadelBot(cfg)
        events = await bot.get_events()
        assert events.upcoming == []
        assert events.previous == []
        assert events.ongoing == []


# Automatically patch spond.Spond for all tests in this file
@pytest.fixture(autouse=True)
def patch_spond(monkeypatch):
    class DummySpond:
        def __init__(self, *a, **kw):
            pass

    monkeypatch.setattr(padelbot_mod.spond, "Spond", DummySpond)


# Group PadelBot tests in a class
class TestGetRules:
    @pytest.fixture
    def events(self):
        return Events()

    @pytest.fixture
    def cfg(self):
        return {
            "auth": {"username": "u", "password": "p", "group_id": "g"},
            "rules": {
                "rule1": {"rule": "DummyRule"},
                "rule2": {"rule": "DummyRule"},
            },
            "general": {"seconds_to_sleep": 10},
        }

    def dummy_create_rule(self, name, events, rule_def):
        class DummyRule:
            def expirationtimes(self):
                return []

            def evaluate(self):
                return []

        return DummyRule()

    def test_get_rules(self, monkeypatch, cfg, events):
        monkeypatch.setattr(padelbot_mod, "create_rule", self.dummy_create_rule)
        bot = PadelBot(cfg)
        rules = bot.get_rules(events)
        assert len(rules) == 2
        print(rules)
        assert all(
            hasattr(r, "expirationtimes") and hasattr(r, "evaluate") for r in rules
        )

    def test_get_rules_empty(self, cfg, events):
        cfg_empty = dict(cfg)
        cfg_empty["rules"] = {}
        bot = PadelBot(cfg_empty)
        rules = bot.get_rules(events)
        assert rules == []
