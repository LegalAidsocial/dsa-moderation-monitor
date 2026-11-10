"""Load and run the trained symbol classifier (ONNX, CPU) on an image.

Adapted from symbol-detector's classify_image.py (SCRUM-53) so the service
doesn't depend on checking out that repo - the model files are copied in
under models/ instead.
"""

import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.environ.get("MODEL_PATH", _SERVICE_ROOT / "models" / "symbol_classifier.onnx"))
NAMES_PATH = Path(os.environ.get("NAMES_PATH", _SERVICE_ROOT / "models" / "symbol_classifier.names.json"))
IMG_SIZE = 224

NEEDS_CONTEXT_CLASSES = {"swastika_religious"}
CLEAN_CLASSES = {"none"}


def load_names(names_path: Path = NAMES_PATH) -> dict[int, str]:
    raw = json.loads(names_path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


def preprocess(image_path: Path, img_size: int = IMG_SIZE) -> np.ndarray:
    img = Image.open(image_path).convert("RGB").resize((img_size, img_size))
    arr = np.asarray(img, dtype=np.float32) / 255.0
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

    def __init__(self, model_path: Path = MODEL_PATH, names_path: Path = NAMES_PATH) -> None:
        self.names = load_names(names_path)
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def classify(self, image_path: Path) -> dict[str, object]:
        x = preprocess(image_path)
        (probs,) = self.session.run(None, {self.input_name: x})
        probs = probs[0]
        top_idx = int(np.argmax(probs))
        symbol_class = self.names[top_idx]
        return {
            "symbol": symbol_class,
            "confidence": float(probs[top_idx]),
            "verdict": verdict_for(symbol_class),
        }
