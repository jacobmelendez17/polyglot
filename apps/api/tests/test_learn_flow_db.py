"""End-to-end learning loop against a real database:
lesson -> unlock into SRS -> review pair -> SRS transition -> XP.
"""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.progress import UserItemProgress, XpEvent


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def learner(client, db):
    """A signed-up user with a published mini-curriculum."""
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=lang.id, position=1, title="Level 1",
                    status=ContentStatus.published)
    db.add(module)
    db.flush()
    for i in range(4):
        db.add(VocabularyItem(
            language_id=lang.id, module_id=module.id, term=f"palabra{i}",
            normalized_term=f"palabra{i}", primary_translation=f"word{i}",
            part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1,
        ))
    db.add(GrammarPoint(
        language_id=lang.id, module_id=module.id, title="ser vs estar",
        translation="to be", status=ContentStatus.published,
    ))
    db.commit()

    r = client.post("/api/v1/auth/signup",
                    json={"email": "learn@example.com", "name": "Ana", "password": "supersecret1"})
    token = r.json()["access_token"]
    return {"token": token, "module": module, "headers": {"Authorization": f"Bearer {token}"}}


def test_levels_list_shows_published_counts(client, learner):
    r = client.get("/api/v1/levels", headers=learner["headers"])
    assert r.status_code == 200
    lv = r.json()[0]
    assert lv["position"] == 1
    assert lv["vocab_count"] == 4
    assert lv["grammar_count"] == 1
    assert lv["unlocked"] is True   # level 1 always open


def test_lesson_detail_returns_teaching_payload(client, learner):
    lessons = client.get("/api/v1/levels/1/lessons", headers=learner["headers"]).json()
    assert len(lessons) >= 1
    detail = client.get(f"/api/v1/levels/1/lessons/{lessons[0]['position']}",
                        headers=learner["headers"])
    assert detail.status_code == 200
    items = detail.json()["items"]
    assert len(items) > 0
    assert "term" in items[0] and "translation" in items[0]
    # accepted/rejected answers must never be exposed
    assert "accepted_answers" not in items[0]
    assert "rejected_answers" not in items[0]


def test_completing_a_lesson_unlocks_srs_and_awards_xp(client, db, learner):
    lessons = client.get("/api/v1/levels/1/lessons", headers=learner["headers"]).json()
    pos = lessons[0]["position"]
    r = client.post(f"/api/v1/levels/1/lessons/{pos}/complete",
                    headers=learner["headers"],
                    json={"idempotency_key": str(uuid.uuid4())})
    assert r.status_code == 200
    body = r.json()
    assert body["unlocked"] > 0
    assert body["xp_awarded"] > 0

    progress = db.execute(select(UserItemProgress)).scalars().all()
    assert len(progress) == body["unlocked"]
    for p in progress:
        assert p.srs_stage == 1               # Beginner 1
        assert p.next_review_at is not None   # first review scheduled
        assert p.lesson_completed_at is not None


def test_lesson_completion_is_idempotent(client, db, learner):
    key = str(uuid.uuid4())
    first = client.post("/api/v1/levels/1/lessons/1/complete",
                        headers=learner["headers"], json={"idempotency_key": key}).json()
    second = client.post("/api/v1/levels/1/lessons/1/complete",
                         headers=learner["headers"], json={"idempotency_key": key}).json()
    assert second["already_completed"] is True
    total_xp = db.execute(
        select(func.coalesce(func.sum(XpEvent.amount), 0))
    ).scalar_one()
    assert total_xp == first["xp_awarded"]   # not double-awarded


def _unlock_all(client, db, learner):
    lessons = client.get("/api/v1/levels/1/lessons", headers=learner["headers"]).json()
    for l in lessons:
        client.post(f"/api/v1/levels/1/lessons/{l['position']}/complete",
                    headers=learner["headers"], json={"idempotency_key": str(uuid.uuid4())})
    # make everything due now
    for p in db.execute(select(UserItemProgress)).scalars().all():
        p.next_review_at = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(minutes=1)
    db.commit()


def test_review_session_returns_two_prompts_per_item(client, db, learner):
    _unlock_all(client, db, learner)
    r = client.post("/api/v1/reviews/sessions", headers=learner["headers"])
    assert r.status_code == 200
    prompts = r.json()["prompts"]
    item_count = db.execute(select(func.count()).select_from(UserItemProgress)).scalar_one()
    assert len(prompts) == item_count * 2
    assert prompts[0]["shown"]           # something to answer
    assert "expected" not in prompts[0]  # never leak the answer


def test_correct_pair_promotes_and_awards_xp(client, db, learner):
    _unlock_all(client, db, learner)
    session = client.post("/api/v1/reviews/sessions", headers=learner["headers"]).json()
    sid = session["session_id"]
    target = next(p for p in session["prompts"] if p["item_type"] == "vocabulary")
    item_id = target["item_id"]

    v = db.get(VocabularyItem, uuid.UUID(item_id))
    answers = {"es_to_en": v.primary_translation, "en_to_es": v.term}

    results = []
    for p in [x for x in session["prompts"] if x["item_id"] == item_id]:
        r = client.post(f"/api/v1/reviews/sessions/{sid}/answers",
                        headers=learner["headers"],
                        json={"item_type": "vocabulary", "item_id": item_id,
                              "direction": p["direction"], "answer": answers[p["direction"]],
                              "idempotency_key": str(uuid.uuid4())})
        assert r.status_code == 200, r.text
        results.append(r.json())

    assert results[0]["pair_resolved"] is False   # SRS waits for the second prompt
    assert results[1]["pair_resolved"] is True
    assert results[1]["srs_stage_before"] == 1
    assert results[1]["srs_stage_after"] == 2     # promoted
    assert results[1]["xp_awarded"] == 10         # vocabulary review


