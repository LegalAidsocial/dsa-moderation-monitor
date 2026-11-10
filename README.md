# dsa-moderation-monitor

Combined moderation service for Task 4 (banned symbols in text and images).

- `codefinder/` - text detector package (SCRUM-49/50).
- `service/` - FastAPI service wrapping `codefinder` plus the ONNX image
  classifier trained in symbol-detector (SCRUM-54). See `service/README.md`.

This is a uv workspace; run everything from the repo root with
`--package <name>`, e.g. `uv sync --package service`.
