"""/me/items and /me/items/{type}/{id}/progress: the item detail page's API."""
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


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def learner(client, db):
    """A user who has learned one word (unlocked into the SRS)."""
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=lang.id, position=1, title="Level 1",
                    status=ContentStatus.published)
    db.add(module)
    db.flush()
    v = VocabularyItem(
        language_id=lang.id, module_id=module.id, term="perro",
        normalized_term="perro", primary_translation="dog",
        part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1,
    )
    db.add(v)
    db.commit()

    tok = client.post("/api/v1/auth/signup",
                      json={"email": "i@example.com", "name": "Ivy", "password": "supersecret1"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    lessons = client.get("/api/v1/levels/1/lessons", headers=headers).json()
    for l in lessons:
        quiz = client.post(f"/api/v1/levels/1/lessons/{l['position']}/quiz", headers=headers)
        if quiz.status_code == 200:
            qbody = quiz.json()
            for p in qbody["prompts"]:
                item = db.get(VocabularyItem, uuid.UUID(p["item_id"]))
                client.post(f"/api/v1/quiz/{qbody['session_id']}/answers", headers=headers,
                            json={"item_type": p["item_type"], "item_id": p["item_id"],
                                  "answer": item.primary_translation if item else "",
                                  "idempotency_key": str(uuid.uuid4())})
        client.post(f"/api/v1/levels/1/lessons/{l['position']}/complete",
                    headers=headers, json={"idempotency_key": str(uuid.uuid4())})
    return {"headers": headers, "vocab_id": str(v.id)}


def test_items_requires_auth(client):
    assert client.get("/api/v1/me/items").status_code == 401


def test_list_items_includes_learned_word(client, learner):
    r = client.get("/api/v1/me/items", headers=learner["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(i["item_id"] == learner["vocab_id"] for i in body)
    row = next(i for i in body if i["item_id"] == learner["vocab_id"])
    assert row["term"] == "perro"
    assert row["srs_stage_name"] == "Beginner 1"
    assert row["practice_stage"] == 0
    assert row["perfect"] is False


def test_item_progress_requires_auth(client, learner):
    r = client.get(f"/api/v1/me/items/vocabulary/{learner['vocab_id']}/progress")
    assert r.status_code == 401


def test_item_progress_not_found_for_unstarted_item(client, learner, db):
    other = VocabularyItem(
        language_id=db.execute(select(VocabularyItem.language_id).limit(1)).scalar_one(),
        module_id=db.execute(select(VocabularyItem.module_id).limit(1)).scalar_one(),
        term="gato", normalized_term="gato", primary_translation="cat",
        part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1,
    )
    db.add(other)
    db.commit()
    r = client.get(f"/api/v1/me/items/vocabulary/{other.id}/progress", headers=learner["headers"])
    assert r.status_code == 404


def test_item_progress_shape(client, learner):
    r = client.get(f"/api/v1/me/items/vocabulary/{learner['vocab_id']}/progress",
                   headers=learner["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["term"] == "perro"
    assert body["translation"] == "dog"
    assert body["level"] == 1
    assert body["srs_stage"] == 1
    assert body["srs_stage_name"] == "Beginner 1"
    # the fixture's lesson quiz already produced one (correct) ReviewAnswer —
    # quiz attempts are part of a word's history too.
    assert body["accuracy"] == 100.0
    assert len(body["history"]) == 1
    assert body["perfect_at"] is None
    # all three practice categories present, none started
    cats = {c["category"]: c for c in body["practice_stages"]}
    assert set(cats) == {"sentences", "listening", "speaking"}
    assert cats["speaking"]["live"] is False
    assert cats["sentences"]["live"] is True
    assert all(c["stage"] == 0 for c in cats.values())


def test_item_progress_reflects_review_history(client, learner, db):
    from app.models.progress import UserItemProgress

    # Make the item due, then answer both prompt directions.
    prog = db.execute(
        select(UserItemProgress).where(UserItemProgress.item_id == uuid.UUID(learner["vocab_id"]))
    ).scalar_one()
    prog.next_review_at = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(minutes=1)
    db.commit()

    session = client.post("/api/v1/reviews/sessions", headers=learner["headers"]).json()
    for p in session["prompts"]:
        answer = "dog" if p["direction"] == "es_to_en" else "perro"
        client.post(f"/api/v1/reviews/sessions/{session['session_id']}/answers",
                   headers=learner["headers"],
                   json={"item_type": p["item_type"], "item_id": p["item_id"],
                         "direction": p["direction"], "answer": answer,
                         "idempotency_key": str(uuid.uuid4())})

    r = client.get(f"/api/v1/me/items/vocabulary/{learner['vocab_id']}/progress",
                   headers=learner["headers"])
    body = r.json()
    assert body["accuracy"] == 100.0
    # 1 lesson-quiz answer (from the fixture) + 2 review-pair answers.
    assert len(body["history"]) == 3
    assert all(h["correct"] for h in body["history"])
    assert body["srs_stage"] == 2   # promoted: clean pair, zero wrong
