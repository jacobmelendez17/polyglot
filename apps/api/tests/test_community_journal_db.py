"""Community journals end-to-end: sharing, privacy, feedback, moderation."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import User
from app.models.progress import JournalEntry


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": email.split("@")[0], "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def _make_entry(db, user_id, body="hoy fui al mercado y compré frutas", title="mi día"):
    e = JournalEntry(user_id=user_id, title=title, body=body, visibility="private")
    db.add(e)
    db.commit()
    return e


def test_all_routes_require_auth(client):
    assert client.get("/api/v1/community/journals").status_code == 401
    assert client.get("/api/v1/me/community-journals/mine").status_code == 401


def test_private_entry_is_not_in_the_feed_or_readable(client, db):
    ha, a = _signup(client, "author@example.com")
    hb, _ = _signup(client, "reader@example.com")
    e = _make_entry(db, a)
    # not in feed
    feed = client.get("/api/v1/community/journals", headers=hb).json()
    assert all(item["id"] != str(e.id) for item in feed)
    # another user gets 404 (existence not revealed)
    r = client.get(f"/api/v1/community/journals/{e.id}", headers=hb)
    assert r.status_code == 404


def test_share_then_feed_and_read(client, db):
    ha, a = _signup(client, "sharer@example.com")
    hb, _ = _signup(client, "peer@example.com")
    e = _make_entry(db, a)

    s = client.post(f"/api/v1/me/community-journals/{e.id}/share", headers=ha).json()
    assert s["shared"] is True

    feed = client.get("/api/v1/community/journals", headers=hb).json()
    assert any(item["id"] == str(e.id) for item in feed)

    entry = client.get(f"/api/v1/community/journals/{e.id}", headers=hb).json()
    assert entry["body"] == "hoy fui al mercado y compré frutas"
    assert entry["is_owner"] is False


def test_unshare_removes_from_feed(client, db):
    ha, a = _signup(client, "s2@example.com")
    hb, _ = _signup(client, "p2@example.com")
    e = _make_entry(db, a)
    client.post(f"/api/v1/me/community-journals/{e.id}/share", headers=ha)
    client.post(f"/api/v1/me/community-journals/{e.id}/unshare", headers=ha)
    feed = client.get("/api/v1/community/journals", headers=hb).json()
    assert all(item["id"] != str(e.id) for item in feed)
    assert client.get(f"/api/v1/community/journals/{e.id}", headers=hb).status_code == 404


def test_cannot_share_someone_elses_entry(client, db):
    ha, a = _signup(client, "owner2@example.com")
    hb, _ = _signup(client, "intruder@example.com")
    e = _make_entry(db, a)
    r = client.post(f"/api/v1/me/community-journals/{e.id}/share", headers=hb)
    assert r.status_code == 404  # not yours → not found


def test_feedback_only_on_shared_entries(client, db):
    ha, a = _signup(client, "s3@example.com")
    hb, _ = _signup(client, "commenter@example.com")
    e = _make_entry(db, a)
    # private → no feedback
    r = client.post(f"/api/v1/community/journals/{e.id}/feedback",
                    headers=hb, json={"body": "great job"})
    assert r.status_code == 404
    # share → feedback works and is sanitized
    client.post(f"/api/v1/me/community-journals/{e.id}/share", headers=ha)
    r = client.post(f"/api/v1/community/journals/{e.id}/feedback",
                    headers=hb, json={"body": "<b>muy</b> bien!"})
    assert r.status_code == 200
    assert r.json()["body"] == "muy bien!"  # markup stripped
    # appears on the entry
    entry = client.get(f"/api/v1/community/journals/{e.id}", headers=ha).json()
    assert len(entry["feedback"]) == 1


def test_moderator_can_hide_feedback(client, db):
    ha, a = _signup(client, "s4@example.com")
    hb, b = _signup(client, "commenter2@example.com")
    hm, m = _signup(client, "mod@example.com")
    db.execute(select(User).where(User.id == m))  # ensure loaded
    mod = db.get(User, m)
    mod.role = UserRole.moderator
    db.commit()

    e = _make_entry(db, a)
    client.post(f"/api/v1/me/community-journals/{e.id}/share", headers=ha)
    fb = client.post(f"/api/v1/community/journals/{e.id}/feedback",
                     headers=hb, json={"body": "spammy comment"}).json()

    # a non-mod cannot hide
    assert client.post(f"/api/v1/community/feedback/{fb['id']}/hide",
                       headers=hb, json={"hidden": True}).status_code == 403
    # a mod can
    assert client.post(f"/api/v1/community/feedback/{fb['id']}/hide",
                       headers=hm, json={"hidden": True, "reason": "spam"}).status_code == 200

    # hidden feedback is gone for a regular reader, still visible to the mod
    peer_view = client.get(f"/api/v1/community/journals/{e.id}", headers=hb).json()
    assert peer_view["feedback"] == []
    mod_view = client.get(f"/api/v1/community/journals/{e.id}", headers=hm).json()
    assert len(mod_view["feedback"]) == 1


def test_moderator_can_hide_a_shared_entry(client, db):
    ha, a = _signup(client, "s5@example.com")
    hb, _ = _signup(client, "peer3@example.com")
    hm, m = _signup(client, "mod2@example.com")
    mod = db.get(User, m); mod.role = UserRole.moderator; db.commit()

    e = _make_entry(db, a)
    client.post(f"/api/v1/me/community-journals/{e.id}/share", headers=ha)
    client.post(f"/api/v1/community/journals/{e.id}/hide",
                headers=hm, json={"hidden": True, "reason": "off-topic"})

    # removed from the feed and unreadable by peers
    feed = client.get("/api/v1/community/journals", headers=hb).json()
    assert all(item["id"] != str(e.id) for item in feed)
    assert client.get(f"/api/v1/community/journals/{e.id}", headers=hb).status_code == 404
    # owner still sees their own entry
    assert client.get(f"/api/v1/community/journals/{e.id}", headers=ha).status_code == 200
