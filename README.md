# dsa-moderation-monitor

Combined moderation service for Task 4 (banned symbols in text and images)
and Task 5 (platform moderation monitor).

- `codefinder/` - text detector package (SCRUM-49/50).
- `service/` - FastAPI service wrapping `codefinder` plus the ONNX image
  classifier trained in symbol-detector (SCRUM-54). See `service/README.md`.
- `monitor/` - DSA Transparency Database monitor: monthly totals, the
  six-platform/27-country scale-up, and alerts (SCRUM-59-63). See
  `monitor/README.md`.

This is a uv workspace (Python 3.12). Run uv commands from the repo root.

## What it does

`POST /text` with `{"text": "..."}` returns `{"hits": [...]}`: the banned codes found in the text.
`POST /image` with an image file returns the classifier result for that image.
Rules for the text detector live in `codefinder/config/codes.csv`, not in the code.

## Run it

With Docker (from a fresh checkout):

```bash
docker compose up --build
```

The service is then at http://localhost:8000 (API docs at `/docs`). Try it:

```bash
curl -X POST localhost:8000/text -H "Content-Type: application/json" -d '{"text":"hello"}'
curl -F file=@service/tests/fixtures/banned_sample.jpg localhost:8000/image
```

Without Docker:

```bash
uv sync --package service
uv run --package service python -m service.main
```

OCR needs Tesseract with the German language pack installed (`tesseract --list-langs` must list `deu`).
The Docker image installs it.

## Settings

All settings are environment variables and are listed in `.env.example`
(`HOST`, `PORT`, `CODEFINDER_CONFIG`, `MODEL_PATH`, `NAMES_PATH`, `OCR_LANG`, `OCR_TIMEOUT`, `TESSERACT_CMD`).
No passwords, keys or cookies are stored in Git.

## Test and check

```bash
cd codefinder && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd ../service && uv run pytest
```

The OCR tests are skipped when Tesseract or its German pack is missing.

## Logs

The service prints one JSON line per request to stdout.
