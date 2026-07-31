"""Community-journal rules — the visibility invariant and content guards."""
import datetime as dt
import uuid

import pytest

from app.domain.community_journal import (
    RATE_LIMIT,
    can_view_shared_entry,
    excerpt,
    is_in_feed,
    sanitize,
    validate_feedback,
    within_rate_limit,
)

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()


def _view(**kw):
    base = dict(owner_id=OWNER, viewer_id=OTHER, shared=False,
                share_hidden=False, viewer_is_mod=False)
    base.update(kw)
    return can_view_shared_entry(**base)


def test_owner_always_sees_own_entry():
    assert _view(viewer_id=OWNER, shared=False) is True
    assert _view(viewer_id=OWNER, shared=True, share_hidden=True) is True


def test_private_entry_never_leaks_to_others():
    assert _view(shared=False) is False


def test_private_entry_is_invisible_even_to_moderators():
    # privacy is privacy — moderation applies to shared content only
    assert _view(shared=False, viewer_is_mod=True) is False


def test_shared_visible_entry_is_public_to_the_community():
    assert _view(shared=True) is True


def test_mod_hidden_shared_entry_only_visible_to_mods():
    assert _view(shared=True, share_hidden=True, viewer_is_mod=False) is False
    assert _view(shared=True, share_hidden=True, viewer_is_mod=True) is True


def test_anonymous_viewer_cannot_see_private():
    assert can_view_shared_entry(owner_id=OWNER, viewer_id=None, shared=False,
                                 share_hidden=False, viewer_is_mod=False) is False


def test_feed_membership():
    assert is_in_feed(shared=True, share_hidden=False) is True
    assert is_in_feed(shared=True, share_hidden=True) is False
    assert is_in_feed(shared=False, share_hidden=False) is False


def test_sanitize_strips_markup_keeps_newlines():
    assert sanitize("<b>hola</b>   mundo") == "hola mundo"
    assert sanitize("a<script>x</script>\nb") == "ax\nb"


def test_validate_feedback():
    assert validate_feedback("  buen trabajo  ") == "buen trabajo"
    with pytest.raises(ValueError):
        validate_feedback("   ")
    with pytest.raises(ValueError):
        validate_feedback("x" * 3001)


def test_rate_limit():
    now = dt.datetime(2026, 7, 30, 12, 0, tzinfo=dt.timezone.utc)
    seven = [now - dt.timedelta(minutes=i) for i in range(7)]
    assert within_rate_limit(seven, now) is True
    at_limit = [now - dt.timedelta(minutes=i) for i in range(RATE_LIMIT)]
    assert within_rate_limit(at_limit, now) is False
    old = [now - dt.timedelta(minutes=30) for _ in range(20)]
    assert within_rate_limit(old, now) is True


def test_excerpt():
    assert excerpt("short") == "short"
    long = excerpt("a" * 300, n=10)
    assert long.endswith("…") and len(long) == 11
