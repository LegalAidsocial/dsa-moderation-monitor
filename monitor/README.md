# monitor

Turns DSA Transparency Database data into monthly totals, for TikTok x
Germany specifically (SCRUM-59/60, verified against the website) and for
all six large platforms x all 27 EU countries (SCRUM-61). Only totals
are stored, never single decisions.

## Run
```bash
uv sync --package monitor
cp .env.example .env     # then export the variables, or set them in your shell
uv run --package monitor monitor build          # rebuild everything, last 12 months
uv run --package monitor monitor build --months 1   # just the current month, for a quick check
uv run --package monitor monitor update         # fetch the newest month and rebuild
uv run --package monitor monitor alerts         # flag sudden month-to-month changes
```

`build`/`update` fetch the published six-platform aggregates themselves
(see `fetch.py` - confirmed live against the real CloudFront host) into
`MONITOR_AGG_DIR`, then rebuild `out/platform_monthly.parquet`,
`out/scale_totals.{parquet,csv}` (CSV in the `monthly-template.csv`
shape) and `out/answers.md` (the six questions, answered).

The TikTok x Germany-only pipeline (`totals.py` -> `out/monthly_totals.csv`)
instead needs the **daily per-platform** zip files in `MONITOR_DATA_DIR` -
there's no documented stable URL for those yet, so download them by hand
from the Transparency Database's own download page (filter to TikTok) and
drop them in `data/`. `build`/`update` pick up whatever's there; an empty
`data/` just means that pipeline's output stays empty - not an error.

## Test
```bash
uv run --package monitor pytest monitor/tests
uv run --package monitor ruff format . && uv run --package monitor ruff check .
```

## Notes
- Each zip is unzipped to a temp folder, aggregated by DuckDB, then deleted. Finished zips are skipped on re-runs.
- `action` is one value per decision, chosen by priority: removal, hiding, reduced_reach, account_action, other.
- `monitor alerts` excludes the current calendar month from all comparisons - verified live that comparing a finished month to the still-in-progress current one always looks like an 80-90% "drop" on every platform, purely because the month isn't over yet, not a real change.
- Licence of the data: write it down here (see the Transparency Database terms).
