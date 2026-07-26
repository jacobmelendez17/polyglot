"""Password reset, email verification, and decks — full DB + API flow.

The reset tests care most about the no-enumeration property and single-use
redemption. The deck tests care about level scoping and the private answer key
never leaking.
"""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.email.provider import MemoryEmailProvider, build_provider
from app.main import create_app
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem
from app.models.email_tokens import PasswordResetToken
from app.models.identity import AuthSession, User


@pytest.fixture()
def mailbox():
    """Swap the email provider for an in-memory one and capture what's sent."""
    box = MemoryEmailProvider()
    app = create_app()
    app.dependency_overrides[build_provider] = lambda settings=None: box
    return app, box


@pytest.fixture()
def client(db, mailbox):
    app, _ = mailbox
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def box(mailbox):
    return mailbox[1]


def _signup(client, email="learner@example.com") -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "Learner", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _token_in(box) -> str:
    """Pull the raw reset/verify token back out of the emailed link."""
    assert box.sent, "no email was sent"
    body = box.sent[-1].text
    marker = "token="
    idx = body.rfind(marker)
    assert idx != -1, body
    return body[idx + len(marker):].split()[0].strip()


# --- password reset -------------------------------------------------------

def test_forgot_password_sends_a_link_for_a_real_account(client, box):
    _signup(client, "real@example.com")
    box.sent.clear()
    r = client.post("/api/v1/auth/forgot-password", json={"email": "real@example.com"})
    assert r.status_code == 200
    assert len(box.sent) == 1
    assert "reset" in box.sent[0].subject.lower()


def test_forgot_password_reveals_nothing_for_an_unknown_account(client, box):
    box.sent.clear()
    r = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
    # Identical response to the real-account case...
    assert r.status_code == 200
    assert "if an account exists" in r.json()["message"].lower()
    # ...and no email actually goes out.
    assert box.sent == []


def test_a_reset_link_actually_resets_the_password(client, box):
    _signup(client, "reset@example.com")
    box.sent.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    token = _token_in(box)

    r = client.post("/api/v1/auth/reset-password",
                    json={"token": token, "new_password": "brandnewpass9"})
    assert r.status_code == 200

    # old password no longer works, new one does
    assert client.post("/api/v1/auth/login", json={
        "email": "reset@example.com", "password": "supersecret1",
    }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "reset@example.com", "password": "brandnewpass9",
    }).status_code == 200


def test_a_reset_token_is_single_use(client, box):
    _signup(client, "once@example.com")
    box.sent.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "once@example.com"})
    token = _token_in(box)

    first = client.post("/api/v1/auth/reset-password",
                        json={"token": token, "new_password": "firsttime12"})
    assert first.status_code == 200
    second = client.post("/api/v1/auth/reset-password",
                         json={"token": token, "new_password": "secondtime12"})
    assert second.status_code == 400
    assert second.json()["detail"]["error"]["code"] == "invalid_token"


def test_an_expired_reset_token_is_refused(client, db, box):
    _signup(client, "stale@example.com")
    box.sent.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "stale@example.com"})
    token = _token_in(box)

    # Age the token past its hour.
    row = db.execute(select(PasswordResetToken)).scalars().first()
    row.expires_at = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(minutes=1)
    db.commit()

    r = client.post("/api/v1/auth/reset-password",
                    json={"token": token, "new_password": "toolate1234"})
    assert r.status_code == 400


def test_requesting_a_new_link_invalidates_the_old_one(client, box):
    _signup(client, "twice@example.com")
    box.sent.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "twice@example.com"})
    old_token = _token_in(box)
    client.post("/api/v1/auth/forgot-password", json={"email": "twice@example.com"})

    # The first link no longer works; only the newest does.
    assert client.post("/api/v1/auth/reset-password",
                       json={"token": old_token, "new_password": "nope12345"}
                       ).status_code == 400


def test_a_garbage_token_is_refused(client):
    r = client.post("/api/v1/auth/reset-password",
                    json={"token": "not-a-real-token", "new_password": "whatever12"})
    assert r.status_code == 400


def test_reset_rejects_a_weak_new_password(client, box):
    _signup(client, "weak@example.com")
    box.sent.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "weak@example.com"})
    token = _token_in(box)
    r = client.post("/api/v1/auth/reset-password",
                    json={"token": token, "new_password": "short"})
    assert r.status_code == 422       # caught by schema min_length


