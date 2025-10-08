import pytest

from src.padelbot.utils import (
    eventid_to_event,
    get_last_event_in_series,
    get_registered_player_names,
    memberid_to_member,
)


# Group get_registered_player_names tests in a class
class TestGetRegisteredPlayerNames:
    @pytest.fixture
    def event(self):
        return {
            "responses": {"acceptedIds": ["1", "2"], "waitinglistIds": ["3"]},
            "recipients": {
                "group": {
                    "members": [
                        {"id": "1", "firstName": "Alice", "lastName": "Smith"},
                        {"id": "2", "firstName": "Bob", "lastName": "Jones"},
                        {"id": "3", "firstName": "Charlie", "lastName": "Brown"},
                        {"id": "4", "firstName": "Dana", "lastName": "White"},
                    ]
                }
            },
        }

    def test_registered_names(self, event):
        names = get_registered_player_names(event)
        assert len(names) == 3
        assert set(names) == {"Alice Smith", "Bob Jones", "Charlie Brown"}

    def test_empty_waiting_list(self, event):
        event["responses"]["waitinglistIds"] = []
        names = get_registered_player_names(event)
        assert names == ["Alice Smith", "Bob Jones"]

    def test_missing_member(self, event):
        # Members with responses should always be on the member list.
        # But just in case something goes wrong we at least shouldn't get invalid data.
        event["responses"]["acceptedIds"].append("999")
        with pytest.raises(ValueError):
            get_registered_player_names(event)


class TestGetLastEventInSeries:
    @pytest.fixture
    def events(self):
        return [
            {"id": "e1", "seriesId": "s1", "startTimestamp": "2025-09-01T10:00:00"},
            {"id": "e2", "seriesId": "s1", "startTimestamp": "2025-09-10T10:00:00"},
            {"id": "e3", "seriesId": "s2", "startTimestamp": "2025-09-15T10:00:00"},
            {"id": "e4", "seriesId": "s1", "startTimestamp": "2025-09-20T10:00:00"},
            {"id": "e5", "seriesId": "s2", "startTimestamp": "2025-09-30T10:00:00"},
        ]

    def test_last_event_found(self, events):
        # Use an event from series s1
        event = events[1]
        last = get_last_event_in_series(event, events)
        assert last is not None
        assert last["id"] == "e4"
        assert last["startTimestamp"] == "2025-09-20T10:00:00"

    def test_no_matching_series(self, events):
        # Use an event with a seriesId not in the list
        event = {
            "id": "eX",
            "seriesId": "notfound",
            "startTimestamp": "2025-09-01T10:00:00",
        }
        last = get_last_event_in_series(event, events)
        assert last is None


class TestEventIdToEvent:
    @pytest.fixture
    def events(self):
        return [
            {"id": "event1", "heading": "Padel Monday"},
            {"id": "event2", "heading": "Padel Thursday"},
        ]

    def test_found(self, events):
        event = eventid_to_event("event2", events)
        assert event["heading"] == "Padel Thursday"
        assert event["id"] == "event2"

    def test_not_found(self, events):
        with pytest.raises(ValueError) as exc:
            eventid_to_event("999", events)
        assert "Event ID 999 not found" in str(exc.value)


class TestMemberIdToMember:
    @pytest.fixture
    def members(self):
        return [
            {"id": "1", "firstName": "Alice"},
            {"id": "2", "firstName": "Bob"},
            {"id": "3", "firstName": "Charlie"},
        ]

    def test_memberid_to_member_found(self, members):
        member = memberid_to_member("2", members)
        assert member["firstName"] == "Bob"
        assert member["id"] == "2"

    def test_memberid_to_member_not_found(self, members):
        with pytest.raises(ValueError) as exc:
            memberid_to_member("999", members)
        assert "Member ID 999 not found" in str(exc.value)
