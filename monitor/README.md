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
uv run --package monitor monitor report         # rebuild just the static HTML report
uv run --package monitor streamlit run monitor/src/monitor/dashboard.py   # interactive dashboard
```

`build`/`update` fetch the published six-platform aggregates themselves
(see `fetch.py` - confirmed live against the real CloudFront host) into
`MONITOR_AGG_DIR`, then rebuild `out/platform_monthly.parquet`,
`out/scale_totals.{parquet,csv}` (CSV in the `monthly-template.csv`
shape), `out/answers.md` (the six questions, answered) and
`out/monthly_report.html` (SCRUM-64 - the same six questions, as
charts, self-contained except for one CDN script tag).

`dashboard.py` is a separate Streamlit app (run with `streamlit run`,
not through the `monitor` CLI) for our own interactive checking - the
deliverable is the static HTML report, this is just a faster way to
look at the current numbers while working. Both read the exact same
chart-builder functions in `charts.py`, so they never drift apart.

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

## Docker
```bash
docker compose up --build monitor
```
Starts just the interactive dashboard (`monitor/Dockerfile`, published on `MONITOR_PORT`,
default 8501) - the container builds and serves even with an empty `out/`, showing
"run `monitor build` first" until data exists. `build`/`update`/`alerts`/`report` are one-off
CLI commands, not a long-running service, so run them inside the running container instead:
```bash
docker compose exec monitor monitor build
```

## Notes
- Each zip is unzipped to a temp folder, aggregated by DuckDB, then deleted. Finished zips are skipped on re-runs.
- `action` is one value per decision, chosen by priority: removal, hiding, reduced_reach, account_action, other.
- `monitor alerts` excludes the current calendar month from all comparisons - verified live that comparing a finished month to the still-in-progress current one always looks like an 80-90% "drop" on every platform, purely because the month isn't over yet, not a real change.
- `monitor alerts` was tested against 3+ real past changes (SCRUM-63), not just synthetic fixtures - real numbers pulled live from the actual database, with researched real-world context for each. See `test_find_alerts_on_3_real_past_changes` in `tests/test_alerts.py` for the full detail and sources: a TikTok total-decisions jump coinciding with its Dec 2025 DSA transparency commitments, an independently-cross-checked TikTok drop in Oct 2026 (a third-party tracker reading the same public database got a matching number), and a YouTube election/civic-discourse category spike coinciding with real German regional elections in March 2026.
- Chart colors are a fixed categorical assignment per platform (TikTok/Instagram/Facebook/YouTube/X/Snapchat, in that order), never re-cycled when a filter changes what's visible - same six colors in the dashboard and the static report, from `charts.PLATFORM_COLORS`.
- Real finding worth flagging for the SCRUM-65 write-up: almost every platform reports ~99-100% of decisions under its own rules rather than "illegal content" (Q2) - only X reports the reverse, ~100% illegal content. Worth checking whether that's a genuine policy difference or a reporting-category quirk before writing it up as fact.

## Licences

See [LICENCES.md](LICENCES.md) for the data licence (DSA Transparency Database, CC BY 4.0) and the licences of the dependencies.
