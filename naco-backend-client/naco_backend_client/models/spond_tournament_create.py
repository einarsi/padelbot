from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="SpondTournamentCreate")


@_attrs_define
class SpondTournamentCreate:
    """
    Attributes:
        name (str):
        type_ (str):
        external_id (str):
        created_by_spond_id (UUID):
        points_to_win (int | None | Unset):
        player_spond_ids (list[UUID] | Unset):
        court_names (list[str] | Unset):
        scheduled_start (datetime.datetime | None | Unset):
        scheduled_end (datetime.datetime | None | Unset):
    """

    name: str
    type_: str
    external_id: str
    created_by_spond_id: UUID
    points_to_win: int | None | Unset = UNSET
    player_spond_ids: list[UUID] | Unset = UNSET
    court_names: list[str] | Unset = UNSET
    scheduled_start: datetime.datetime | None | Unset = UNSET
    scheduled_end: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        type_ = self.type_

        external_id = self.external_id

        created_by_spond_id = str(self.created_by_spond_id)

        points_to_win: int | None | Unset
        if isinstance(self.points_to_win, Unset):
            points_to_win = UNSET
        else:
            points_to_win = self.points_to_win

        player_spond_ids: list[str] | Unset = UNSET
        if not isinstance(self.player_spond_ids, Unset):
            player_spond_ids = []
            for player_spond_ids_item_data in self.player_spond_ids:
                player_spond_ids_item = str(player_spond_ids_item_data)
                player_spond_ids.append(player_spond_ids_item)

        court_names: list[str] | Unset = UNSET
        if not isinstance(self.court_names, Unset):
            court_names = self.court_names

        scheduled_start: None | str | Unset
        if isinstance(self.scheduled_start, Unset):
            scheduled_start = UNSET
        elif isinstance(self.scheduled_start, datetime.datetime):
            scheduled_start = self.scheduled_start.isoformat()
        else:
            scheduled_start = self.scheduled_start

        scheduled_end: None | str | Unset
        if isinstance(self.scheduled_end, Unset):
            scheduled_end = UNSET
        elif isinstance(self.scheduled_end, datetime.datetime):
            scheduled_end = self.scheduled_end.isoformat()
        else:
            scheduled_end = self.scheduled_end

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "type": type_,
                "external_id": external_id,
                "created_by_spond_id": created_by_spond_id,
            }
        )
        if points_to_win is not UNSET:
            field_dict["points_to_win"] = points_to_win
        if player_spond_ids is not UNSET:
            field_dict["player_spond_ids"] = player_spond_ids
        if court_names is not UNSET:
            field_dict["court_names"] = court_names
        if scheduled_start is not UNSET:
            field_dict["scheduled_start"] = scheduled_start
        if scheduled_end is not UNSET:
            field_dict["scheduled_end"] = scheduled_end

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        type_ = d.pop("type")

        external_id = d.pop("external_id")

        created_by_spond_id = UUID(d.pop("created_by_spond_id"))

        def _parse_points_to_win(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        points_to_win = _parse_points_to_win(d.pop("points_to_win", UNSET))

        _player_spond_ids = d.pop("player_spond_ids", UNSET)
        player_spond_ids: list[UUID] | Unset = UNSET
        if _player_spond_ids is not UNSET:
            player_spond_ids = []
            for player_spond_ids_item_data in _player_spond_ids:
                player_spond_ids_item = UUID(player_spond_ids_item_data)

                player_spond_ids.append(player_spond_ids_item)

        court_names = cast(list[str], d.pop("court_names", UNSET))

        def _parse_scheduled_start(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                scheduled_start_type_0 = isoparse(data)

                return scheduled_start_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        scheduled_start = _parse_scheduled_start(d.pop("scheduled_start", UNSET))

        def _parse_scheduled_end(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                scheduled_end_type_0 = isoparse(data)

                return scheduled_end_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        scheduled_end = _parse_scheduled_end(d.pop("scheduled_end", UNSET))

        spond_tournament_create = cls(
            name=name,
            type_=type_,
            external_id=external_id,
            created_by_spond_id=created_by_spond_id,
            points_to_win=points_to_win,
            player_spond_ids=player_spond_ids,
            court_names=court_names,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )

        spond_tournament_create.additional_properties = d
        return spond_tournament_create

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
