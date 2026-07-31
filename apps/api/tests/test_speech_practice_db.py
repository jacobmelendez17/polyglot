"""Speaking practice end-to-end: server-side scoring, stage advance, idempotent XP."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.enums import ItemType, PracticeCategory
from app.models.progress import UserItemPracticeStage, UserItemProgress, XpEvent


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def learner(client, db):
    """A user who has 'learned' two vocab items (has progress rows)."""
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m = Module(language_id=lang.id, position=1, title="Level 1",
               status=ContentStatus.published)
    db.add(m)
    db.flush()
    gato = VocabularyItem(
        language_id=lang.id, module_id=m.id, term="gato", normalized_term="gato",
        primary_translation="cat", part_of_speech="noun",
        status=ContentStatus.published, difficulty_rank=1,
    )
    perro = VocabularyItem(
        language_id=lang.id, module_id=m.id, term="perro", normalized_term="perro",
        primary_translation="dog", part_of_speech="noun",
        status=ContentStatus.published, difficulty_rank=1,
    )
    db.add_all([gato, perro])
    db.flush()

    r = client.post("/api/v1/auth/signup",
                    json={"email": "say@example.com", "name": "S", "password": "supersecret1"})
    token = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    uid = uuid.UUID(me["id"])
    # mark the two items learned
    for item in (gato, perro):
        db.add(UserItemProgress(user_id=uid, item_type=ItemType.vocabulary,
                                item_id=item.id, srs_stage=1))
    db.commit()
    return {"headers": {"Authorization": f"Bearer {token}"}, "uid": uid,
            "gato": gato, "perro": perro}


def test_speaking_requires_auth(client):
    assert client.post("/api/v1/me/practice/speaking/start").status_code == 401
    assert client.post("/api/v1/me/practice/speaking/score",
                       json={"item_type": "vocabulary", "item_id": "x",
                             "transcript": "gato", "idempotency_key": "k"}).status_code == 401


def test_start_returns_learned_items_only(client, learner):
    r = client.post("/api/v1/me/practice/speaking/start", headers=learner["headers"])
    assert r.status_code == 200
    prompts = r.json()["prompts"]
    assert {p["prompt"] for p in prompts} == {"gato", "perro"}
    for p in prompts:
        assert p["prompt_lang"] == "es" and p["hint"] in ("cat", "dog")


def test_correct_utterance_passes_awards_xp_and_advances_stage(client, db, learner):
    body = {"item_type": "vocabulary", "item_id": str(learner["gato"].id),
            "transcript": "gato", "idempotency_key": str(uuid.uuid4())}
    r = client.post("/api/v1/me/practice/speaking/score", headers=learner["headers"], json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["passed"] is True and out["score"] == 100
    assert out["xp_awarded"] > 0
    assert out["practice_stage"] == 1  # advanced Uno

    stage = db.execute(select(UserItemPracticeStage).where(
        UserItemPracticeStage.category == PracticeCategory.speaking)).scalar_one()
    assert stage.stage == 1


def test_client_cannot_fake_a_pass(client, db, learner):
    # The transcript is scored against the SERVER's expected phrase; a wrong
    # utterance fails no matter what the client sends.
    body = {"item_type": "vocabulary", "item_id": str(learner["gato"].id),
            "transcript": "elephant zebra", "idempotency_key": str(uuid.uuid4())}
    out = client.post("/api/v1/me/practice/speaking/score",
                     headers=learner["headers"], json=body).json()
    assert out["passed"] is False and out["score"] == 0
    assert out["xp_awarded"] == 0
    total_xp = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()
    assert total_xp == 0


def test_scoring_is_idempotent(client, db, learner):
    key = str(uuid.uuid4())
    body = {"item_type": "vocabulary", "item_id": str(learner["gato"].id),
            "transcript": "gato", "idempotency_key": key}
    first = client.post("/api/v1/me/practice/speaking/score",
                       headers=learner["headers"], json=body).json()
    second = client.post("/api/v1/me/practice/speaking/score",
                        headers=learner["headers"], json=body).json()
    assert first["xp_awarded"] > 0 and second["already_scored"] is True
    assert second["xp_awarded"] == 0
    # XP awarded once; stage advanced once
    total_xp = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()
    assert total_xp == first["xp_awarded"]
    stage = db.execute(select(UserItemPracticeStage).where(
        UserItemPracticeStage.category == PracticeCategory.speaking)).scalar_one()
    assert stage.stage == 1


def test_cannot_score_an_unlearned_item(client, db, learner):
    # a published item the learner has NOT met
    other = VocabularyItem(
        language_id=learner["gato"].language_id, module_id=learner["gato"].module_id,
        term="casa", normalized_term="casa", primary_translation="house",
        part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1,
    )
    db.add(other)
    db.commit()
    body = {"item_type": "vocabulary", "item_id": str(other.id),
            "transcript": "casa", "idempotency_key": str(uuid.uuid4())}
    r = client.post("/api/v1/me/practice/speaking/score", headers=learner["headers"], json=body)
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "not_learned"
