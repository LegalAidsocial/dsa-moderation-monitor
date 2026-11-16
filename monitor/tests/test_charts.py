"""Chart builders, on a tiny fake platform_monthly/scale_totals (offline)."""

from pathlib import Path

import duckdb

from monitor import charts


def make_platform_monthly(path: Path) -> None:
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE t AS SELECT * FROM (VALUES
            ('2026-09', 'TikTok', 'illegal_content', 'violence', 'yes', 'fully', 'removal', 100),
            ('2026-09', 'TikTok', 'incompatible_content', 'scams_and_fraud', 'no', 'none', 'hiding', 50),
            ('2026-10', 'TikTok', 'illegal_content', 'violence', 'yes', 'fully', 'removal', 120),
            ('2026-09', 'Instagram', 'incompatible_content', 'scams_and_fraud', 'no', 'partially', 'account_action', 30),
            ('2026-10', 'Instagram', 'incompatible_content', 'scams_and_fraud', 'no', 'partially', 'account_action', 40)
        ) v(month, platform, decision_ground, category, automated_detection, automated_mode,
            action, decisions)"""
    )
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")


def make_scale_totals(path: Path) -> None:
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE t AS SELECT * FROM (VALUES
            ('2026-10', 'TikTok', 'DE', 'listed', 50),
            ('2026-10', 'TikTok', 'FR', 'listed', 30)
        ) v(month, platform, country, scope_kind, decisions)"""
    )
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")


def test_decisions_per_month_uses_fixed_platform_colors(tmp_path: Path):
    path = tmp_path / "platform_monthly.parquet"
    make_platform_monthly(path)
    fig = charts.decisions_per_month(path)
    names = [t.name for t in fig.data]
    assert names == ["TikTok", "Instagram"]  # fixed order, not insertion order
    tiktok_trace = next(t for t in fig.data if t.name == "TikTok")
    assert tiktok_trace.line.color == charts.PLATFORM_COLORS["TikTok"]
    assert list(tiktok_trace.y) == [150, 120]  # 100+50 summed for 2026-09


def test_illegal_vs_own_rules_percentages(tmp_path: Path):
    path = tmp_path / "platform_monthly.parquet"
    make_platform_monthly(path)
    fig = charts.illegal_vs_own_rules(path, "2026-09")
    illegal = next(t for t in fig.data if t.name == "Illegal content")
    own_rules = next(t for t in fig.data if t.name == "Own rules")
    tiktok_idx = list(illegal.x).index("TikTok")
    assert round(illegal.y[tiktok_idx]) == 67  # 100 of 150
    assert round(own_rules.y[tiktok_idx]) == 33


def test_category_trend_picks_top_n(tmp_path: Path):
    path = tmp_path / "platform_monthly.parquet"
    make_platform_monthly(path)
    fig = charts.category_trend(path, "TikTok", top_n=2)
    names = {t.name for t in fig.data}
    assert names == {"violence", "scams_and_fraud"}


def test_top_countries_highlights_de(tmp_path: Path):
    path = tmp_path / "scale_totals.parquet"
    make_scale_totals(path)
    fig = charts.top_countries(path, "2026-10")
    trace = fig.data[0]
    de_idx = list(trace.x).index("DE")
    assert trace.marker.color[de_idx] == "#2a78d6"
    other_idx = list(trace.x).index("FR")
    assert trace.marker.color[other_idx] == "#86b6ef"


def test_no_dual_axis_in_any_chart(tmp_path: Path):
    """Non-negotiable per the dataviz skill: never two y-scales on one chart."""
    path = tmp_path / "platform_monthly.parquet"
    make_platform_monthly(path)
    fig = charts.decisions_per_month(path)
    assert "yaxis2" not in fig.layout
