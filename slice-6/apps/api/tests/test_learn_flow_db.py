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
    _pass_quiz(client, learner["headers"], 1, pos, db)
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
    _pass_quiz(client, learner["headers"], 1, 1, db)
    first = client.post("/api/v1/levels/1/lessons/1/complete",
                        headers=learner["headers"], json={"idempotency_key": key}).json()
    second = client.post("/api/v1/levels/1/lessons/1/complete",
                         headers=learner["headers"], json={"idempotency_key": key}).json()
    assert second["already_completed"] is True
    total_xp = db.execute(
        select(func.coalesce(func.sum(XpEvent.amount), 0))
    ).scalar_one()
    assert total_xp == first["xp_awarded"]   # not double-awarded


def _pass_quiz(client, headers, level, lesson_pos, db):
    """Answer every quiz prompt correctly so the items are allowed into the SRS."""
    quiz = client.post(f"/api/v1/levels/{level}/lessons/{lesson_pos}/quiz",
                       headers=headers)
    if quiz.status_code != 200:
        return
    body = quiz.json()
    for p in body["prompts"]:
        if p["item_type"] == "vocabulary":
            item = db.get(VocabularyItem, uuid.UUID(p["item_id"]))
            answer = item.primary_translation if item else ""
        else:
            item = db.get(GrammarPoint, uuid.UUID(p["item_id"]))
            answer = item.translation if item else ""
        client.post(f"/api/v1/quiz/{body['session_id']}/answers", headers=headers,
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "answer": answer, "idempotency_key": str(uuid.uuid4())})


def _unlock_all(client, db, learner):
    lessons = client.get("/api/v1/levels/1/lessons", headers=learner["headers"]).json()
    for l in lessons:
        _pass_quiz(client, learner["headers"], 1, l["position"], db)
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
    # WaniKani-style fields
    assert "stage_group_counts" in s
    assert set(s["stage_group_counts"].keys()) == {
        "beginner", "familiar", "intermediate", "advanced", "fluent",
    }
    assert len(s["stage_counts"]) == 9           # one per SRS stage
    assert len(s["forecast"]) == 7               # today + 6 days
    # everything just unlocked sits at Beginner, so lessons_available is 0 here
    assert s["lessons_available"] == 0
    # all learned items are at stage 1 (beginner group)
    assert s["stage_group_counts"]["beginner"] == s["items_learned"]


def test_lessons_available_counts_unstarted_published_items(client, db, learner):
    # Before completing any lesson, all published items are "available to learn".
    r = client.get("/api/v1/me/stats", headers=learner["headers"])
    s = r.json()
    # learner fixture published 4 vocab + 1 grammar, none started yet
    assert s["lessons_available"] == 5
    assert s["items_learned"] == 0


# --- lesson quiz gate (WaniKani-style) -----------------------------------

def test_quiz_returns_a_prompt_per_lesson_item(client, db, learner):
    lessons = client.get("/api/v1/levels/1/lessons", headers=learner["headers"]).json()
    pos = lessons[0]["position"]
    detail = client.get(f"/api/v1/levels/1/lessons/{pos}", headers=learner["headers"]).json()
    quiz = client.post(f"/api/v1/levels/1/lessons/{pos}/quiz", headers=learner["headers"])
    assert quiz.status_code == 200
    body = quiz.json()
    assert len(body["prompts"]) == len(detail["items"])
    # the quiz shows the Spanish and asks for the meaning — never leaks the answer
    assert "expected" not in body["prompts"][0]
    assert "translation" not in body["prompts"][0]


def test_lesson_does_not_unlock_without_passing_the_quiz(client, db, learner):
    """This is the core gate: teaching isn't proof, so nothing enters the SRS
    until the learner answers correctly."""
    r = client.post("/api/v1/levels/1/lessons/1/complete", headers=learner["headers"],
                    json={"idempotency_key": str(uuid.uuid4())})
    assert r.status_code == 200
    body = r.json()
    assert body["unlocked"] == 0
    assert body["blocked_by_quiz"] > 0
    assert body["xp_awarded"] == 0
    assert db.execute(select(func.count()).select_from(UserItemProgress)).scalar_one() == 0


