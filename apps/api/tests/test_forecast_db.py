"""Integration test for GET /me/reviews/forecast (slice 47)."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.progress import UserItemProgress


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
    items = []
    for i in range(4):
        v = VocabularyItem(language_id=lang.id, module_id=module.id, status=ContentStatus.published,
                           term=f"w{i}", normalized_term=f"w{i}", primary_translation="x",
                           part_of_speech="noun", difficulty_rank=1)
        db.add(v); db.flush(); items.append(v)
    r = client.post("/api/v1/auth/signup",
                    json={"email": "fc@example.com", "name": "F", "password": "supersecret1"})
    from app.models.identity import User
    uid = db.execute(select(User).where(User.email == "fc@example.com")).scalar_one().id
    db.commit()
    return {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"}, "uid": uid, "items": items}


def _due(db, uid, item_id, when, stage=3):
    db.add(UserItemProgress(user_id=uid, item_type=ItemType.vocabulary, item_id=item_id,
                            srs_stage=stage, next_review_at=when))


def test_forecast_shape_labels_and_counts(client, db, world):
    now = dt.datetime.now(tz=dt.timezone.utc)
    it = world["items"]
    _due(db, world["uid"], it[0].id, now + dt.timedelta(hours=2))    # today
    _due(db, world["uid"], it[1].id, now + dt.timedelta(days=1))     # tomorrow
    _due(db, world["uid"], it[2].id, now + dt.timedelta(hours=3))    # today + within 24h
    _due(db, world["uid"], it[3].id, now - dt.timedelta(hours=1))    # overdue → excluded
    db.commit()

    body = client.get("/api/v1/me/reviews/forecast", headers=world["hdr"]).json()
    assert len(body["days"]) == 7
    assert body["days"][0]["label"] == "today"
    assert body["days"][1]["label"] in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    assert len(body["days"][0]["hours"]) == 24
    # today has 2 upcoming, tomorrow 1, overdue excluded → 3 total across the week
    assert sum(d["count"] for d in body["days"]) == 3
    assert body["days"][0]["count"] == 2
    # next 24h contains the two due today (2h, 3h out); tomorrow's is >24h? no, +1 day = 24h boundary excluded
    assert len(body["next_24h"]) == 24
    assert sum(b["count"] for b in body["next_24h"]) == 2


def test_forecast_empty_for_new_user(client, db, world):
    body = client.get("/api/v1/me/reviews/forecast", headers=world["hdr"]).json()
    assert sum(d["count"] for d in body["days"]) == 0
    assert len(body["days"]) == 7 and len(body["next_24h"]) == 24


def test_forecast_requires_auth(client, db, world):
    assert client.get("/api/v1/me/reviews/forecast").status_code in (401, 403)
