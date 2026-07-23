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

    # learn all six: teach, pass the quiz (items only unlock once proven), complete
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


# --- listening practice ---------------------------------------------------

def test_listening_session_speaks_without_showing_the_word(client, db, practiced_user):
    r = client.post("/api/v1/practice/sessions?mode=listening",
                    headers=practiced_user["headers"])
    assert r.status_code == 200, r.text
    prompts = r.json()["prompts"]
    assert len(prompts) > 0
    p = prompts[0]
    # the whole point: the Spanish is never displayed, only spoken
    assert p["shown"] == ""
    assert p["audio"] is not None
    assert p["audio"]["mode"] in ("browser_tts", "stored")
    assert p["audio"]["text"]          # something to say


def test_listening_expects_the_spanish_word(client, db, practiced_user):
    session = client.post("/api/v1/practice/sessions?mode=listening",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    spoken = p["audio"]["text"]        # the Spanish term that was read aloud
    r = client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                    headers=practiced_user["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "mode": "listening", "answer": spoken,
                          "idempotency_key": str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    assert r.json()["correct"] is True


def test_listening_rejects_the_english(client, db, practiced_user):
    session = client.post("/api/v1/practice/sessions?mode=listening",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    r = client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
                    headers=practiced_user["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "mode": "listening", "answer": p["translation"],
                          "idempotency_key": str(uuid.uuid4())}).json()
    assert r["correct"] is False       # typing the meaning isn't hearing it


# --- practice-stage category + 24h gate + overall perfect -----------------

def test_listening_practice_advances_listening_category_not_sentences(client, db, practiced_user):
    from app.models.enums import PracticeCategory
    from app.models.progress import UserItemPracticeStage

    session = client.post("/api/v1/practice/sessions?mode=listening",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    spoken = p["audio"]["text"]
    client.post(f"/api/v1/practice/sessions/{session['session_id']}/answers",
               headers=practiced_user["headers"],
               json={"item_type": p["item_type"], "item_id": p["item_id"],
                     "mode": "listening", "answer": spoken, "idempotency_key": str(uuid.uuid4())})

    listening_stage = db.execute(
        select(UserItemPracticeStage).where(
            UserItemPracticeStage.item_id == uuid.UUID(p["item_id"]),
            UserItemPracticeStage.category == PracticeCategory.listening,
        )
    ).scalar_one_or_none()
    sentences_stage = db.execute(
        select(UserItemPracticeStage).where(
            UserItemPracticeStage.item_id == uuid.UUID(p["item_id"]),
            UserItemPracticeStage.category == PracticeCategory.sentences,
        )
    ).scalar_one_or_none()
    assert listening_stage is not None and listening_stage.stage == 1
    assert sentences_stage is None   # never touched by a listening rep


def test_practice_stage_holds_within_24h_then_advances(client, db, practiced_user):
    import datetime as _dt

    from app.services import practice as practice_svc

    session = client.post("/api/v1/practice/sessions?mode=weak_items",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    t0 = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)
    user_id = _user_id(db)

    g1 = practice_svc.grade_practice(
        db, user_id=user_id, item_type=p["item_type"], item_id=p["item_id"], mode="weak_items",
        submitted=p["translation"], idempotency_key=uuid.uuid4(), now=t0,
    )
    db.commit()
    assert g1.practice_stage == 1

    # Same item, one hour later — still gated, stage holds.
    g2 = practice_svc.grade_practice(
        db, user_id=_user_id(db), item_type=p["item_type"], item_id=p["item_id"],
        mode="weak_items", submitted=p["translation"], idempotency_key=uuid.uuid4(),
        now=t0 + _dt.timedelta(hours=1),
    )
    db.commit()
    assert g2.practice_stage == 1

    # 24h later — gate clears.
    g3 = practice_svc.grade_practice(
        db, user_id=_user_id(db), item_type=p["item_type"], item_id=p["item_id"],
        mode="weak_items", submitted=p["translation"], idempotency_key=uuid.uuid4(),
        now=t0 + _dt.timedelta(hours=24),
    )
    db.commit()
    assert g3.practice_stage == 2


def _user_id(db):
    from app.models.identity import User
    return db.execute(select(User.id).where(User.email == "p@example.com")).scalar_one()


def test_perfect_at_requires_both_shipped_categories_and_fluent_srs(client, db, practiced_user):
    import datetime as _dt

    from app.models.enums import PracticeCategory
    from app.models.progress import UserItemPracticeStage
    from app.services import practice as practice_svc

    session = client.post("/api/v1/practice/sessions?mode=listening",
                          headers=practiced_user["headers"]).json()
    p = session["prompts"][0]
    item_id = uuid.UUID(p["item_id"])
    user_id = _user_id(db)

    progress = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id, UserItemProgress.item_id == item_id,
        )
    ).scalar_one()
    progress.srs_stage = 9   # Fluent
    db.add(UserItemPracticeStage(
        user_id=user_id, item_type=progress.item_type, item_id=item_id,
        category=PracticeCategory.sentences, stage=4, stage_reached_at=None,
    ))
    db.add(UserItemPracticeStage(
        user_id=user_id, item_type=progress.item_type, item_id=item_id,
        category=PracticeCategory.listening, stage=4, stage_reached_at=None,
    ))
    db.commit()

    now = _dt.datetime.now(tz=_dt.timezone.utc)
    spoken = p["audio"]["text"]
    grade = practice_svc.grade_practice(
        db, user_id=user_id, item_type="vocabulary", item_id=str(item_id), mode="listening",
        submitted=spoken, idempotency_key=uuid.uuid4(), now=now,
    )
    db.commit()
    # listening just reached 5, but sentences is still at 4 — not perfect yet.
    assert grade.practice_stage == 5
    assert grade.perfect_overall is False

    # weak_items (no example sentence for this item) falls back to translating
    # INTO Spanish — the expected answer is the term itself, not the gloss.
    term = db.get(VocabularyItem, item_id).term
    grade2 = practice_svc.grade_practice(
        db, user_id=user_id, item_type="vocabulary", item_id=str(item_id), mode="weak_items",
        submitted=term, idempotency_key=uuid.uuid4(), now=now,
    )
    db.commit()
    assert grade2.practice_stage == 5
    assert grade2.perfect_overall is True

    db.refresh(progress)
    assert progress.perfect_at is not None


def test_review_prompts_include_audio(client, db, practiced_user):
    import datetime as _dt

    from app.models.progress import UserItemProgress
    for prog in db.execute(select(UserItemProgress)).scalars().all():
        prog.next_review_at = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=1)
    db.commit()
    session = client.post("/api/v1/reviews/sessions",
                          headers=practiced_user["headers"]).json()
    assert session["prompts"], "expected due reviews"
    assert any(p.get("audio") for p in session["prompts"])
