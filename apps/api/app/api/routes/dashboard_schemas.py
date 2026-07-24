"""Request/response schemas for dashboard layout and guided tours."""
from __future__ import annotations

from pydantic import BaseModel, Field


class WidgetCatalogEntry(BaseModel):
    key: str
    title: str
    description: str
    default: bool
    span: int
    min_span: int
    max_span: int


class LayoutEntryIn(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    span: int | None = Field(default=None, ge=1, le=6)


class LayoutIn(BaseModel):
    # Bounded so a hostile client can't post a million entries; the domain layer
    # trims to MAX_WIDGETS after unknown keys are dropped.
    widgets: list[LayoutEntryIn] = Field(default_factory=list, max_length=96)
    version: int = 1


class LayoutOut(BaseModel):
    version: int
    widgets: list[dict]


class DashboardOut(BaseModel):
    layout: LayoutOut
    catalog: list[WidgetCatalogEntry]
    grid_columns: int
    max_widgets: int


class TourStateOut(BaseModel):
    tour_key: str
    step_index: int
    completed: bool
    skipped: bool
    completed_at: str | None = None


class TourStepIn(BaseModel):
    step_index: int = Field(ge=0, le=20)


class TourCompleteIn(BaseModel):
    skipped: bool = False
