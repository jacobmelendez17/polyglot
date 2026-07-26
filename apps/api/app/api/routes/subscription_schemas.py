"""Schemas for subscriptions, billing, and the dev sandbox."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EntitlementOut(BaseModel):
    status: str
    full_access: bool
    max_free_level: int
    access_until: str | None = None
    cancel_at_period_end: bool = False
    price_interval: str | None = None
    prices: dict[str, str] = Field(default_factory=dict)


class CheckoutRequest(BaseModel):
    interval: str = Field(pattern="^(month|year)$")


class CheckoutOut(BaseModel):
    url: str


class PortalOut(BaseModel):
    url: str


class AdminSetStatusRequest(BaseModel):
    status: str = Field(
        pattern="^(free|beta|lifetime|paid_active|paid_past_due|paid_canceled)$"
    )


# --- dev sandbox ---------------------------------------------------------

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
