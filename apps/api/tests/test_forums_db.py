"""Forum endpoints — full DB + API flow.

The properties that matter: reads are public, writes are gated on the posting
switch, the rate limiter and sanitizer actually run, reporting auto-hides at the
threshold, and only a moderator can hide/delete or see hidden content.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.seed import seed
from app.db.seed_forums import seed_forums
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.forum import ForumReply, ForumThread
from app.models.identity import User


@pytest.fixture()
def app_settings():
    """Posting is ON for most tests; the read-only test overrides it."""
    s = get_settings()
    original = getattr(s, "forums_posting_enabled", False)
    s.forums_posting_enabled = True
    yield s
    s.forums_posting_enabled = original


@pytest.fixture()
def client(db, app_settings):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def world(client, db):
    seed(db)
    seed_forums(db)
    db.commit()


def _signup(client, email="poster@example.com") -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "Poster", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _promote(db, email: str, role: UserRole) -> None:
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.role = role
    db.commit()


# --- public reads ---------------------------------------------------------

def test_categories_are_public(client, world):
    r = client.get("/api/v1/forums/categories")     # no auth
    assert r.status_code == 200
    slugs = {c["slug"] for c in r.json()}
    assert {"grammar-help", "vocabulary", "bug-reports"} <= slugs


def test_threads_list_is_public_and_empty_at_first(client, world):
    r = client.get("/api/v1/forums/categories/grammar-help/threads")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_unknown_category_is_404(client, world):
    assert client.get("/api/v1/forums/categories/nope/threads").status_code == 404


# --- posting gate ---------------------------------------------------------

def test_posting_requires_auth(client, world):
    r = client.post("/api/v1/forums/categories/grammar-help/threads",
                    json={"title": "Hi", "body": "Question"})
    assert r.status_code == 401


def test_posting_when_disabled_is_refused(client, db, world):
    """The read-only switch is enforced server-side (§18)."""
    get_settings().forums_posting_enabled = False
    headers = _signup(client)
    r = client.post("/api/v1/forums/categories/grammar-help/threads",
                    headers=headers, json={"title": "Hi", "body": "Question"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "posting_disabled"
    get_settings().forums_posting_enabled = True


def test_create_a_thread_and_read_it_back(client, world):
    headers = _signup(client)
    created = client.post("/api/v1/forums/categories/grammar-help/threads",
                          headers=headers,
                          json={"title": "Ser vs estar?", "body": "When do I use each?"})
    assert created.status_code == 201
    tid = created.json()["id"]

    detail = client.get(f"/api/v1/forums/threads/{tid}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Ser vs estar?"

    listing = client.get("/api/v1/forums/categories/grammar-help/threads")
    assert listing.json()["total"] == 1


def test_thread_body_is_sanitized(client, db, world):
    headers = _signup(client)
    created = client.post("/api/v1/forums/categories/grammar-help/threads",
                          headers=headers,
                          json={"title": "Test", "body": "<script>alert(1)</script>hi"})
    tid = created.json()["id"]
    body = client.get(f"/api/v1/forums/threads/{tid}").json()["body"]
    assert "<script>" not in body
    assert "hi" in body


def test_reply_to_a_thread(client, world):
    headers = _signup(client)
    tid = client.post("/api/v1/forums/categories/vocabulary/threads", headers=headers,
                      json={"title": "T", "body": "B"}).json()["id"]
    replier = _signup(client, "replier@example.com")
    r = client.post(f"/api/v1/forums/threads/{tid}/replies", headers=replier,
                    json={"body": "Here's my answer"})
    assert r.status_code == 201
    detail = client.get(f"/api/v1/forums/threads/{tid}").json()
    assert detail["reply_total"] == 1


def test_empty_body_is_rejected(client, world):
    headers = _signup(client)
    r = client.post("/api/v1/forums/categories/vocabulary/threads", headers=headers,
                    json={"title": "T", "body": "   "})
    assert r.status_code == 422    # schema min_length catches whitespace-only


# --- rate limiting --------------------------------------------------------

def test_rate_limit_kicks_in(client, world):
    headers = _signup(client)
    # POST_MAX_IN_WINDOW is 6; the 7th in quick succession should 429.
    codes = []
    for i in range(8):
        r = client.post("/api/v1/forums/categories/vocabulary/threads", headers=headers,
                        json={"title": f"T{i}", "body": "content"})
        codes.append(r.status_code)
    assert 429 in codes
    assert codes.count(201) <= 6


# --- reporting & moderation ----------------------------------------------

def _make_thread(client, headers, category="vocabulary") -> str:
    return client.post(f"/api/v1/forums/categories/{category}/threads", headers=headers,
                       json={"title": "Reportable", "body": "content"}).json()["id"]


def test_reporting_auto_hides_at_threshold(client, db, world):
    author = _signup(client, "author@example.com")
    tid = _make_thread(client, author)

    # Three different users report it → auto-hidden.
    for i in range(3):
        reporter = _signup(client, f"reporter{i}@example.com")
        r = client.post("/api/v1/forums/report", headers=reporter,
                        json={"target_type": "thread", "target_id": tid, "reason": "spam"})
        assert r.status_code == 200

    # A normal reader no longer sees it.
    assert client.get(f"/api/v1/forums/threads/{tid}").status_code == 404


def test_reporting_twice_is_idempotent(client, world):
    author = _signup(client, "author2@example.com")
    tid = _make_thread(client, author)
    reporter = _signup(client, "dupe@example.com")
    first = client.post("/api/v1/forums/report", headers=reporter,
                        json={"target_type": "thread", "target_id": tid, "reason": "spam"})
    second = client.post("/api/v1/forums/report", headers=reporter,
                         json={"target_type": "thread", "target_id": tid, "reason": "spam"})
    assert second.json()["already"] is True


def test_only_moderators_can_moderate(client, world):
    author = _signup(client, "author3@example.com")
    tid = _make_thread(client, author)
    r = client.post("/api/v1/forums/moderation/act", headers=author,
                    json={"target_type": "thread", "target_id": tid, "action": "hide"})
    assert r.status_code == 403


def test_a_moderator_can_hide_and_restore(client, db, world):
    author = _signup(client, "author4@example.com")
    tid = _make_thread(client, author)

    mod = _signup(client, "mod@example.com")
    _promote(db, "mod@example.com", UserRole.moderator)
    mod = _signup(client, "mod@example.com")     # fresh token after the role change

    hide = client.post("/api/v1/forums/moderation/act", headers=mod,
                       json={"target_type": "thread", "target_id": tid, "action": "hide"})
    assert hide.status_code == 200
    assert hide.json()["hidden"] is True

    # Public can't see it; the moderator still can.
    assert client.get(f"/api/v1/forums/threads/{tid}").status_code == 404
    assert client.get(f"/api/v1/forums/threads/{tid}", headers=mod).status_code == 200

    restore = client.post("/api/v1/forums/moderation/act", headers=mod,
                          json={"target_type": "thread", "target_id": tid, "action": "unhide"})
    assert restore.json()["hidden"] is False
    assert client.get(f"/api/v1/forums/threads/{tid}").status_code == 200


def test_moderator_sees_the_report_queue(client, db, world):
    author = _signup(client, "author5@example.com")
    tid = _make_thread(client, author)
    reporter = _signup(client, "flag@example.com")
    client.post("/api/v1/forums/report", headers=reporter,
                json={"target_type": "thread", "target_id": tid, "reason": "abuse"})

    mod = _signup(client, "mod2@example.com")
    _promote(db, "mod2@example.com", UserRole.moderator)
    mod = _signup(client, "mod2@example.com")

    queue = client.get("/api/v1/forums/moderation/reports", headers=mod)
    assert queue.status_code == 200
    assert any(item["target_id"] == tid for item in queue.json())


def test_a_normal_user_cannot_see_the_report_queue(client, world):
    headers = _signup(client, "nosy@example.com")
    assert client.get("/api/v1/forums/moderation/reports", headers=headers).status_code == 403
