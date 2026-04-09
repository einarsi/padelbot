from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="User")


@_attrs_define
class User:
    """
    Attributes:
        id (UUID):
        username (str):
        first_name (str):
        last_name (str):
        ranking (float):
        name (str):
        email (None | str | Unset):
        spond_profile_id (None | Unset | UUID):
    """

    id: UUID
    username: str
    first_name: str
    last_name: str
    ranking: float
    name: str
    email: None | str | Unset = UNSET
    spond_profile_id: None | Unset | UUID = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        username = self.username

        first_name = self.first_name

        last_name = self.last_name

        ranking = self.ranking

        name = self.name

        email: None | str | Unset
        if isinstance(self.email, Unset):
            email = UNSET
        else:
            email = self.email

        spond_profile_id: None | str | Unset
        if isinstance(self.spond_profile_id, Unset):
            spond_profile_id = UNSET
        elif isinstance(self.spond_profile_id, UUID):
            spond_profile_id = str(self.spond_profile_id)
        else:
            spond_profile_id = self.spond_profile_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "ranking": ranking,
                "name": name,
            }
        )
        if email is not UNSET:
            field_dict["email"] = email
        if spond_profile_id is not UNSET:
            field_dict["spond_profile_id"] = spond_profile_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        username = d.pop("username")

        first_name = d.pop("first_name")

        last_name = d.pop("last_name")

        ranking = d.pop("ranking")

        name = d.pop("name")

        def _parse_email(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        email = _parse_email(d.pop("email", UNSET))

        def _parse_spond_profile_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                spond_profile_id_type_0 = UUID(data)

                return spond_profile_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        spond_profile_id = _parse_spond_profile_id(d.pop("spond_profile_id", UNSET))

        user = cls(
            id=id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            ranking=ranking,
            name=name,
            email=email,
            spond_profile_id=spond_profile_id,
        )

        user.additional_properties = d
        return user

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