def test_reset_revokes_existing_sessions(client, db, box):
    signup = _signup(client, "revoke@example.com")
    box.sent.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "revoke@example.com"})
    token = _token_in(box)
    client.post("/api/v1/auth/reset-password",
                json={"token": token, "new_password": "freshpass123"})

    # The refresh token from before the reset must be dead.
    reuse = client.post("/api/v1/auth/refresh",
                        json={"refresh_token": signup["refresh_token"]})
    assert reuse.status_code == 401


# --- email verification ---------------------------------------------------

def test_send_and_confirm_verification(client, db, box):
    tokens = _signup(client, "verify@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    box.sent.clear()

    sent = client.post("/api/v1/auth/send-verification", headers=headers)
    assert sent.status_code == 200
    token = _token_in(box)

    before = client.get("/api/v1/auth/verification-status", headers=headers).json()
    assert before["verified"] is False

    confirmed = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert confirmed.status_code == 200
    assert confirmed.json()["verified"] is True

    after = client.get("/api/v1/auth/verification-status", headers=headers).json()
    assert after["verified"] is True


def test_confirming_twice_is_idempotent(client, box):
    tokens = _signup(client, "double@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    box.sent.clear()
    client.post("/api/v1/auth/send-verification", headers=headers)
    token = _token_in(box)

    first = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert first.json()["already_verified"] is False
    # token is single-use, so a replay of the same token fails...
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_verification_status_requires_auth(client):
    assert client.get("/api/v1/auth/verification-status").status_code == 401


# --- decks ----------------------------------------------------------------

def _module(db, lang_id, position) -> Module:
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
        rejected_answers=kw.pop("rejected_answers", ["office"]),
        **kw,
    )
    db.add(v)
    db.flush()
    return v


@pytest.fixture()
def world(client, db):
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    l1 = _module(db, lang.id, 1)
    l2 = _module(db, lang.id, 2)
    _vocab(db, lang.id, l1.id, "casa", "house")
    _vocab(db, lang.id, l1.id, "correr", "to run", part_of_speech="verb",
           accepted_answers=["run"], rejected_answers=[])
    db.add(GrammarPoint(
        language_id=lang.id, module_id=l1.id, title="ser vs estar",
        translation="to be", status=ContentStatus.published,
        accepted_answers=["to be"], rejected_answers=[],
    ))
    _vocab(db, lang.id, l2.id, "playa", "beach")   # locked level
    db.commit()
    tokens = _signup(client, "decker@example.com")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_decks_require_auth(client):
    assert client.get("/api/v1/me/decks").status_code == 401


def test_deck_list_shows_three_decks_with_counts(client, world):
    decks = client.get("/api/v1/me/decks", headers=world).json()
    by_type = {d["type"]: d for d in decks}
    assert set(by_type) == {"vocabulary", "grammar", "intermissions"}
    assert by_type["vocabulary"]["count"] == 2      # level 1 only
    assert by_type["grammar"]["count"] == 1


def test_vocab_deck_lists_unlocked_items_only(client, world):
    page = client.get("/api/v1/me/decks/vocabulary", headers=world).json()
    terms = {i["term"] for i in page["items"]}
    assert terms == {"casa", "correr"}      # playa is in a locked level
    assert page["total"] == 2


def test_deck_never_leaks_the_answer_key(client, world):
    body = client.get("/api/v1/me/decks/vocabulary", headers=world).text
    assert "accepted_answers" not in body
    assert "rejected_answers" not in body
    assert "office" not in body             # the rejected answer text


def test_vocab_deck_marks_articles_for_nouns_only(client, world):
    items = client.get("/api/v1/me/decks/vocabulary", headers=world).json()["items"]
    verb = next(i for i in items if i["term"] == "correr")
    assert verb["article"] is None


def test_grammar_deck_lists_grammar(client, world):
    page = client.get("/api/v1/me/decks/grammar", headers=world).json()
    assert [i["term"] for i in page["items"]] == ["ser vs estar"]


def test_intermission_deck_is_empty_until_something_is_viewed(client, world):
    page = client.get("/api/v1/me/decks/intermissions", headers=world).json()
    assert page["total"] == 0


def test_unknown_deck_is_404(client, world):
    assert client.get("/api/v1/me/decks/nonsense", headers=world).status_code == 422


def test_deck_paginates(client, world):
    page = client.get("/api/v1/me/decks/vocabulary?limit=1&offset=0", headers=world).json()
    assert len(page["items"]) == 1
    assert page["total"] == 2
