from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_ok() -> None:
    client = TestClient(create_app())
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_healthz_leaks_nothing() -> None:
    """Security checklist: health endpoint exposes no version/config detail."""
    client = TestClient(create_app())
    body = client.get("/healthz").json()
    assert set(body.keys()) == {"status"}
