from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="SpondTournamentCreateResponse")


@_attrs_define
class SpondTournamentCreateResponse:
    """
    Attributes:
        tournament_id (UUID):
        view_url (str):
        edit_url (str):
        skipped_spond_ids (list[UUID] | Unset): Spond IDs that could not be resolved to users. Only populated on
            creation (201); empty on idempotent returns (200).
    """

    tournament_id: UUID
    view_url: str
    edit_url: str
    skipped_spond_ids: list[UUID] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        tournament_id = str(self.tournament_id)

        view_url = self.view_url

        edit_url = self.edit_url

        skipped_spond_ids: list[str] | Unset = UNSET
        if not isinstance(self.skipped_spond_ids, Unset):
            skipped_spond_ids = []
            for skipped_spond_ids_item_data in self.skipped_spond_ids:
                skipped_spond_ids_item = str(skipped_spond_ids_item_data)
                skipped_spond_ids.append(skipped_spond_ids_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "tournament_id": tournament_id,
                "view_url": view_url,
                "edit_url": edit_url,
            }
        )
        if skipped_spond_ids is not UNSET:
            field_dict["skipped_spond_ids"] = skipped_spond_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        tournament_id = UUID(d.pop("tournament_id"))

        view_url = d.pop("view_url")

        edit_url = d.pop("edit_url")

        _skipped_spond_ids = d.pop("skipped_spond_ids", UNSET)
        skipped_spond_ids: list[UUID] | Unset = UNSET
        if _skipped_spond_ids is not UNSET:
            skipped_spond_ids = []
            for skipped_spond_ids_item_data in _skipped_spond_ids:
                skipped_spond_ids_item = UUID(skipped_spond_ids_item_data)

                skipped_spond_ids.append(skipped_spond_ids_item)

        spond_tournament_create_response = cls(
            tournament_id=tournament_id,
            view_url=view_url,
            edit_url=edit_url,
            skipped_spond_ids=skipped_spond_ids,
        )

        spond_tournament_create_response.additional_properties = d
        return spond_tournament_create_response

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
