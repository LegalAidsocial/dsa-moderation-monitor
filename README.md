# dsa-moderation-monitor

Combined moderation service for Task 4 (banned symbols in text and images)
and Task 5 (platform moderation monitor).

- `codefinder/` - text detector package (SCRUM-49/50).
- `service/` - FastAPI service wrapping `codefinder` plus the ONNX image
  classifier trained in symbol-detector (SCRUM-54). See `service/README.md`.
- `monitor/` - DSA Transparency Database monitor: monthly totals, the
  six-platform/27-country scale-up, and alerts (SCRUM-59-63). See
  `monitor/README.md`.

This is a uv workspace; run everything from the repo root with
`--package <name>`, e.g. `uv sync --package service`.
