"""Integration tests for the deck catalog + custom decks (slice 43)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VerbMeta, VocabularyItem
from app.models.enums import ItemType
from app.models.progress import UserItemProgress


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def user_tok(client, db):
    seed(db)
    r = client.post("/api/v1/auth/signup",
                    json={"email": "deckfan@example.com", "name": "D", "password": "supersecret1"})
    return r.json()["access_token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _uid(db, email):
    from app.models.identity import User
    return db.execute(select(User).where(User.email == email)).scalar_one().id


def _add_familiar_verb(db, lang, module, term, *, irregular):
    v = VocabularyItem(
        language_id=lang.id, module_id=module.id, status=ContentStatus.published,
        term=term, normalized_term=term, primary_translation="x",
        part_of_speech="verb", difficulty_rank=1,
    )
    db.add(v); db.flush()
    db.add(VerbMeta(vocabulary_item_id=v.id, conjugation_class="ar", is_regular=not irregular,
                    conjugations={}))
    db.add(UserItemProgress(user_id=_uid(db, "deckfan@example.com"), item_type=ItemType.vocabulary,
                            item_id=v.id, srs_stage=5))
    db.flush()


def test_catalog_lists_always_on_and_locked_decks(client, db, user_tok):
    catalog = client.get("/api/v1/me/decks/catalog/all", headers=_hdr(user_tok)).json()
    by_id = {d["id"]: d for d in catalog}
    # always-on
    assert by_id["vocabulary"]["unlocked"] is True
    # threshold-gated, no progress yet
    assert by_id["verbs"]["unlocked"] is False
    assert by_id["verbs"]["threshold"] == 20
    assert by_id["irregular_verbs"]["unlocked"] is False


def test_irregular_verb_deck_unlocks_at_five(client, db, user_tok):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=lang.id, position=1, title="L1", status=ContentStatus.published)
    db.add(module); db.flush()
    for i in range(5):
        _add_familiar_verb(db, lang, module, f"irr{i}", irregular=True)
    db.commit()

    by_id = {d["id"]: d for d in client.get("/api/v1/me/decks/catalog/all", headers=_hdr(user_tok)).json()}
    assert by_id["irregular_verbs"]["unlocked"] is True
    assert by_id["irregular_verbs"]["have"] == 5
    # verbs deck (needs 20) still locked but shows progress from these 5
    assert by_id["verbs"]["unlocked"] is False
    assert by_id["verbs"]["have"] == 5
    assert by_id["verbs"]["need"] == 15


def test_create_list_delete_custom_deck(client, db, user_tok):
    hdr = _hdr(user_tok)
    r = client.post("/api/v1/me/decks/catalog/custom", headers=hdr,
                    json={"name": "kitchen words", "description": "cooking vocab"})
    assert r.status_code == 201
    deck_id = r.json()["id"]
    assert deck_id.startswith("custom:") and r.json()["custom"] is True

    catalog = client.get("/api/v1/me/decks/catalog/all", headers=hdr).json()
    assert any(d["id"] == deck_id and d["title"] == "kitchen words" for d in catalog)

    d = client.request("DELETE", f"/api/v1/me/decks/catalog/custom/{deck_id}", headers=hdr)
    assert d.status_code == 200 and d.json()["deleted"] is True
    catalog2 = client.get("/api/v1/me/decks/catalog/all", headers=hdr).json()
    assert not any(x["id"] == deck_id for x in catalog2)


def test_custom_deck_requires_name(client, db, user_tok):
    r = client.post("/api/v1/me/decks/catalog/custom", headers=_hdr(user_tok),
                    json={"name": "   "})
    assert r.status_code == 422


def test_cannot_delete_another_users_deck(client, db, user_tok):
    other = client.post("/api/v1/auth/signup",
                        json={"email": "other@example.com", "name": "O", "password": "supersecret1"}).json()
    r = client.post("/api/v1/me/decks/catalog/custom", headers={"Authorization": f"Bearer {other['access_token']}"},
                    json={"name": "theirs"})
    other_deck = r.json()["id"]
    d = client.request("DELETE", f"/api/v1/me/decks/catalog/custom/{other_deck}", headers=_hdr(user_tok))
    assert d.status_code == 404


def test_catalog_requires_auth(client, db):
    assert client.get("/api/v1/me/decks/catalog/all").status_code in (401, 403)
