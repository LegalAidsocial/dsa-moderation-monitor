"""OCR for images: read the text with Tesseract (German), then run the text detector.

Settings come from environment variables:
  OCR_LANG        Tesseract language packs, default "deu" ("deu+eng" also works)
  TESSERACT_CMD   full path to tesseract(.exe) if it is not on PATH
  OCR_TIMEOUT     seconds allowed for one OCR pass, default 10
"""

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pytesseract
from PIL import Image, ImageOps

from codefinder.finder import find_codes

MIN_TEXT_CHARS = 3  # fewer letters/digits than this: try the inverted image as well
MAX_SIDE = 3000  # larger images are scaled down
MIN_SIDE = 1000  # smaller images are scaled up; Tesseract reads small text badly

ImageSource = str | Path | bytes | BinaryIO


@dataclass(frozen=True)
class OcrResult:
    """The text found in an image and the codes found in that text."""

    text: str
    codes: list[str]
    error: str | None = None


def _configure() -> None:
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def _open(source: ImageSource) -> Image.Image:
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    image = Image.open(source)
    image.load()
    return ImageOps.exif_transpose(image).convert("L")


def _prepare(image: Image.Image) -> Image.Image:
    """Grayscale, sensible size, stretched contrast."""
    longest = max(image.size)
    if longest < MIN_SIDE:
        scale = MIN_SIDE / longest
    elif longest > MAX_SIDE:
        scale = MAX_SIDE / longest
    else:
        scale = 1.0
    if scale != 1.0:
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
        )
    return ImageOps.autocontrast(image)


def _read(image: Image.Image) -> str:
    timeout = float(os.environ.get("OCR_TIMEOUT", "10"))
    lang = os.environ.get("OCR_LANG", "deu")
    # psm 11 = sparse text: finds text scattered over a picture, as in memes
    return pytesseract.image_to_string(
        image, lang=lang, config="--psm 11", timeout=timeout
    )


def _useful(text: str) -> bool:
    return sum(c.isalnum() for c in text) >= MIN_TEXT_CHARS


def ocr_text(source: ImageSource) -> str:
    """Return the text Tesseract reads in the image (empty string if none)."""
    _configure()
    image = _prepare(_open(source))
    text = _read(image)
    if not _useful(text):  # light text on a dark background is often missed
        text = _read(ImageOps.invert(image))
    return " ".join(text.split())


def scan_image(source: ImageSource) -> OcrResult:
    """OCR the image and run the text through find_codes (normalize runs inside it)."""
    try:
        text = ocr_text(source)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract is not installed or not on PATH. Install it with the German language "
            "pack, or set TESSERACT_CMD to its full path."
        ) from e
    except (OSError, ValueError, RuntimeError, Image.DecompressionBombError) as e:
        # unreadable image, Tesseract timeout or failure, decompression bomb
        return OcrResult(text="", codes=[], error=f"{type(e).__name__}: {e}")
    return OcrResult(text=text, codes=find_codes(text))


def ocr_hits(result: OcrResult) -> list[dict[str, str]]:
    """Hits in a shape that can be appended to an /image response."""
    return [{"code": code, "source": "ocr"} for code in result.codes]
