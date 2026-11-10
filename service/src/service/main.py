"""SCRUM-54: small FastAPI service wrapping codefinder (text) and the ONNX
image classifier (image). POST /text and POST /image return hits as JSON.

Settings from env vars:
    HOST, PORT               - uvicorn bind address (default 0.0.0.0:8000)
    CODEFINDER_CONFIG        - path to codes.csv (codefinder's own default if unset)
    MODEL_PATH, NAMES_PATH   - ONNX model + class names (service/models/ default)

Run: uv run uvicorn service.main:app --host 0.0.0.0 --port 8000
"""

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

from codefinder import find_codes
from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import JSONResponse

from service.image_model import ImageClassifier

logger = logging.getLogger("service")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False

app = FastAPI(title="DSA moderation service")
_classifier: ImageClassifier | None = None


def get_classifier() -> ImageClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ImageClassifier()
    return _classifier


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    logger.info(
        json.dumps(
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000, 1),
            }
        )
    )
    return response


@app.post("/text")
async def check_text(body: dict) -> JSONResponse:
    text = body.get("text", "")
    hits = find_codes(text, config_path=os.environ.get("CODEFINDER_CONFIG"))
    return JSONResponse({"hits": hits})


@app.post("/image")
async def check_image(file: UploadFile) -> JSONResponse:
    suffix = Path(file.filename or "upload").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        result = get_classifier().classify(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return JSONResponse(result)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "service.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
