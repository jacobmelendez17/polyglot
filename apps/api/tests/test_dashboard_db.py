"""Dashboard layout + guided tour endpoints: auth, persistence, per-user scoping."""
import pytest
from fastapi.testclient import TestClient

from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="learner@example.com") -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "Learner", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def learner(client, db):
    seed(db)
    db.commit()
    return _signup(client)


# --- authorization --------------------------------------------------------

def test_dashboard_requires_auth(client):
    assert client.get("/api/v1/me/dashboard").status_code == 401
    assert client.put("/api/v1/me/dashboard", json={"widgets": []}).status_code == 401


def test_tours_require_auth(client):
    assert client.get("/api/v1/me/tours/dashboard").status_code == 401


# --- layout ---------------------------------------------------------------

def test_new_user_gets_the_default_layout(client, learner):
    body = client.get("/api/v1/me/dashboard", headers=learner).json()
    keys = [w["key"] for w in body["layout"]["widgets"]]
    assert "welcome" in keys and "progression" in keys
    assert body["grid_columns"] == 6
    assert len(body["catalog"]) >= len(keys)


def test_catalog_marks_which_widgets_are_not_shown_yet(client, learner):
    body = client.get("/api/v1/me/dashboard", headers=learner).json()
    shown = {w["key"] for w in body["layout"]["widgets"]}
    optional = [c for c in body["catalog"] if c["key"] not in shown]
    assert optional, "there should be something available to add"


def test_saving_a_layout_persists_it(client, learner):
    r = client.put("/api/v1/me/dashboard", headers=learner, json={
        "widgets": [{"key": "xp", "span": 2}, {"key": "welcome", "span": 6}],
    })
    assert r.status_code == 200
    assert [w["key"] for w in r.json()["layout"]["widgets"]] == ["xp", "welcome"]

    again = client.get("/api/v1/me/dashboard", headers=learner).json()
    assert [w["key"] for w in again["layout"]["widgets"]] == ["xp", "welcome"]


def test_the_response_is_what_was_stored_not_what_was_sent(client, learner):
    """Unknown widgets are dropped server-side, and the PUT reflects that so the
    client's next render matches the database."""
    r = client.put("/api/v1/me/dashboard", headers=learner, json={
        "widgets": [{"key": "xp"}, {"key": "definitely_not_a_widget"}],
    })
    assert [w["key"] for w in r.json()["layout"]["widgets"]] == ["xp"]


def test_spans_are_clamped_on_write(client, learner):
    r = client.put("/api/v1/me/dashboard", headers=learner,
                   json={"widgets": [{"key": "xp", "span": 6}]})
    assert r.json()["layout"]["widgets"][0]["span"] <= 2   # xp maxes at 2


def test_out_of_range_spans_are_rejected_by_validation(client, learner):
    r = client.put("/api/v1/me/dashboard", headers=learner,
                   json={"widgets": [{"key": "xp", "span": 999}]})
    assert r.status_code == 422


def test_an_absurd_number_of_widgets_is_rejected(client, learner):
    r = client.put("/api/v1/me/dashboard", headers=learner,
                   json={"widgets": [{"key": "xp"}] * 500})
    assert r.status_code == 422


def test_an_empty_layout_is_allowed(client, learner):
    r = client.put("/api/v1/me/dashboard", headers=learner, json={"widgets": []})
    assert r.status_code == 200
    assert r.json()["layout"]["widgets"] == []


def test_reset_restores_the_defaults(client, learner):
    client.put("/api/v1/me/dashboard", headers=learner, json={"widgets": []})
    r = client.post("/api/v1/me/dashboard/reset", headers=learner)
    assert r.status_code == 200
    assert len(r.json()["layout"]["widgets"]) > 0


def test_layouts_are_per_user(client, db, learner):
    client.put("/api/v1/me/dashboard", headers=learner,
               json={"widgets": [{"key": "xp"}]})
    other = _signup(client, "other@example.com")

    mine = client.get("/api/v1/me/dashboard", headers=learner).json()
    theirs = client.get("/api/v1/me/dashboard", headers=other).json()
    assert [w["key"] for w in mine["layout"]["widgets"]] == ["xp"]
    assert len(theirs["layout"]["widgets"]) > 1      # untouched defaults


# --- tours ----------------------------------------------------------------

def test_a_new_user_has_not_seen_the_tour(client, learner):
    state = client.get("/api/v1/me/tours/dashboard", headers=learner).json()
    assert state["completed"] is False
    assert state["step_index"] == 0


def test_unknown_tours_are_404(client, learner):
    assert client.get("/api/v1/me/tours/nonsense", headers=learner).status_code == 404


def test_malformed_tour_keys_fail_validation(client, learner):
    assert client.get("/api/v1/me/tours/NOT-A-KEY", headers=learner).status_code == 422


def test_step_progress_is_remembered_so_a_refresh_resumes(client, learner):
    client.post("/api/v1/me/tours/dashboard/step", headers=learner,
                json={"step_index": 3})
    state = client.get("/api/v1/me/tours/dashboard", headers=learner).json()
    assert state["step_index"] == 3


def test_a_stale_tab_cannot_drag_the_tour_backwards(client, learner):
    client.post("/api/v1/me/tours/dashboard/step", headers=learner,
                json={"step_index": 4})
    client.post("/api/v1/me/tours/dashboard/step", headers=learner,
                json={"step_index": 1})
    state = client.get("/api/v1/me/tours/dashboard", headers=learner).json()
    assert state["step_index"] == 4


def test_out_of_range_steps_are_rejected(client, learner):
    r = client.post("/api/v1/me/tours/dashboard/step", headers=learner,
                    json={"step_index": 999})
    assert r.status_code == 422


def test_completing_the_tour_records_it(client, learner):
    r = client.post("/api/v1/me/tours/dashboard/complete", headers=learner,
                    json={"skipped": False})
    assert r.json()["completed"] is True
    assert r.json()["skipped"] is False
    assert r.json()["completed_at"] is not None


def test_skipping_is_recorded_separately_from_finishing(client, learner):
    r = client.post("/api/v1/me/tours/dashboard/complete", headers=learner,
                    json={"skipped": True})
    assert r.json()["completed"] is True
    assert r.json()["skipped"] is True


def test_completing_twice_keeps_the_first_timestamp(client, learner):
    first = client.post("/api/v1/me/tours/dashboard/complete", headers=learner,
                        json={"skipped": True}).json()
    second = client.post("/api/v1/me/tours/dashboard/complete", headers=learner,
                         json={"skipped": False}).json()
    assert second["completed_at"] == first["completed_at"]
    assert second["skipped"] is True


def test_restart_clears_completion_for_an_explicit_replay(client, learner):
    client.post("/api/v1/me/tours/dashboard/complete", headers=learner,
                json={"skipped": True})
    r = client.post("/api/v1/me/tours/dashboard/restart", headers=learner)
    assert r.json()["completed"] is False
    assert r.json()["step_index"] == 0


def test_tour_state_is_per_user(client, learner):
    client.post("/api/v1/me/tours/dashboard/complete", headers=learner,
                json={"skipped": False})
    other = _signup(client, "other2@example.com")
    assert client.get("/api/v1/me/tours/dashboard",
                      headers=other).json()["completed"] is False
