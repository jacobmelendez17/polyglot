"""Item detail, review history, user synonyms, level progression.

Real Postgres + TestClient. These tests care about three things: that the
answer key never leaks, that reads are scoped to the requesting user, and that
a locked level is a 403 rather than a hidden link.
"""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import (
    GrammarPoint,
    Language,
    Module,
    Sentence,
    SentenceLink,
    VocabularyItem,
)
from app.models.enums import ItemType, PracticeCategory
from app.models.progress import (
    ReviewAnswer,
    ReviewSession,
    UserItemPracticeStage,
    UserItemProgress,
    UserSynonym,
)

NOW = dt.datetime(2026, 7, 22, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email: str) -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "Learner", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _module(db, lang_id, position: int) -> Module:
    m = Module(language_id=lang_id, position=position, title=f"Level {position}",
               status=ContentStatus.published)
    db.add(m)
    db.flush()
    return m


def _vocab(db, lang_id, module_id, term, translation, **kw) -> VocabularyItem:
    v = VocabularyItem(
        language_id=lang_id, module_id=module_id, term=term,
        normalized_term=term.lower(), primary_translation=translation,
        part_of_speech=kw.pop("part_of_speech", "noun"),
        status=ContentStatus.published,
        accepted_answers=kw.pop("accepted_answers", ["the house"]),
        rejected_answers=kw.pop("rejected_answers", ["home office"]),
        synonyms=kw.pop("synonyms", ["dwelling"]),
        **kw,
    )
    db.add(v)
    db.flush()
    return v


@pytest.fixture()
def world(client, db):
    """One learner, one unlocked level with 2 vocab + 1 grammar, one locked level."""
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    level1 = _module(db, lang.id, 1)
    level2 = _module(db, lang.id, 2)

    casa = _vocab(db, lang.id, level1.id, "casa", "house", meaning="a place to live",
                  pronunciation="KAH-sah", ipa="ˈkasa")
    correr = _vocab(db, lang.id, level1.id, "correr", "to run",
                    part_of_speech="verb", accepted_answers=["run"],
                    rejected_answers=[], synonyms=[])
    gram = GrammarPoint(
        language_id=lang.id, module_id=level1.id, title="ser vs estar",
        translation="to be (permanent vs temporary)", structure_pattern="ser + adj",
        explanation_rich="Use ser for essence.", status=ContentStatus.published,
        accepted_answers=["to be"], rejected_answers=["to have"], synonyms=[],
    )
    db.add(gram)
    # Level 2 needs published content so the level exists but stays locked.
    _vocab(db, lang.id, level2.id, "playa", "beach")

    sentence = Sentence(language_id=lang.id, text_es="Esta es mi casa.",
                        text_en="This is my house.", difficulty="phrase",
                        status=ContentStatus.published)
    db.add(sentence)
    db.flush()
    db.add(SentenceLink(sentence_id=sentence.id, item_type=ItemType.vocabulary,
                        item_id=casa.id, role="example"))
    db.commit()

    headers = _signup(client, "learner@example.com")
    return {"headers": headers, "lang": lang, "casa": casa, "correr": correr,
            "grammar": gram, "level2": level2}


def _user_id(db, email="learner@example.com") -> uuid.UUID:
    from app.models.identity import User
    return db.execute(select(User).where(User.email == email)).scalar_one().id


def _learn(db, user_id, item_type: ItemType, item_id, *, stage=3, **kw):
    p = UserItemProgress(
        user_id=user_id, item_type=item_type, item_id=item_id, srs_stage=stage,
        lesson_completed_at=NOW - dt.timedelta(days=2),
        unlocked_at=NOW - dt.timedelta(days=2),
        next_review_at=NOW + dt.timedelta(hours=4),
        total_reviews=kw.pop("total_reviews", 4),
        total_incorrect=kw.pop("total_incorrect", 1),
        **kw,
    )
    db.add(p)
    db.flush()
    return p


# --- authorization -------------------------------------------------------

def test_item_detail_requires_auth(client, world):
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}")
    assert r.status_code == 401


def test_item_in_a_locked_level_is_forbidden(client, db, world):
    playa = db.execute(
        select(VocabularyItem).where(VocabularyItem.term == "playa")
    ).scalar_one()
    r = client.get(f"/api/v1/items/vocabulary/{playa.id}", headers=world["headers"])
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "level_locked"