def test_one_wrong_answer_demotes_the_pair(client, db, learner):
    _unlock_all(client, db, learner)
    # push an item up to Familiar 1 so the penalty factor is 2
    p = db.execute(
        select(UserItemProgress).where(UserItemProgress.item_type == ItemType.vocabulary)
    ).scalars().first()
    p.srs_stage = 5
    db.commit()
    item_id = str(p.item_id)

    session = client.post("/api/v1/reviews/sessions", headers=learner["headers"]).json()
    sid = session["session_id"]
    v = db.get(VocabularyItem, p.item_id)
    prompts = [x for x in session["prompts"] if x["item_id"] == item_id]

    # first prompt wrong, second right
    client.post(f"/api/v1/reviews/sessions/{sid}/answers", headers=learner["headers"],
                json={"item_type": "vocabulary", "item_id": item_id,
                      "direction": prompts[0]["direction"], "answer": "definitely wrong",
                      "idempotency_key": str(uuid.uuid4())})
    correct = v.primary_translation if prompts[1]["direction"] == "es_to_en" else v.term
    last = client.post(f"/api/v1/reviews/sessions/{sid}/answers", headers=learner["headers"],
                       json={"item_type": "vocabulary", "item_id": item_id,
                             "direction": prompts[1]["direction"], "answer": correct,
                             "idempotency_key": str(uuid.uuid4())}).json()
    # stage 5, 1 wrong -> ceil(1/2)=1 * penalty 2 = 2 -> stage 3
    assert last["pair_resolved"] is True
    assert last["srs_stage_after"] == 3


def test_answer_submission_is_idempotent(client, db, learner):
    _unlock_all(client, db, learner)
    session = client.post("/api/v1/reviews/sessions", headers=learner["headers"]).json()
    sid = session["session_id"]
    p = next(x for x in session["prompts"] if x["item_type"] == "vocabulary")
    key = str(uuid.uuid4())
    body = {"item_type": p["item_type"], "item_id": p["item_id"],
            "direction": p["direction"], "answer": "algo", "idempotency_key": key}
    first = client.post(f"/api/v1/reviews/sessions/{sid}/answers",
                        headers=learner["headers"], json=body).json()
    second = client.post(f"/api/v1/reviews/sessions/{sid}/answers",
                         headers=learner["headers"], json=body).json()
    assert first["answer_id"] == second["answer_id"]   # same row, not a duplicate


def test_undo_marks_correct_without_touching_xp(client, db, learner):
    _unlock_all(client, db, learner)
    session = client.post("/api/v1/reviews/sessions", headers=learner["headers"]).json()
    sid = session["session_id"]
    p = next(x for x in session["prompts"] if x["item_type"] == "vocabulary")
    wrong = client.post(f"/api/v1/reviews/sessions/{sid}/answers", headers=learner["headers"],
                        json={"item_type": p["item_type"], "item_id": p["item_id"],
                              "direction": p["direction"], "answer": "totally wrong",
                              "idempotency_key": str(uuid.uuid4())}).json()
    assert wrong["original_correct"] is False
    xp_before = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()

    r = client.post(f"/api/v1/reviews/answers/{wrong['answer_id']}/undo",
                    headers=learner["headers"], json={"reason": "typo"})
    assert r.status_code == 200
    xp_after = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()
    assert xp_after == xp_before   # undo never grants XP


def test_early_exit_keeps_only_resolved_pairs(client, db, learner):
    _unlock_all(client, db, learner)
    session = client.post("/api/v1/reviews/sessions", headers=learner["headers"]).json()
    sid = session["session_id"]
    p = next(x for x in session["prompts"] if x["item_type"] == "vocabulary")
    # answer only ONE prompt of the pair, then abandon
    client.post(f"/api/v1/reviews/sessions/{sid}/answers", headers=learner["headers"],
                json={"item_type": p["item_type"], "item_id": p["item_id"],
                      "direction": p["direction"], "answer": "x",
                      "idempotency_key": str(uuid.uuid4())})
    prog = db.execute(
        select(UserItemProgress).where(UserItemProgress.item_id == uuid.UUID(p["item_id"]))
    ).scalar_one()
    assert prog.srs_stage == 1   # unchanged: the pair never resolved

    r = client.post(f"/api/v1/reviews/sessions/{sid}/complete?abandoned=true",
                    headers=learner["headers"])
    assert r.status_code == 200
    assert r.json()["state"] == "abandoned"


def test_reviews_require_authentication(client):
    assert client.post("/api/v1/reviews/sessions").status_code == 401
    assert client.get("/api/v1/levels").status_code == 401


def test_stats_reflect_progress(client, db, learner):
    _unlock_all(client, db, learner)
    r = client.get("/api/v1/me/stats", headers=learner["headers"])
    assert r.status_code == 200
    s = r.json()
    assert s["items_learned"] > 0
    assert s["reviews_due"] > 0
    assert s["xp_total"] > 0
