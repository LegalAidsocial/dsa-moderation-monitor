# monitor

Turns daily DSA Transparency Database files (TikTok) into monthly totals.
Only totals are stored, never single decisions.

## Run
```bash
uv sync
cp .env.example .env     # then export the variables, or set them in your shell
uv run monitor build
```
Put the daily zip files in `data/`. Results: `out/monthly_totals.parquet` and `out/monthly_totals.csv`
(columns: month, platform, country, decision_ground, category, automated_detection,
automated_decision, action, decisions).

## Test
```bash
uv run pytest
uv run ruff format . && uv run ruff check .
```

## Notes
- Each zip is unzipped to a temp folder, aggregated by DuckDB, then deleted. Finished zips are skipped on re-runs.
- `action` is one value per decision, chosen by priority: removal, hiding, reduced_reach, account_action, other.
- Licence of the data: write it down here (see the Transparency Database terms).
