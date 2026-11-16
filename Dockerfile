# DSA moderation service: FastAPI wrapping codefinder (text, OCR) and the ONNX image classifier.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Tesseract with the German language pack, used by codefinder's OCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv>=0.11.19,<0.12"

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY codefinder ./codefinder
COPY service ./service
COPY monitor ./monitor
RUN uv sync --frozen --no-dev --package service

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=4)"]

CMD ["python", "-m", "service.main"]
