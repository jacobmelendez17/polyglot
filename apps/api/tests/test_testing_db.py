"""Testing maps end-to-end: start (no answer leak), grade, XP idempotency, admin."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.seed import seed
from app.db.seed_tests import seed_tests
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import User
from app.models.platform import AdminAuditLog
from app.models.progress import XpEvent
from app.models.testing import TestQuestion


@pytest.fixture()
def client(db):
    seed(db)
    seed_tests(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="test@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "T", "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def test_testing_requires_auth(client):
    assert client.post("/api/v1/tests/cefr/start").status_code == 401


def test_unknown_map_is_404(client):
    hdr, _ = _signup(client)
    assert client.post("/api/v1/tests/dragons/start", headers=hdr).status_code == 404


def test_start_returns_questions_without_the_answer(client):
    hdr, _ = _signup(client, "cefr@example.com")
    r = client.post("/api/v1/tests/cefr/start", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["map"] == "cefr" and len(body["questions"]) >= 1
    q = body["questions"][0]
    assert "correct_index" not in q          # never leak the answer
    assert len(q["options"]) >= 2
    assert all("text" in o for o in q["options"])


def test_answering_correctly_awards_xp_once(client, db):
    hdr, uid = _signup(client, "score@example.com")
    start = client.post("/api/v1/tests/app/start", headers=hdr).json()
    aid = start["attempt_id"]
    q = start["questions"][0]
    # find the true correct index from the DB (the client wouldn't know it)
    correct = db.get(TestQuestion, uuid.UUID(q["id"])).correct_index

    key = str(uuid.uuid4())
    body = {"question_id": q["id"], "chosen_index": correct, "idempotency_key": key}
    r1 = client.post(f"/api/v1/tests/attempts/{aid}/answer", headers=hdr, json=body).json()
    assert r1["correct"] is True and r1["xp_awarded"] == 20
    assert r1["correct_index"] == correct

    # retry same key → idempotent, no extra XP
    r2 = client.post(f"/api/v1/tests/attempts/{aid}/answer", headers=hdr, json=body).json()
    assert r2["already_answered"] is True and r2["xp_awarded"] == 0
    total_xp = db.execute(select(func.coalesce(func.sum(XpEvent.amount), 0))).scalar_one()
    assert total_xp == 20


def test_wrong_answer_scores_zero_xp(client, db):
    hdr, _ = _signup(client, "wrong@example.com")
    start = client.post("/api/v1/tests/app/start", headers=hdr).json()
    q = start["questions"][0]
    correct = db.get(TestQuestion, uuid.UUID(q["id"])).correct_index
    wrong = (correct + 1) % len(q["options"])
    r = client.post(f"/api/v1/tests/attempts/{start['attempt_id']}/answer", headers=hdr,
                    json={"question_id": q["id"], "chosen_index": wrong,
                          "idempotency_key": str(uuid.uuid4())}).json()
    assert r["correct"] is False and r["xp_awarded"] == 0


def test_complete_reports_score(client, db):
    hdr, _ = _signup(client, "complete@example.com")
    start = client.post("/api/v1/tests/cefr/start", headers=hdr).json()
    aid = start["attempt_id"]
    for q in start["questions"]:
        correct = db.get(TestQuestion, uuid.UUID(q["id"])).correct_index
        client.post(f"/api/v1/tests/attempts/{aid}/answer", headers=hdr,
                    json={"question_id": q["id"], "chosen_index": correct,
                          "idempotency_key": str(uuid.uuid4())})
    done = client.post(f"/api/v1/tests/attempts/{aid}/complete", headers=hdr).json()
    assert done["score"] == done["total"] == len(start["questions"])
    assert done["percentage"] == 100


def test_cannot_answer_a_foreign_attempt(client, db):
    hdr_a, _ = _signup(client, "a@example.com")
    hdr_b, _ = _signup(client, "b@example.com")
    start = client.post("/api/v1/tests/cefr/start", headers=hdr_a).json()
    q = start["questions"][0]
    r = client.post(f"/api/v1/tests/attempts/{start['attempt_id']}/answer", headers=hdr_b,
                    json={"question_id": q["id"], "chosen_index": 0,
                          "idempotency_key": str(uuid.uuid4())})
    assert r.status_code == 404


def test_admin_authoring_is_gated_and_audited(client, db):
    hdr_user, _ = _signup(client, "plain@example.com")
    hdr_ed, ed_id = _signup(client, "ed@example.com")
    db.get(User, ed_id).role = UserRole.content_editor
    db.commit()

    payload = {"map": "life", "stem": "New scenario?",
               "options": ["a", "b", "c", "d"], "correct_index": 2, "band": "cafe"}
    # normal user forbidden
    assert client.post("/api/v1/admin/tests/questions", headers=hdr_user,
                       json=payload).status_code == 403
    created = client.post("/api/v1/admin/tests/questions", headers=hdr_ed, json=payload).json()
    qid = created["id"]
    assert created["status"] == "draft"
    # publish
    client.patch(f"/api/v1/admin/tests/questions/{qid}/status", headers=hdr_ed,
                 json={"status": "published"})
    q = db.get(TestQuestion, uuid.UUID(qid))
    assert q.status == "published" and q.correct_index == 2

    logs = db.execute(select(func.count()).select_from(AdminAuditLog)
                      .where(AdminAuditLog.target_table == "test_questions")).scalar_one()
    assert logs >= 2