def test_wrong_quiz_answer_does_not_unlock_that_item(client, db, learner):
    quiz = client.post("/api/v1/levels/1/lessons/1/quiz", headers=learner["headers"]).json()
    p = quiz["prompts"][0]
    r = client.post(f"/api/v1/quiz/{quiz['session_id']}/answers", headers=learner["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "answer": "definitely not the answer",
                          "idempotency_key": str(uuid.uuid4())})
    assert r.status_code == 200
    assert r.json()["correct"] is False

    done = client.post("/api/v1/levels/1/lessons/1/complete", headers=learner["headers"],
                       json={"idempotency_key": str(uuid.uuid4())}).json()
    assert done["unlocked"] == 0            # the wrong answer proved nothing
    assert done["blocked_by_quiz"] > 0


def test_retrying_a_quiz_item_correctly_unlocks_it(client, db, learner):
    """Wrong answers aren't punished — the learner just tries again."""
    quiz = client.post("/api/v1/levels/1/lessons/1/quiz", headers=learner["headers"]).json()
    p = next(x for x in quiz["prompts"] if x["item_type"] == "vocabulary")
    # first attempt wrong
    client.post(f"/api/v1/quiz/{quiz['session_id']}/answers", headers=learner["headers"],
                json={"item_type": p["item_type"], "item_id": p["item_id"],
                      "answer": "wrong", "idempotency_key": str(uuid.uuid4())})
    # second attempt right
    item = db.get(VocabularyItem, uuid.UUID(p["item_id"]))
    r = client.post(f"/api/v1/quiz/{quiz['session_id']}/answers", headers=learner["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "answer": item.primary_translation,
                          "idempotency_key": str(uuid.uuid4())})
    assert r.json()["correct"] is True

    done = client.post("/api/v1/levels/1/lessons/1/complete", headers=learner["headers"],
                       json={"idempotency_key": str(uuid.uuid4())}).json()
    assert done["unlocked"] >= 1            # the retried item made it through


def test_quiz_grades_server_side_and_accepts_typos(client, db, learner):
    quiz = client.post("/api/v1/levels/1/lessons/1/quiz", headers=learner["headers"]).json()
    p = next(x for x in quiz["prompts"] if x["item_type"] == "vocabulary")
    item = db.get(VocabularyItem, uuid.UUID(p["item_id"]))
    # one transposed letter should still pass, and the response reveals the answer
    typo = item.primary_translation
    if len(typo) > 4:
        typo = typo[:2] + typo[3] + typo[2] + typo[4:]
    r = client.post(f"/api/v1/quiz/{quiz['session_id']}/answers", headers=learner["headers"],
                    json={"item_type": p["item_type"], "item_id": p["item_id"],
                          "answer": typo, "idempotency_key": str(uuid.uuid4())}).json()
    assert r["expected"] == item.primary_translation


# --- level unlock gating -------------------------------------------------

def test_level_one_is_always_unlocked_and_reports_no_progress(client, db, learner):
    levels = client.get("/api/v1/levels", headers=learner["headers"]).json()
    lv1 = next(l for l in levels if l["position"] == 1)
    assert lv1["unlocked"] is True
    assert lv1["unlock_progress"] is None


def test_later_levels_report_unlock_progress(client, db, learner):
    """A locked level tells the learner exactly how far off they are."""
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m2 = Module(language_id=lang.id, position=2, title="Level 2",
                status=ContentStatus.published)
    db.add(m2)
    db.flush()
    db.add(VocabularyItem(
        language_id=lang.id, module_id=m2.id, term="otra", normalized_term="otra",
        primary_translation="another", status=ContentStatus.published, difficulty_rank=1,
    ))
    db.commit()

    levels = client.get("/api/v1/levels", headers=learner["headers"]).json()
    lv2 = next(l for l in levels if l["position"] == 2)
    assert lv2["unlocked"] is False          # level 1 isn't at Familiar yet
    assert lv2["unlock_progress"] is not None
    assert lv2["unlock_progress"]["percent"] == 0
    assert lv2["unlock_progress"]["remaining"] > 0


