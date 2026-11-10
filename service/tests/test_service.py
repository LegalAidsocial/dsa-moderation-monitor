from pathlib import Path

from fastapi.testclient import TestClient

from service.main import app

client = TestClient(app)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_text_hit():
    resp = client.post("/text", json={"text": "sieg heil"})
    assert resp.status_code == 200
    assert "sieg heil" in resp.json()["hits"]


def test_text_clean():
    resp = client.post("/text", json={"text": "have a nice day"})
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


def test_image_banned():
    with open(FIXTURES / "banned_sample.jpg", "rb") as f:
        resp = client.post("/image", files={"file": ("test.jpg", f, "image/jpeg")})
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "banned"


def test_image_needs_context():
    with open(FIXTURES / "needs_context_sample.jpg", "rb") as f:
        resp = client.post("/image", files={"file": ("test.jpg", f, "image/jpeg")})
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "needs_context"
