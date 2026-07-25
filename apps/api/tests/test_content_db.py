"""Intermissions, changelog, and immersion endpoints."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import User, UserSettings
from app.models.platform import ChangelogEntry, Intermission


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="learner@example.com") -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "Learner", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _promote(db, email: str, role: UserRole) -> None:
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.role = role
    db.commit()


@pytest.fixture()
def learner(client, db):
    seed(db)
    db.commit()
    return _signup(client)


def _intermission(db, title="Vowels", level=1, publish=True, **trigger) -> Intermission:
    row = Intermission(
        title=title, body_rich="Some short reading.",
        trigger={"kind": "level_start", "level": level, **trigger},
        status=ContentStatus.published if publish else ContentStatus.draft,
    )
    db.add(row)
    db.commit()
    return row


# --- intermissions --------------------------------------------------------

def test_pending_requires_auth(client):
    assert client.get("/api/v1/me/intermissions/pending?event=level_start").status_code == 401


def test_pending_returns_a_matching_intermission(client, db, learner):
    _intermission(db, title="Vowels", level=1)
    r = client.get("/api/v1/me/intermissions/pending?event=level_start&level=1",
                   headers=learner)
    assert r.status_code == 200
    assert [i["title"] for i in r.json()] == ["Vowels"]


def test_pending_skips_a_non_matching_level(client, db, learner):
    _intermission(db, title="Vowels", level=2)
    r = client.get("/api/v1/me/intermissions/pending?event=level_start&level=1",
                   headers=learner)
    assert r.json() == []


def test_drafts_are_never_shown_to_learners(client, db, learner):
    _intermission(db, title="Unfinished", level=1, publish=False)
    r = client.get("/api/v1/me/intermissions/pending?event=level_start&level=1",
                   headers=learner)
    assert r.json() == []


def test_an_unknown_event_fails_validation(client, learner):
    r = client.get("/api/v1/me/intermissions/pending?event=whenever", headers=learner)
    assert r.status_code == 422


def test_marking_viewed_stops_it_reappearing(client, db, learner):
    row = _intermission(db, title="Vowels", level=1)
    url = "/api/v1/me/intermissions/pending?event=level_start&level=1"
    assert len(client.get(url, headers=learner).json()) == 1

    marked = client.post(f"/api/v1/me/intermissions/{row.id}/viewed", headers=learner)
    assert marked.status_code == 200
    assert marked.json()["viewed_at"] is not None
    assert client.get(url, headers=learner).json() == []


def test_marking_viewed_twice_is_harmless(client, db, learner):
    row = _intermission(db, title="Vowels", level=1)
    first = client.post(f"/api/v1/me/intermissions/{row.id}/viewed", headers=learner)
    second = client.post(f"/api/v1/me/intermissions/{row.id}/viewed", headers=learner)
    assert second.status_code == 200
    assert second.json()["viewed_at"] == first.json()["viewed_at"]


def test_marking_an_unknown_intermission_is_404(client, learner):
    import uuid
    r = client.post(f"/api/v1/me/intermissions/{uuid.uuid4()}/viewed", headers=learner)
    assert r.status_code == 404


def test_turning_intermissions_off_is_honoured_server_side(client, db, learner):
    """The setting can't be enforced in the client alone (§17)."""
    _intermission(db, title="Vowels", level=1)
    user = db.execute(
        select(User).where(User.email == "learner@example.com")
    ).scalar_one()
    settings = db.get(UserSettings, user.id) or UserSettings(user_id=user.id)
    settings.intermissions_enabled = False
    db.add(settings)
    db.commit()

    r = client.get("/api/v1/me/intermissions/pending?event=level_start&level=1",
                   headers=learner)
    assert r.json() == []


def test_history_lists_what_was_read(client, db, learner):
    row = _intermission(db, title="Vowels", level=1)
    client.post(f"/api/v1/me/intermissions/{row.id}/viewed", headers=learner)
    body = client.get("/api/v1/me/intermissions/history", headers=learner).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Vowels"
    assert body["items"][0]["viewed_at"] is not None


def test_history_is_empty_before_anything_is_read(client, db, learner):
    _intermission(db, title="Vowels", level=1)
    assert client.get("/api/v1/me/intermissions/history",
                      headers=learner).json()["total"] == 0


def test_history_is_per_user(client, db, learner):
    row = _intermission(db, title="Vowels", level=1)
    client.post(f"/api/v1/me/intermissions/{row.id}/viewed", headers=learner)
    other = _signup(client, "other@example.com")
    assert client.get("/api/v1/me/intermissions/history",
                      headers=other).json()["total"] == 0


# --- changelog ------------------------------------------------------------

def _entry(db, title="Shipped a thing", publish=True, when=None) -> ChangelogEntry:
    row = ChangelogEntry(
        type="feature", title=title, body="Details.",
        status=ContentStatus.published if publish else ContentStatus.draft,
        published_at=(when or dt.datetime.now(tz=dt.timezone.utc)) if publish else None,
    )
    db.add(row)
    db.commit()
    return row


def test_changelog_is_public(client, db, learner):
    _entry(db, title="Shipped a thing")
    r = client.get("/api/v1/changelog")     # no auth header
    assert r.status_code == 200
    assert [i["title"] for i in r.json()["items"]] == ["Shipped a thing"]


def test_unpublished_entries_are_not_public(client, db, learner):
    _entry(db, title="Secret plans", publish=False)
    assert client.get("/api/v1/changelog").json()["items"] == []


