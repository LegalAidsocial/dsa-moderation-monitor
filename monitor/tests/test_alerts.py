"""Run find_alerts on a tiny fake platform_monthly.parquet (offline)."""

from datetime import date
from pathlib import Path

import duckdb

from monitor.alerts import find_alerts

TODAY = date(2026, 11, 12)


def make_platform_monthly(path: Path) -> None:
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE t AS SELECT * FROM (VALUES
            -- TikTok: total roughly flat, no platform-level alert
            ('2026-09', 'TikTok', 'illegal_content', 'hate_speech', 'yes', 'none', 'removal', 100000),
            ('2026-10', 'TikTok', 'illegal_content', 'hate_speech', 'yes', 'none', 'removal', 105000),
            -- TikTok hate_speech category more than doubles month to month
            ('2026-09', 'TikTok', 'illegal_content', 'scams', 'yes', 'none', 'removal', 5000),
            ('2026-10', 'TikTok', 'illegal_content', 'scams', 'yes', 'none', 'removal', 5200),
            -- Instagram: total decisions jump 200%, small category stays under the floor
            ('2026-09', 'Instagram', 'incompatible_content', 'violence', 'no', 'fully', 'hiding', 10000),
            ('2026-10', 'Instagram', 'incompatible_content', 'violence', 'no', 'fully', 'hiding', 30000),
            -- YouTube: automated share drops from ~100% to 0%
            ('2026-09', 'YouTube', 'illegal_content', 'spam', 'yes', 'fully', 'removal', 50000),
            ('2026-10', 'YouTube', 'illegal_content', 'spam', 'yes', 'none', 'removal', 50000)
        ) v(month, platform, decision_ground, category, automated_detection, automated_mode,
            action, decisions)"""
    )
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")


def test_find_alerts_detects_platform_category_and_automation_changes(tmp_path: Path):
    make_platform_monthly(tmp_path / "platform_monthly.parquet")
    text = find_alerts(tmp_path, today=TODAY)

    assert "Instagram total decisions jumped 200.0%" in text
    assert "TikTok total decisions" not in text  # +5% is not a sudden change
    assert "scams" not in text  # under the 100k-decision floor
    assert "YouTube automated-decision share dropped" in text


def test_find_alerts_reports_none_when_nothing_changed(tmp_path: Path):
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE t AS SELECT * FROM (VALUES
            ('2026-09', 'TikTok', 'illegal_content', 'hate_speech', 'yes', 'none', 'removal', 100000),
            ('2026-10', 'TikTok', 'illegal_content', 'hate_speech', 'yes', 'none', 'removal', 101000)
        ) v(month, platform, decision_ground, category, automated_detection, automated_mode,
            action, decisions)"""
    )
    con.execute(f"COPY t TO '{(tmp_path / 'platform_monthly.parquet').as_posix()}' (FORMAT PARQUET)")

    assert find_alerts(tmp_path, today=TODAY) == "No sudden changes detected."


def test_find_alerts_excludes_the_current_in_progress_month(tmp_path: Path):
    """Verified live against real Oct/Nov 2026 data: comparing a finished
    month to the still-in-progress current month produces a false ~85%
    "drop" on every platform, purely from the month not being over yet.
    """
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE t AS SELECT * FROM (VALUES
            ('2026-10', 'TikTok', 'illegal_content', 'hate_speech', 'yes', 'none', 'removal', 100000),
            ('2026-11', 'TikTok', 'illegal_content', 'hate_speech', 'yes', 'none', 'removal', 12000)
        ) v(month, platform, decision_ground, category, automated_detection, automated_mode,
            action, decisions)"""
    )
    con.execute(f"COPY t TO '{(tmp_path / 'platform_monthly.parquet').as_posix()}' (FORMAT PARQUET)")

    assert find_alerts(tmp_path, today=TODAY) == "No sudden changes detected."
