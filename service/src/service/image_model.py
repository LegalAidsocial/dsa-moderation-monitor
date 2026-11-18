"""Load and run the trained symbol classifier (ONNX, CPU) on an image.

Adapted from symbol-detector's classify_image.py (SCRUM-53) so the service
doesn't depend on checking out that repo - the model files are copied in
under models/ instead.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(
    os.environ.get("MODEL_PATH", _SERVICE_ROOT / "models" / "symbol_classifier.onnx")
)
NAMES_PATH = Path(
    os.environ.get(
        "NAMES_PATH", _SERVICE_ROOT / "models" / "symbol_classifier.names.json"
    )
)
IMG_SIZE = 224
MAX_FRAMES = 8  # cap per animated image (GIF/animated WEBP/APNG) - evenly spaced sample

NEEDS_CONTEXT_CLASSES = {"swastika_religious"}
CLEAN_CLASSES = {"none"}
_VERDICT_SEVERITY = {"clean": 0, "needs_context": 1, "banned": 2}


def load_names(names_path: Path = NAMES_PATH) -> dict[int, str]:
    raw = json.loads(names_path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


def iter_frames(
    image_path: Path, max_frames: int = MAX_FRAMES
) -> Iterator[Image.Image]:
    """Yield RGB frames to check. A plain image yields itself once.

    An animated image (GIF, animated WEBP/APNG - anything PIL reports
    n_frames > 1 for) yields up to max_frames evenly spaced frames,
    always including the first and last - a banned symbol can appear on
    any single frame of a sticker/GIF, not just the first.
    """
    img = Image.open(image_path)
    n_frames = getattr(img, "n_frames", 1)
    if n_frames <= 1:
        yield img.convert("RGB")
        return
    if n_frames <= max_frames:
        indices: list[int] = list(range(n_frames))
    else:
        step = (n_frames - 1) / (max_frames - 1)
        indices = sorted({round(i * step) for i in range(max_frames)})
    for i in indices:
        img.seek(i)
        yield img.convert("RGB")


def preprocess(frame: Image.Image, img_size: int = IMG_SIZE) -> np.ndarray:
    arr = np.asarray(frame.resize((img_size, img_size)), dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)  # HWC -> CHW
    return np.expand_dims(arr, axis=0)  # add batch dim


def verdict_for(symbol_class: str) -> str:
    if symbol_class in CLEAN_CLASSES:
        return "clean"
    if symbol_class in NEEDS_CONTEXT_CLASSES:
        return "needs_context"
    return "banned"


class ImageClassifier:
    """Loads the ONNX session once; reused across requests."""

    def __init__(
        self, model_path: Path = MODEL_PATH, names_path: Path = NAMES_PATH
    ) -> None:
        self.names = load_names(names_path)
        self.session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def _classify_frame(self, frame: Image.Image) -> dict[str, object]:
        x = preprocess(frame)
        (probs,) = self.session.run(None, {self.input_name: x})
        probs = probs[0]
        top_idx = int(np.argmax(probs))
        symbol_class = self.names[top_idx]
        return {
            "symbol": symbol_class,
            "confidence": float(probs[top_idx]),
            "verdict": verdict_for(symbol_class),
        }

    def classify(self, image_path: Path) -> dict[str, object]:
        results = [self._classify_frame(frame) for frame in iter_frames(image_path)]
        if len(results) == 1:
            return results[0]
        worst = max(
            results,
            key=lambda r: (_VERDICT_SEVERITY[str(r["verdict"])], r["confidence"]),
        )
        return {**worst, "frames_checked": len(results)}
