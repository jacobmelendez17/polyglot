"""Schemas for the dev sandbox."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DevStateOut(BaseModel):
    dev_mode: bool
    srs_scale: float
    srs_scale_description: str
    presets: dict[str, float]


class DevModeRequest(BaseModel):
    enabled: bool
    # A preset name ("fast", "instant", "off") or a raw multiplier string.
    scale: str | None = Field(default=None, max_length=20)


class UnlockAllRequest(BaseModel):
    up_to_level: int | None = Field(default=None, ge=1, le=1000)


class SetStageRequest(BaseModel):
    item_type: str = Field(pattern="^(vocabulary|grammar)$")
    item_id: str = Field(min_length=1, max_length=64)
    stage: int = Field(ge=1, le=9)


class DevActionOut(BaseModel):
    ok: bool = True
    detail: dict
