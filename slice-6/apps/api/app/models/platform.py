"""Dashboard, widgets, intermissions, changelog, feedback, subscriptions,
audit logs, content versioning, imports, and deletion approvals."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, ContentMixin, TimestampMixin, fk, pk


class DashboardWidget(Base, TimestampMixin):
    """Catalog of widget types + whether they are default-on."""

    __tablename__ = "dashboard_widgets"
    id: Mapped[uuid.UUID] = pk()
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class UserWidgetLayout(Base, TimestampMixin):
    """Per-user layout, persisted so it follows the user across devices (§15)."""

    __tablename__ = "user_widget_layouts"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    layout: Mapped[list] = mapped_column(JSON, default=list)  # [{widget,x,y,w,h,config}]


class Intermission(Base, ContentMixin):
    __tablename__ = "intermissions"
    id: Mapped[uuid.UUID] = pk()
    module_id: Mapped[uuid.UUID | None] = fk("modules.id", nullable=True)
    trigger: Mapped[dict] = mapped_column(JSON, default=dict)
    title: Mapped[str] = mapped_column(String(200))
    body_rich: Mapped[str] = mapped_column(Text, default="")


class UserIntermissionView(Base, TimestampMixin):
    __tablename__ = "user_intermission_views"
    __table_args__ = (UniqueConstraint("user_id", "intermission_id", name="uq_user_interm"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    intermission_id: Mapped[uuid.UUID] = fk("intermissions.id", nullable=False)
    viewed_at: Mapped[datetime | None]


class ChangelogEntry(Base, ContentMixin):
    __tablename__ = "changelog_entries"
    id: Mapped[uuid.UUID] = pk()
    type: Mapped[str] = mapped_column(String(20))  # feature|fix|content|announcement
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None]
    author_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)


class UserChangelogRead(Base, TimestampMixin):
    __tablename__ = "user_changelog_reads"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    last_read_at: Mapped[datetime | None]


class FeedbackTicket(Base, TimestampMixin):
    """Support/feedback; also emailed to owner (§30). Filterable by state + pinned."""

    __tablename__ = "feedback_tickets"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="general")
    route: Mapped[str] = mapped_column(String(300), default="")
    browser: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    screenshot_asset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    state: Mapped[str] = mapped_column(String(12), default="unanswered")  # unanswered|answered
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent_at: Mapped[datetime | None]


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    # tier: free_beta | lifetime | monthly | annual
    tier: Mapped[str] = mapped_column(String(20), default="free_beta")
    status: Mapped[str] = mapped_column(String(20), default="active")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_period_end: Mapped[datetime | None]
    canceled_at: Mapped[datetime | None]


class AdminAuditLog(Base, TimestampMixin):
    """Every admin mutation, written in the same transaction as the action (§22)."""

    __tablename__ = "admin_audit_logs"
    id: Mapped[uuid.UUID] = pk()
    actor_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80))
    target_table: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ContentVersion(Base, TimestampMixin):
    """Tracks curriculum changes over time (§23)."""

    __tablename__ = "content_versions"
    id: Mapped[uuid.UUID] = pk()
    table_name: Mapped[str] = mapped_column(String(60), index=True)
    row_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    changed_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)


class ContentImport(Base, TimestampMixin):
    """Record of each CSV import, with the full warning/error report."""

    __tablename__ = "content_imports"
    id: Mapped[uuid.UUID] = pk()
    filename: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))   # vocabulary | grammar
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)


class DeletionApproval(Base, TimestampMixin):
    """Permanent deletion requires owner approval (§22)."""

    __tablename__ = "deletion_approvals"
    id: Mapped[uuid.UUID] = pk()
    target_table: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[uuid.UUID] = mapped_column(GUID())
    requested_by: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    approved_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)  # must be owner
    executed_at: Mapped[datetime | None]
