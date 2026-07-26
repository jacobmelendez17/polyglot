"""Capability-based authorization (PLANNING §4).

Roles are NOT strictly hierarchical: a moderator manages forums but cannot edit
curriculum; a content_editor edits curriculum but cannot manage users. We map each
role to an explicit set of capabilities in ONE place, unit-tested, so a route asks
\"does this user have capability X?\" rather than \"is this user role >= Y?\".
"""
from __future__ import annotations

import enum

from app.models.enums import UserRole


class Capability(str, enum.Enum):
    # content
    content_view_draft = "content_view_draft"
    content_edit = "content_edit"
    content_publish = "content_publish"
    content_archive = "content_archive"
    content_import = "content_import"
    # forums / community
    forum_moderate = "forum_moderate"
    # users & subscriptions
    user_manage = "user_manage"
    subscription_manage = "subscription_manage"
    # destructive / owner-only
    permanent_delete_approve = "permanent_delete_approve"
    # admin surface access (feedback, audit logs, dashboards)
    admin_panel = "admin_panel"
    feedback_manage = "feedback_manage"
    audit_view = "audit_view"


_CONTENT_CAPS = {
    Capability.content_view_draft,
    Capability.content_edit,
    Capability.content_publish,
    Capability.content_archive,
    Capability.content_import,
}

# Explicit, non-hierarchical role -> capability mapping.
ROLE_CAPABILITIES: dict[UserRole, frozenset[Capability]] = {
    UserRole.user: frozenset(),
    UserRole.beta_tester: frozenset(),
    UserRole.moderator: frozenset({
        Capability.forum_moderate,
        Capability.admin_panel,
        Capability.feedback_manage,
    }),
    UserRole.content_editor: frozenset({
        *_CONTENT_CAPS,
        Capability.admin_panel,
    }),
    UserRole.admin: frozenset({
        *_CONTENT_CAPS,
        Capability.forum_moderate,
        Capability.user_manage,
        Capability.subscription_manage,
        Capability.admin_panel,
        Capability.feedback_manage,
        Capability.audit_view,
    }),
    UserRole.owner: frozenset({
        *_CONTENT_CAPS,
        Capability.forum_moderate,
        Capability.user_manage,
        Capability.subscription_manage,
        Capability.permanent_delete_approve,  # owner-only
        Capability.admin_panel,
        Capability.feedback_manage,
        Capability.audit_view,
    }),
}


def capabilities_for(role: UserRole) -> frozenset[Capability]:
    return ROLE_CAPABILITIES.get(role, frozenset())


def has_capability(role: UserRole, capability: Capability) -> bool:
    return capability in capabilities_for(role)
