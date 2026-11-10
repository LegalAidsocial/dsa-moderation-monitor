# service (SCRUM-54)

Small FastAPI service wrapping `codefinder` (text) and the ONNX symbol
classifier trained in symbol-detector (image). JSON logs to stdout,
settings from env vars.

```bash
uv sync --package service
uv run --package service uvicorn service.main:app --reload
```

- `POST /text` - body `{"text": "..."}` -> `{"hits": ["code1", ...]}`
- `POST /image` - multipart file upload -> `{"symbol", "confidence", "verdict"}`

Env vars: `HOST`, `PORT`, `CODEFINDER_CONFIG`, `MODEL_PATH`, `NAMES_PATH`.
