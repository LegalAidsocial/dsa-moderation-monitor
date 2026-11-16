"""SCRUM-64: the monthly report as a single static HTML file - the six
questions, answered in plain language, each backed by the chart that
shows it. Self-contained (plotly.js loaded once, inline), so it opens
straight from the filesystem with no server.
"""

from datetime import date
from pathlib import Path

import duckdb

from monitor import charts


def _latest_finished_month(plat_path: Path, today_month: str) -> str:
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT DISTINCT month FROM read_parquet('{plat_path.as_posix()}')
        WHERE month != '{today_month}' ORDER BY month DESC LIMIT 1
    """).fetchall()
    if not rows:
        raise ValueError("No finished month found to report on.")
    return rows[0][0]


def build_report(out_dir: Path, today: date | None = None) -> Path:
    """Write out_dir/monthly_report.html. Returns its path."""
    plat_path = out_dir / "platform_monthly.parquet"
    scale_path = out_dir / "scale_totals.parquet"
    today_month = f"{(today or date.today()):%Y-%m}"
    month = _latest_finished_month(plat_path, today_month)

    figures = {
        "Q1. Decisions per month, per platform": charts.decisions_per_month(plat_path),
        "Q2. Illegal content vs. own rules": charts.illegal_vs_own_rules(plat_path, month),
        "Q4. Automation share": charts.automation_share(plat_path, month),
        "Q5. Action taken": charts.action_breakdown(plat_path, month),
        "Q6. Top countries": charts.top_countries(scale_path, month, top_n=10),
    }
    present = {r[0] for r in _platforms_with_data(plat_path)}
    category_sections = "".join(
        f"<h3>Q3. {p}: top categories over time</h3>\n"
        + charts.category_trend(plat_path, p).to_html(
            full_html=False, include_plotlyjs=False, div_id=f"cat-{p}"
        )
        for p in charts.PLATFORM_ORDER
        if p in present
    )

    body_sections = "".join(
        f"<h2>{title}</h2>\n"
        + fig.to_html(full_html=False, include_plotlyjs=False, div_id=title[:2])
        for title, fig in figures.items()
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DSA moderation monitor - {month}</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
          color: #0b0b0b; background: #f9f9f7; max-width: 900px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 1.5rem; }}
  h2, h3 {{ color: #52514e; margin-top: 2.5rem; }}
  p.meta {{ color: #898781; }}
</style>
</head>
<body>
<h1>DSA platform moderation monitor</h1>
<p class="meta">Month: {month}. Six platforms, EU-wide totals. Only aggregate totals are shown - never single decisions.</p>
{body_sections}
{category_sections}
</body>
</html>
"""
    out_path = out_dir / "monthly_report.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _platforms_with_data(plat_path: Path) -> list[tuple[str]]:
    con = duckdb.connect()
    return con.execute(
        f"SELECT DISTINCT platform FROM read_parquet('{plat_path.as_posix()}')"
    ).fetchall()


def main() -> None:
    from monitor.config import load_settings

    path = build_report(load_settings().out_dir)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