def test_unknown_item_is_404(client, world):
    r = client.get(f"/api/v1/items/vocabulary/{uuid.uuid4()}", headers=world["headers"])
    assert r.status_code == 404


def test_bad_item_type_is_rejected_by_validation(client, world):
    r = client.get(f"/api/v1/items/sandwich/{world['casa'].id}",
                   headers=world["headers"])
    assert r.status_code == 422


def test_draft_items_are_invisible_to_learners(client, db, world):
    world["casa"].status = ContentStatus.draft
    db.commit()
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"])
    assert r.status_code == 404


# --- privacy -------------------------------------------------------------

def test_item_detail_never_leaks_the_answer_key(client, world):
    """accepted_answers / rejected_answers are private (spec §6)."""
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"])
    assert r.status_code == 200
    body = r.text
    assert "accepted_answers" not in body
    assert "rejected_answers" not in body
    assert "home office" not in body           # the rejected answer's text
    payload = r.json()
    assert payload["synonyms"] == ["dwelling"]  # public synonyms still shown


# --- detail content ------------------------------------------------------

def test_item_detail_shows_the_word_and_its_level(client, world):
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"]).json()
    assert r["term"] == "casa"
    assert r["translation"] == "house"
    assert r["level"] == 1
    assert r["pronunciation"] == "KAH-sah"
    assert r["audio"]["mode"] in ("stored", "browser_tts")
    assert r["examples"][0]["text_es"] == "Esta es mi casa."


def test_unlearned_item_reports_an_empty_progress_state(client, world):
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"]).json()
    assert r["progress"]["learned"] is False
    assert r["progress"]["srs_stage"] == 0
    assert r["progress"]["srs_stage_name"] == "Not learned"
    assert r["progress"]["accuracy"] is None
    assert r["practice"]["categories_complete"] == 0


def test_learned_item_reports_srs_state(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id, stage=6)
    db.commit()
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"]).json()
    assert r["progress"]["learned"] is True
    assert r["progress"]["srs_stage"] == 6
    assert r["progress"]["srs_stage_name"] == "Familiar 2"
    assert r["progress"]["next_review_at"] is not None


def test_grammar_detail_uses_grammar_fields(client, world):
    r = client.get(f"/api/v1/items/grammar/{world['grammar'].id}",
                   headers=world["headers"]).json()
    assert r["term"] == "ser vs estar"
    assert r["structure"] == "ser + adj"
    assert r["explanation"] == "Use ser for essence."


def test_articles_are_only_reported_for_nouns(client, world):
    """A verb must never be shown with el/la (spec §6)."""
    r = client.get(f"/api/v1/items/vocabulary/{world['correr'].id}",
                   headers=world["headers"]).json()
    assert r["part_of_speech"] == "verb"
    assert r["article"] is None


# --- practice stages -----------------------------------------------------

def test_practice_stages_are_surfaced_with_spanish_labels(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id, stage=9)
    db.add(UserItemPracticeStage(
        user_id=uid, item_type=ItemType.vocabulary, item_id=world["casa"].id,
        category=PracticeCategory.sentences, stage=3,
        stage_reached_at=dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=2),
    ))
    db.commit()

    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"]).json()
    by_category = {s["category"]: s for s in r["practice"]["stages"]}
    assert by_category["sentences"]["stage"] == 3
    assert by_category["sentences"]["label"] == "Stage Tres"
    assert by_category["sentences"]["on_cooldown"] is True
    assert by_category["listening"]["label"] == "Not started"
    assert r["practice"]["categories_complete"] == 0
    assert r["practice"]["perfect"] is False


def test_perfect_needs_all_categories_and_fluent(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id, stage=9)
    for category in PracticeCategory:
        db.add(UserItemPracticeStage(
            user_id=uid, item_type=ItemType.vocabulary, item_id=world["casa"].id,
            category=category, stage=5,
        ))
    db.commit()

    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"]).json()
    assert r["practice"]["categories_complete"] == 3
    assert r["practice"]["srs_fluent"] is True
    assert r["practice"]["perfect"] is True


# --- review history ------------------------------------------------------

