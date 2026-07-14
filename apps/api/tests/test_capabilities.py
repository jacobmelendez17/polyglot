from app.auth.capabilities import Capability, capabilities_for, has_capability
from app.models.enums import UserRole


def test_regular_user_has_no_capabilities():
    assert capabilities_for(UserRole.user) == frozenset()
    assert capabilities_for(UserRole.beta_tester) == frozenset()


def test_content_editor_edits_but_cannot_manage_users():
    r = UserRole.content_editor
    assert has_capability(r, Capability.content_edit)
    assert has_capability(r, Capability.content_publish)
    assert not has_capability(r, Capability.user_manage)
    assert not has_capability(r, Capability.forum_moderate)


def test_moderator_moderates_but_cannot_edit_curriculum():
    r = UserRole.moderator
    assert has_capability(r, Capability.forum_moderate)
    assert not has_capability(r, Capability.content_edit)
    assert not has_capability(r, Capability.user_manage)


def test_only_owner_can_approve_permanent_delete():
    assert has_capability(UserRole.owner, Capability.permanent_delete_approve)
    assert not has_capability(UserRole.admin, Capability.permanent_delete_approve)


def test_admin_has_broad_but_not_owner_only():
    r = UserRole.admin
    assert has_capability(r, Capability.user_manage)
    assert has_capability(r, Capability.content_edit)
    assert has_capability(r, Capability.audit_view)
    assert not has_capability(r, Capability.permanent_delete_approve)
