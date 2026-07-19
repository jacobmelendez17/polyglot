"""Practice flow against a real DB: build session, grade, advance stage, XP."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.progress import UserItemProgress, XpEvent


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def practiced_user(client, db):
    """A user who has learned some vocab (so practice has a pool to draw from)."""
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=lang.id, position=1, title="Level 1",
                    status=ContentStatus.published)
    db.add(module)
    db.flush()
    ids = []
    for i in range(6):
        v = VocabularyItem(
            language_id=lang.id, module_id=module.id, term=f"palabra{i}",
            normalized_term=f"palabra{i}", primary_translation=f"word{i}",
            part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1,
        )
        db.add(v)
        db.flush()
        ids.append(v.id)
    db.commit()

    tok = client.post("/api/v1/auth/signup",
                      json={"email": "p@example.com", "name": "Pia", "password": "supersecret1"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    # learn all six via lesson completion
    lessons = client.get("/api/v1/levels/1/lessons", headers=headers).json()
    for l in lessons:
        client.post(f"/api/v1/levels/1/lessons/{l['position']}/complete",
                    headers=headers, json={"idempotency_key": str(uuid.uuid4())})
    return {"headers": headers, "vocab_ids": ids}


def test_practice_requires_auth(client):
    assert client.post("/api/v1/practice/sessions?mode=weak_items").status_code == 401


def test_build_weak_practice_session(client, db, practiced_user):
    r = client.post("/api/v1/practice/sessions?mode=weak_items",
                    headers=practiced_user["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "weak_items"
    assert len(body["prompts"]) > 0
    # prompts never leak the raw answer field name
    assert "answer" not in body["prompts"][0]


def test_correct_practice_awards_xp_and_advances_stage(client, db, practiced_user):
    session = client.post("/api/v1/practice/sessions?mode=weak_items",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    xp_before = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()

    r = client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                    headers=practiced_user["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "mode": "weak_items", "answer": p["translation"], "idempotency_key": str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    grade = r.json()
    assert grade["correct"] is True
    assert grade["xp_awarded"] > 0
    assert grade["practice_stage"] == 1   # advanced from 0 -> 1

    xp_after = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()
    assert xp_after > xp_before


def test_wrong_practice_holds_stage_and_no_xp(client, db, practiced_user):
    session = client.post("/api/v1/practice/sessions?mode=weak_items",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    r = client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                    headers=practiced_user["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "mode": "weak_items", "answer": "totally wrong", "idempotency_key": str(uuid.uuid4())})
    grade = r.json()
    assert grade["correct"] is False
    assert grade["xp_awarded"] == 0
    assert grade["practice_stage"] == 0   # held


def test_practice_does_not_change_srs_stage(client, db, practiced_user):
    # capture SRS stage before practicing
    before = {
        str(p.item_id): p.srs_stage
        for p in db.execute(select(UserItemProgress)).scalars().all()
    }
    session = client.post("/api/v1/practice/sessions?mode=weak_items",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                headers=practiced_user["headers"],
                json={"item_type": p["item_type"], "item_id": p["item_id"],
                      "mode": "weak_items", "answer": p["translation"], "idempotency_key": str(uuid.uuid4())})
    after = {
        str(p.item_id): p.srs_stage
        for p in db.execute(select(UserItemProgress)).scalars().all()
    }
    assert before == after   # practice never touches SRS


def test_practice_answer_is_idempotent(client, db, practiced_user):
    session = client.post("/api/v1/practice/sessions?mode=weak_items",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    key = str(uuid.uuid4())
    body = {"item_type": p["item_type"], "item_id": p["item_id"], "mode": "weak_items",
            "answer": p["translation"], "idempotency_key": key}
    client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                headers=practiced_user["headers"], json=body)
    client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                headers=practiced_user["headers"], json=body)
    # only one XP event for that key
    n = db.execute(select(func.count()).select_from(XpEvent)
                   .where(XpEvent.idempotency_key == uuid.UUID(key))).scalar_one()
    assert n == 1


def test_complete_practice_session(client, db, practiced_user):
    session = client.post("/api/v1/practice/sessions?mode=fill_blank",
                          headers=practiced_user["headers"]).json()
    r = client.post(f"/api/v1/practice/sessions/{session['session_id']}/complete",
                    headers=practiced_user["headers"])
    assert r.status_code == 200
    assert r.json()["state"] == "completed"
