"""The static HTML report, on a tiny fake dataset (offline)."""

from datetime import date
from pathlib import Path

import duckdb

from monitor.report import build_report


def make_fixtures(out_dir: Path) -> None:
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE plat AS SELECT * FROM (VALUES
            ('2026-09', 'TikTok', 'illegal_content', 'violence', 'yes', 'fully', 'removal', 100),
            ('2026-10', 'TikTok', 'illegal_content', 'violence', 'yes', 'fully', 'removal', 120),
            ('2026-11', 'TikTok', 'illegal_content', 'violence', 'yes', 'fully', 'removal', 5)
        ) v(month, platform, decision_ground, category, automated_detection, automated_mode,
            action, decisions)"""
    )
    con.execute(
        f"COPY plat TO '{(out_dir / 'platform_monthly.parquet').as_posix()}' (FORMAT PARQUET)"
    )
    con.execute(
        """CREATE TABLE scale AS SELECT * FROM (VALUES
            ('2026-10', 'TikTok', 'DE', 'listed', 50)
        ) v(month, platform, country, scope_kind, decisions)"""
    )
    con.execute(f"COPY scale TO '{(out_dir / 'scale_totals.parquet').as_posix()}' (FORMAT PARQUET)")


def test_build_report_writes_html_for_the_latest_finished_month(tmp_path: Path):
    make_fixtures(tmp_path)
    path = build_report(tmp_path, today=date(2026, 11, 16))

    assert path == tmp_path / "monthly_report.html"
    html = path.read_text(encoding="utf-8")
    assert "2026-10" in html  # the latest *finished* month, not the in-progress Nov
    assert "<html" in html
    assert "Q1. Decisions per month" in html
    assert "Q3. TikTok: top categories over time" in html


def test_build_report_is_self_contained_except_plotly_cdn(tmp_path: Path):
    make_fixtures(tmp_path)
    path = build_report(tmp_path, today=date(2026, 11, 16))
    html = path.read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" in html  # the one external dependency, loaded once
    assert html.count("<script src=") == 1  # not re-loaded per chart