def test_changelog_is_newest_first(client, db, learner):
    now = dt.datetime.now(tz=dt.timezone.utc)
    _entry(db, title="Older", when=now - dt.timedelta(days=2))
    _entry(db, title="Newer", when=now)
    titles = [i["title"] for i in client.get("/api/v1/changelog").json()["items"]]
    assert titles == ["Newer", "Older"]


def test_changelog_paginates(client, db, learner):
    for i in range(5):
        _entry(db, title=f"Entry {i}",
               when=dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=i))
    page = client.get("/api/v1/changelog?limit=2&offset=2").json()
    assert page["total"] == 5 and len(page["items"]) == 2


def test_unread_count_starts_at_everything_published(client, db, learner):
    _entry(db, title="One")
    _entry(db, title="Two")
    assert client.get("/api/v1/me/changelog/unread", headers=learner).json()["unread"] == 2


def test_marking_read_zeroes_the_count(client, db, learner):
    _entry(db, title="One")
    client.post("/api/v1/me/changelog/mark-read", headers=learner)
    assert client.get("/api/v1/me/changelog/unread", headers=learner).json()["unread"] == 0


def test_an_entry_published_after_reading_counts_as_unread(client, db, learner):
    _entry(db, title="Old news")
    client.post("/api/v1/me/changelog/mark-read", headers=learner)
    _entry(db, title="Fresh news",
           when=dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(seconds=5))
    assert client.get("/api/v1/me/changelog/unread", headers=learner).json()["unread"] == 1


# --- admin ----------------------------------------------------------------

def test_a_normal_user_cannot_create_changelog_entries(client, learner):
    r = client.post("/api/v1/admin/changelog", headers=learner,
                    json={"type": "feature", "title": "I am admin now"})
    assert r.status_code == 403


def test_a_normal_user_cannot_list_drafts(client, learner):
    assert client.get("/api/v1/admin/changelog", headers=learner).status_code == 403


def test_admin_routes_require_auth(client):
    assert client.get("/api/v1/admin/changelog").status_code == 401


def test_an_editor_can_create_and_publish(client, db, learner):
    headers = _signup(client, "editor@example.com")
    _promote(db, "editor@example.com", UserRole.content_editor)

    created = client.post("/api/v1/admin/changelog", headers=headers, json={
        "type": "feature", "title": "Dashboard customization", "body": "Drag cards.",
    })
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert client.get("/api/v1/changelog").json()["items"] == []

    entry_id = created.json()["id"]
    published = client.patch(f"/api/v1/admin/changelog/{entry_id}/status",
                             headers=headers, json={"status": "published"})
    assert published.status_code == 200
    assert published.json()["published_at"] is not None
    assert len(client.get("/api/v1/changelog").json()["items"]) == 1


def test_republishing_keeps_the_original_publish_date(client, db, learner):
    """Editing an entry should not shove it back to the top of everyone's unread."""
    headers = _signup(client, "editor@example.com")
    _promote(db, "editor@example.com", UserRole.content_editor)
    created = client.post("/api/v1/admin/changelog", headers=headers, json={
        "type": "fix", "title": "Fixed a thing", "publish": True,
    }).json()
    first = created["published_at"]

    client.patch(f"/api/v1/admin/changelog/{created['id']}/status",
                 headers=headers, json={"status": "draft"})
    again = client.patch(f"/api/v1/admin/changelog/{created['id']}/status",
                         headers=headers, json={"status": "published"}).json()
    assert again["published_at"] == first


def test_invalid_changelog_types_are_rejected(client, db, learner):
    headers = _signup(client, "editor@example.com")
    _promote(db, "editor@example.com", UserRole.content_editor)
    r = client.post("/api/v1/admin/changelog", headers=headers,
                    json={"type": "gossip", "title": "Nope"})
    assert r.status_code == 422


def test_deleting_an_entry_is_a_soft_delete(client, db, learner):
    headers = _signup(client, "editor@example.com")
    _promote(db, "editor@example.com", UserRole.content_editor)
    created = client.post("/api/v1/admin/changelog", headers=headers, json={
        "type": "fix", "title": "Oops", "publish": True,
    }).json()

    assert client.delete(f"/api/v1/admin/changelog/{created['id']}",
                         headers=headers).status_code == 204
    assert client.get("/api/v1/changelog").json()["items"] == []
    row = db.get(ChangelogEntry, __import__("uuid").UUID(created["id"]))
    assert row is not None and row.deleted_at is not None   # still on record


def test_intermissions_need_a_known_trigger_kind(client, db, learner):
    headers = _signup(client, "editor@example.com")
    _promote(db, "editor@example.com", UserRole.content_editor)
    r = client.post("/api/v1/admin/intermissions", headers=headers, json={
        "title": "Bad trigger", "body": "x", "trigger": {"kind": "whenever"},
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "invalid_trigger"


# --- immersion ------------------------------------------------------------

def test_immersion_starts_locked(client, learner):
    r = client.get("/api/v1/me/immersion", headers=learner).json()
    assert r["unlocked"] is False
    assert r["enabled"] is False
    assert r["unlock_level"] == 10
    assert r["levels_remaining"] == 10


def test_enabling_immersion_while_locked_is_refused(client, learner):
    """Server-side — hiding the toggle in the UI would not be enough."""
    r = client.put("/api/v1/me/immersion", headers=learner, json={"enabled": True})
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "locked"


def test_disabling_immersion_is_always_allowed(client, learner):
    r = client.put("/api/v1/me/immersion", headers=learner, json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_immersion_requires_auth(client):
    assert client.get("/api/v1/me/immersion").status_code == 401