def test_level_unlocks_only_when_everything_reaches_familiar(client, db, learner):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m2 = Module(language_id=lang.id, position=2, title="Level 2",
                status=ContentStatus.published)
    db.add(m2)
    db.commit()

    _unlock_all(client, db, learner)
    rows = db.execute(select(UserItemProgress)).scalars().all()

    # everything but one item at Familiar 1 -> still locked
    for p in rows:
        p.srs_stage = 5
    rows[0].srs_stage = 4
    db.commit()
    levels = client.get("/api/v1/levels", headers=learner["headers"]).json()
    assert next(l for l in levels if l["position"] == 2)["unlocked"] is False

    # that last item reaches Familiar 1 -> unlocked
    rows[0].srs_stage = 5
    db.commit()
    levels = client.get("/api/v1/levels", headers=learner["headers"]).json()
    lv2 = next(l for l in levels if l["position"] == 2)
    assert lv2["unlocked"] is True
    assert lv2["unlock_progress"]["percent"] == 100


# --- lessons_available is scoped to UNLOCKED levels ----------------------

def _add_level(db, position: int, vocab_n: int):
    """Add a published level with some published vocabulary."""
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m = Module(language_id=lang.id, position=position, title=f"Level {position}",
               status=ContentStatus.published)
    db.add(m)
    db.flush()
    for i in range(vocab_n):
        db.add(VocabularyItem(
            language_id=lang.id, module_id=m.id, term=f"l{position}w{i}",
            normalized_term=f"l{position}w{i}", primary_translation=f"l{position}word{i}",
            part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1,
        ))
    db.commit()
    return m


def test_lessons_available_counts_only_unlocked_levels(client, db, learner):
    """The dashboard's lesson count must reflect what's actually reachable —
    not the entire published curriculum."""
    _add_level(db, 2, 30)
    _add_level(db, 3, 30)

    s = client.get("/api/v1/me/stats", headers=learner["headers"]).json()
    # learner fixture has 4 vocab + 1 grammar in level 1; levels 2 and 3 are locked
    assert s["lessons_available"] == 5
    assert s["lessons_available"] != 65   # would be the "count everything" bug


def test_lessons_available_grows_when_a_level_unlocks(client, db, learner):
    _add_level(db, 2, 30)

    before = client.get("/api/v1/me/stats", headers=learner["headers"]).json()
    assert before["lessons_available"] == 5

    # take level 1 to Familiar 1 so level 2 opens
    _unlock_all(client, db, learner)
    for p in db.execute(select(UserItemProgress)).scalars().all():
        p.srs_stage = 5
    db.commit()

    after = client.get("/api/v1/me/stats", headers=learner["headers"]).json()
    assert after["lessons_available"] == 30      # level 2's items are now reachable


def test_locked_level_lessons_are_not_reachable_by_url(client, db, learner):
    """The gate is server-side: navigating straight to a locked level fails."""
    _add_level(db, 2, 5)
    r = client.get("/api/v1/levels/2/lessons", headers=learner["headers"])
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "level_locked"

    detail = client.get("/api/v1/levels/2/lessons/1", headers=learner["headers"])
    assert detail.status_code == 403

    quiz = client.post("/api/v1/levels/2/lessons/1/quiz", headers=learner["headers"])
    assert quiz.status_code == 403

    done = client.post("/api/v1/levels/2/lessons/1/complete", headers=learner["headers"],
                       json={"idempotency_key": str(uuid.uuid4())})
    assert done.status_code == 403


def test_unlocked_level_lessons_are_reachable(client, db, learner):
    _add_level(db, 2, 5)
    _unlock_all(client, db, learner)
    for p in db.execute(select(UserItemProgress)).scalars().all():
        p.srs_stage = 5
    db.commit()
    r = client.get("/api/v1/levels/2/lessons", headers=learner["headers"])
    assert r.status_code == 200