def _answer(db, user_id, session_id, item_id, *, correct: bool, direction="es_to_en",
            undo=False, when=None):
    a = ReviewAnswer(
        session_id=session_id, user_id=user_id, item_type=ItemType.vocabulary,
        item_id=item_id, prompt_direction=direction, prompt_kind="translation",
        submitted_answer="casa" if correct else "cassa",
        normalized_answer="", original_correct=correct,
        final_correct=correct or undo, undo_used=undo,
        srs_stage_before=3, srs_stage_after=4 if correct else 2,
        idempotency_key=uuid.uuid4(),
        answered_at=when or dt.datetime.now(tz=dt.timezone.utc),
    )
    db.add(a)
    db.flush()
    return a


def test_history_returns_answers_newest_first(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id)
    session = ReviewSession(user_id=uid, kind="review", state="completed")
    db.add(session)
    db.flush()
    _answer(db, uid, session.id, world["casa"].id, correct=False)
    _answer(db, uid, session.id, world["casa"].id, correct=True)
    db.commit()

    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}/history",
                   headers=world["headers"]).json()
    assert r["total"] == 2
    assert len(r["items"]) == 2
    assert r["items"][0]["original_correct"] is True     # newest first


def test_history_records_an_undo_without_erasing_the_mistake(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id)
    session = ReviewSession(user_id=uid, kind="review", state="completed")
    db.add(session)
    db.flush()
    _answer(db, uid, session.id, world["casa"].id, correct=False, undo=True)
    db.commit()

    entry = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}/history",
                       headers=world["headers"]).json()["items"][0]
    assert entry["original_correct"] is False   # the mistake is still on record
    assert entry["final_correct"] is True
    assert entry["undo_used"] is True


def test_history_is_paginated(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id)
    session = ReviewSession(user_id=uid, kind="review", state="completed")
    db.add(session)
    db.flush()
    for _ in range(5):
        _answer(db, uid, session.id, world["casa"].id, correct=True)
    db.commit()

    page = client.get(
        f"/api/v1/items/vocabulary/{world['casa'].id}/history?limit=2&offset=2",
        headers=world["headers"],
    ).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["offset"] == 2


def test_history_page_size_is_capped(client, world):
    r = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}/history?limit=5000",
                   headers=world["headers"])
    assert r.status_code == 422


def test_history_is_scoped_to_the_requesting_user(client, db, world):
    """Another learner's answers must never appear here."""
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id)
    other_headers = _signup(client, "other@example.com")
    other_id = _user_id(db, "other@example.com")

    mine = ReviewSession(user_id=uid, kind="review", state="completed")
    theirs = ReviewSession(user_id=other_id, kind="review", state="completed")
    db.add_all([mine, theirs])
    db.flush()
    _answer(db, uid, mine.id, world["casa"].id, correct=True)
    for _ in range(3):
        _answer(db, other_id, theirs.id, world["casa"].id, correct=False)
    db.commit()

    assert client.get(f"/api/v1/items/vocabulary/{world['casa'].id}/history",
                      headers=world["headers"]).json()["total"] == 1
    assert client.get(f"/api/v1/items/vocabulary/{world['casa'].id}/history",
                      headers=other_headers).json()["total"] == 3


def test_accuracy_is_computed_from_recorded_answers(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id)
    session = ReviewSession(user_id=uid, kind="review", state="completed")
    db.add(session)
    db.flush()
    for correct in (True, True, True, False):
        _answer(db, uid, session.id, world["casa"].id, correct=correct)
    db.commit()

    p = client.get(f"/api/v1/items/vocabulary/{world['casa'].id}",
                   headers=world["headers"]).json()["progress"]
    assert p["answers_total"] == 4
    assert p["answers_correct"] == 3
    assert p["accuracy"] == 0.75
    assert p["mistakes"] == 1


# --- user synonyms -------------------------------------------------------

def test_add_and_list_a_user_synonym(client, world):
    url = f"/api/v1/items/vocabulary/{world['casa'].id}/synonyms"
    r = client.post(url, headers=world["headers"], json={"synonym": "  My  Place "})
    assert r.status_code == 201
    assert r.json()["synonym"] == "My Place"     # whitespace collapsed
    assert r.json()["created"] is True

    listed = client.get(url, headers=world["headers"]).json()
    assert [s["synonym"] for s in listed] == ["My Place"]


