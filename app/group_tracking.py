from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validation import normalize_symbol


class SavedGroupNameConflict(ValueError):
    """Raised when a saved group name is already in use."""


class SavedGroupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    members: list[str] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name or any(ord(character) < 32 for character in name):
            raise ValueError("group name must be printable text")
        return name

    @field_validator("members")
    @classmethod
    def normalize_members(cls, values: list[Any]) -> list[str]:
        members: list[str] = []
        seen: set[str] = set()
        for value in values:
            symbol = normalize_symbol(value)
            if symbol not in seen:
                members.append(symbol)
                seen.add(symbol)
        if not members:
            raise ValueError("at least one member is required")
        return members
