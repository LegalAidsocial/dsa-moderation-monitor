"""OCR tests. They are skipped when Tesseract or its German language pack is missing."""

import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from codefinder.ocr import ocr_hits, ocr_text, scan_image

pytesseract = pytest.importorskip("pytesseract")

if shutil.which("tesseract") is None:
    pytest.skip("Tesseract is not installed", allow_module_level=True)
if "deu" not in pytesseract.get_languages():
    pytest.skip(
        "Tesseract German language pack (deu) is missing", allow_module_level=True
    )


def make_image(text: str, inverted: bool = False) -> Image.Image:
    """Render text on a plain image."""
    back, front = ("black", "white") if inverted else ("white", "black")
    image = Image.new("RGB", (1200, 260), back)
    ImageDraw.Draw(image).text(
        (40, 80), text, fill=front, font=ImageFont.load_default(size=64)
    )
    return image


def to_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_reads_plain_text() -> None:
    assert "berlin" in ocr_text(to_png(make_image("Hallo Berlin"))).lower()


def test_finds_code_in_image() -> None:
    result = scan_image(to_png(make_image("Deutschland erwache")))
    assert "deutschland erwache" in result.codes
    assert ocr_hits(result) == [{"code": "deutschland erwache", "source": "ocr"}]


def test_finds_code_in_light_text_on_dark_background() -> None:
    result = scan_image(to_png(make_image("Deutschland erwache", inverted=True)))
    assert "deutschland erwache" in result.codes


def test_harmless_text_has_no_hits() -> None:
    result = scan_image(to_png(make_image("Das kostet 88 Euro")))
    assert result.codes == []


def test_blank_image_gives_empty_result() -> None:
    result = scan_image(to_png(Image.new("RGB", (800, 300), "white")))
    assert result.text == "" and result.codes == []


def test_unreadable_file_returns_error_not_crash() -> None:
    result = scan_image(b"this is not an image")
    assert result.codes == [] and result.error is not None
