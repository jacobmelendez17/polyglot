"""Integration test for GET /me/reviews/activity (slice 46)."""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.progress import ReviewAnswer, ReviewSession


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def world(client, db):
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=lang.id, position=1, title="L1", status=ContentStatus.published)
    db.add(module); db.flush()
    v = VocabularyItem(language_id=lang.id, module_id=module.id, status=ContentStatus.published,
                       term="casa", normalized_term="casa", primary_translation="house",
                       part_of_speech="noun", difficulty_rank=1)
    db.add(v); db.flush()
    r = client.post("/api/v1/auth/signup",
                    json={"email": "grapher@example.com", "name": "G", "password": "supersecret1"})
    from app.models.identity import User
    uid = db.execute(select(User).where(User.email == "grapher@example.com")).scalar_one().id
    session = ReviewSession(user_id=uid, kind="review", state="completed")
    db.add(session); db.flush()
    db.commit()
    return {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"},
            "uid": uid, "vid": v.id, "session": session.id}


def _answer(db, uid, sid, vid, when):
    db.add(ReviewAnswer(
        session_id=sid, user_id=uid, item_type=ItemType.vocabulary, item_id=vid,
        prompt_direction="es_to_en", prompt_kind="translation",
        submitted_answer="house", normalized_answer="house",
        original_correct=True, final_correct=True, undo_used=False,
        srs_stage_before=3, srs_stage_after=4, idempotency_key=uuid.uuid4(),
        answered_at=when, created_at=when,
    ))


def test_activity_shape_and_counts(client, db, world):
    now = dt.datetime.now(tz=dt.timezone.utc)
    _answer(db, world["uid"], world["session"], world["vid"], now)                       # today + this hour
    _answer(db, world["uid"], world["session"], world["vid"], now - dt.timedelta(hours=2))  # today, earlier hour
    _answer(db, world["uid"], world["session"], world["vid"], now - dt.timedelta(days=2))   # earlier this week
    db.commit()

    r = client.get("/api/v1/me/reviews/activity", headers=world["hdr"])
    assert r.status_code == 200
    body = r.json()
    assert len(body["seven_day"]) == 7
    assert len(body["twenty_four_hour"]) == 24
    # 3 answers landed in the 7-day window
    assert sum(b["count"] for b in body["seven_day"]) == 3
    # 2 of them within the last 24h
    assert sum(b["count"] for b in body["twenty_four_hour"]) == 2


def test_activity_empty_for_new_user(client, db, world):
    body = client.get("/api/v1/me/reviews/activity", headers=world["hdr"]).json()
    assert sum(b["count"] for b in body["seven_day"]) == 0
    assert len(body["seven_day"]) == 7


def test_activity_requires_auth(client, db, world):
    assert client.get("/api/v1/me/reviews/activity").status_code in (401, 403)