def test_duplicate_synonyms_are_idempotent(client, world):
    url = f"/api/v1/items/vocabulary/{world['casa'].id}/synonyms"
    client.post(url, headers=world["headers"], json={"synonym": "pad"})
    again = client.post(url, headers=world["headers"], json={"synonym": "PAD"})
    assert again.json()["created"] is False
    assert len(client.get(url, headers=world["headers"]).json()) == 1


def test_empty_and_overlong_synonyms_are_rejected(client, world):
    url = f"/api/v1/items/vocabulary/{world['casa'].id}/synonyms"
    assert client.post(url, headers=world["headers"],
                       json={"synonym": ""}).status_code == 422
    assert client.post(url, headers=world["headers"],
                       json={"synonym": "x" * 200}).status_code == 422


def test_synonym_cap_per_item(client, db, world):
    from app.services.items import MAX_USER_SYNONYMS_PER_ITEM
    uid = _user_id(db)
    for i in range(MAX_USER_SYNONYMS_PER_ITEM):
        db.add(UserSynonym(user_id=uid, item_type=ItemType.vocabulary,
                           item_id=world["casa"].id, synonym=f"s{i}",
                           normalized=f"s{i}"))
    db.commit()
    r = client.post(f"/api/v1/items/vocabulary/{world['casa'].id}/synonyms",
                    headers=world["headers"], json={"synonym": "one too many"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "limit_reached"


def test_synonyms_can_be_deleted_only_by_their_owner(client, db, world):
    url = f"/api/v1/items/vocabulary/{world['casa'].id}/synonyms"
    created = client.post(url, headers=world["headers"],
                          json={"synonym": "abode"}).json()
    other_headers = _signup(client, "thief@example.com")

    assert client.delete(f"/api/v1/synonyms/{created['id']}",
                         headers=other_headers).status_code == 404
    assert client.delete(f"/api/v1/synonyms/{created['id']}",
                         headers=world["headers"]).status_code == 204
    assert client.get(url, headers=world["headers"]).json() == []


def test_synonyms_on_a_locked_item_are_refused(client, db, world):
    playa = db.execute(
        select(VocabularyItem).where(VocabularyItem.term == "playa")
    ).scalar_one()
    r = client.post(f"/api/v1/items/vocabulary/{playa.id}/synonyms",
                    headers=world["headers"], json={"synonym": "shore"})
    assert r.status_code == 403


# --- level progression ---------------------------------------------------

def test_level_progress_lists_every_item_with_state(client, db, world):
    uid = _user_id(db)
    _learn(db, uid, ItemType.vocabulary, world["casa"].id, stage=5)
    db.commit()

    r = client.get("/api/v1/levels/1/progress", headers=world["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["position"] == 1
    assert body["totals"]["items"] == 3          # 2 vocab + 1 grammar
    assert body["totals"]["learned"] == 1
    assert body["totals"]["not_started"] == 2
    assert body["totals"]["familiar_plus"] == 1

    casa = next(i for i in body["items"] if i["term"] == "casa")
    assert casa["srs_stage_name"] == "Familiar 1"
    assert casa["practice_stages"] == {"sentences": 0, "listening": 0, "speaking": 0}
    assert casa["practice_labels"]["speaking"] == "Not started"


def test_level_progress_counts_perfect_items(client, db, world):
    uid = _user_id(db)
    p = _learn(db, uid, ItemType.vocabulary, world["casa"].id, stage=9)
    p.perfect_at = dt.datetime.now(tz=dt.timezone.utc)
    db.commit()
    body = client.get("/api/v1/levels/1/progress", headers=world["headers"]).json()
    assert body["totals"]["perfect"] == 1
    assert body["totals"]["fluent"] == 1


def test_level_progress_is_gated_on_unlock(client, world):
    r = client.get("/api/v1/levels/2/progress", headers=world["headers"])
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "level_locked"


def test_level_progress_requires_auth(client, world):
    assert client.get("/api/v1/levels/1/progress").status_code == 401


def test_unknown_level_is_404(client, world):
    r = client.get("/api/v1/levels/97/progress", headers=world["headers"])
    assert r.status_code == 404
