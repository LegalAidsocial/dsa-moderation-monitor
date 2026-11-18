from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
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


def test_gif_checks_every_frame_not_just_the_first(tmp_path: Path):
    """A sticker/GIF comment can be clean on frame 1 and banned on a later
    frame - the classifier must not stop at frame 0 (confirmed this was the
    bug before: PIL's Image.open().convert("RGB") only reads the first
    frame of an animated image)."""
    clean = Image.new("RGB", (64, 64), color=(200, 200, 200))
    banned = Image.open(FIXTURES / "banned_sample.jpg").convert("RGB").resize((64, 64))
    gif_path = tmp_path / "sticker.gif"
    clean.save(
        gif_path, save_all=True, append_images=[clean, clean, banned, clean], loop=0
    )

    with open(gif_path, "rb") as f:
        resp = client.post("/image", files={"file": ("sticker.gif", f, "image/gif")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "banned"
    # PIL may de-duplicate identical consecutive frames on save, so don't
    # assert the exact count we appended - just that more than frame 0 was
    # actually looked at (the thing the old, first-frame-only code got wrong).
    assert body["frames_checked"] > 1


def test_static_image_response_unchanged_shape():
    """Single-frame images (the vast majority of the dataset) must not grow
    a frames_checked key - keeps the existing API contract stable."""
    with open(FIXTURES / "banned_sample.jpg", "rb") as f:
        resp = client.post("/image", files={"file": ("test.jpg", f, "image/jpeg")})
    assert "frames_checked" not in resp.json()
