"""SCRUM-64: chart builders shared by the Streamlit dashboard and the
static HTML monthly report - one function per question, each returning
a plotly Figure, so both consumers render the exact same chart from the
same data.

Platform colors are a fixed categorical assignment (never re-cycled by
a filter) - slots 1-6, in order, from the project's validated 8-hue
categorical palette. A 7th platform would take slot 7, not reshuffle
these six.
"""

from pathlib import Path

import duckdb
import plotly.graph_objects as go

PLATFORM_COLORS = {
    "TikTok": "#2a78d6",  # slot 1, blue
    "Instagram": "#eb6834",  # slot 2, orange
    "Facebook": "#1baf7a",  # slot 3, aqua
    "YouTube": "#eda100",  # slot 4, yellow
    "X": "#e87ba4",  # slot 5, magenta
    "Snapchat": "#008300",  # slot 6, green
}
PLATFORM_ORDER = list(PLATFORM_COLORS)

ACTION_COLORS = {
    "removal": "#2a78d6",
    "hiding": "#eda100",
    "reduced_reach": "#1baf7a",
    "account_action": "#e34948",
    "other": "#898781",
}

CHART_LAYOUT = {
    "paper_bgcolor": "#fcfcfb",
    "plot_bgcolor": "#fcfcfb",
    "font": {"family": "system-ui, -apple-system, 'Segoe UI', sans-serif", "color": "#0b0b0b"},
    "legend": {"orientation": "h", "y": -0.25},
    "margin": {"t": 60, "b": 60, "l": 60, "r": 20},
}


def _platform_series(con: duckdb.DuckDBPyConnection, sql: str) -> dict[str, tuple[list, list]]:
    """Run sql (must select month, platform, value in that order) and
    group into {platform: (months, values)}, platforms in fixed order.
    """
    rows = con.execute(sql).fetchall()
    by_platform: dict[str, tuple[list, list]] = {}
    for platform in PLATFORM_ORDER:
        months = [r[0] for r in rows if r[1] == platform]
        values = [r[2] for r in rows if r[1] == platform]
        if months:
            by_platform[platform] = (months, values)
    return by_platform


def decisions_per_month(plat_path: Path) -> go.Figure:
    """Q1: decisions per month, per platform."""
    con = duckdb.connect()
    series = _platform_series(
        con,
        f"""SELECT month, platform, sum(decisions) AS decisions
            FROM read_parquet('{plat_path.as_posix()}') GROUP BY 1, 2 ORDER BY 1, 2""",
    )
    fig = go.Figure()
    for platform, (months, values) in series.items():
        fig.add_trace(
            go.Scatter(
                x=months,
                y=values,
                mode="lines+markers",
                name=platform,
                line={"color": PLATFORM_COLORS[platform], "width": 2},
                marker={"size": 6},
            )
        )
    fig.update_layout(
        title="Decisions per month, by platform", yaxis_title="Decisions", **CHART_LAYOUT
    )
    return fig


def illegal_vs_own_rules(plat_path: Path, month: str) -> go.Figure:
    """Q2: share of decisions for illegal content vs. the platform's own
    rules, per platform, for one month (the most recent finished one by
    default - caller picks it).
    """
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT platform,
               coalesce(100.0 * sum(decisions) FILTER (WHERE decision_ground = 'illegal_content') / sum(decisions), 0) AS illegal_pct,
               coalesce(100.0 * sum(decisions) FILTER (WHERE decision_ground = 'incompatible_content') / sum(decisions), 0) AS own_rules_pct
        FROM read_parquet('{plat_path.as_posix()}') WHERE month = '{month}' GROUP BY 1
    """).fetchall()
    by_platform = {r[0]: (r[1], r[2]) for r in rows}
    platforms = [p for p in PLATFORM_ORDER if p in by_platform]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=platforms,
            y=[by_platform[p][0] for p in platforms],
            name="Illegal content",
            marker_color="#2a78d6",
            text=[f"{by_platform[p][0]:.0f}%" for p in platforms],
            textposition="inside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=platforms,
            y=[by_platform[p][1] for p in platforms],
            name="Own rules",
            marker_color="#eb6834",
            text=[f"{by_platform[p][1]:.0f}%" for p in platforms],
            textposition="inside",
        )
    )
    fig.update_layout(
        title=f"Illegal content vs. own-rules share, by platform ({month})",
        yaxis_title="% of decisions",
        barmode="stack",
        **CHART_LAYOUT,
    )
    return fig


def category_trend(plat_path: Path, platform: str, top_n: int = 3) -> go.Figure:
    """Q3: the platform's top categories by volume, over time."""
    con = duckdb.connect()
    top = [
        r[0]
        for r in con.execute(f"""
            SELECT category, sum(decisions) AS d
            FROM read_parquet('{plat_path.as_posix()}') WHERE platform = '{platform}'
            GROUP BY 1 ORDER BY 2 DESC LIMIT {top_n}
        """).fetchall()
    ]
    fig = go.Figure()
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    for i, category in enumerate(top):
        rows = con.execute(f"""
            SELECT month, sum(decisions) FROM read_parquet('{plat_path.as_posix()}')
            WHERE platform = '{platform}' AND category = '{category}' GROUP BY 1 ORDER BY 1
        """).fetchall()
        fig.add_trace(
            go.Scatter(
                x=[r[0] for r in rows],
                y=[r[1] for r in rows],
                mode="lines+markers",
                name=category,
                line={"color": palette[i % len(palette)], "width": 2},
            )
        )
    fig.update_layout(
        title=f"{platform}: top {top_n} categories over time",
        yaxis_title="Decisions",
        **CHART_LAYOUT,
    )
    return fig


def automation_share(plat_path: Path, month: str) -> go.Figure:
    """Q4: automated detection and decision share, per platform."""
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT platform,
               coalesce(100.0 * sum(decisions) FILTER (WHERE automated_mode = 'fully') / sum(decisions), 0) AS fully,
               coalesce(100.0 * sum(decisions) FILTER (WHERE automated_mode = 'partially') / sum(decisions), 0) AS partially,
               coalesce(100.0 * sum(decisions) FILTER (WHERE automated_mode = 'none') / sum(decisions), 0) AS by_people
        FROM read_parquet('{plat_path.as_posix()}') WHERE month = '{month}' GROUP BY 1
    """).fetchall()
    by_platform = {r[0]: r[1:] for r in rows}
    platforms = [p for p in PLATFORM_ORDER if p in by_platform]
    labels = ["Fully automated", "Partially automated", "By people"]
    colors = ["#2a78d6", "#86b6ef", "#898781"]
    fig = go.Figure()
    for i, label in enumerate(labels):
        fig.add_trace(
            go.Bar(
                x=platforms,
                y=[by_platform[p][i] for p in platforms],
                name=label,
                marker_color=colors[i],
            )
        )
    fig.update_layout(
        title=f"Automation share of decisions, by platform ({month})",
        yaxis_title="% of decisions",
        barmode="stack",
        **CHART_LAYOUT,
    )
    return fig


def action_breakdown(plat_path: Path, month: str) -> go.Figure:
    """Q5: action taken (removal, hiding, reduced reach, account action,
    other), per platform.
    """
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT platform, action,
               100.0 * sum(decisions) / sum(sum(decisions)) OVER (PARTITION BY platform) AS pct
        FROM read_parquet('{plat_path.as_posix()}') WHERE month = '{month}' GROUP BY 1, 2
    """).fetchall()
    by_platform_action: dict[str, dict[str, float]] = {}
    for platform, action, pct in rows:
        by_platform_action.setdefault(platform, {})[action] = pct
    platforms = [p for p in PLATFORM_ORDER if p in by_platform_action]
    fig = go.Figure()
    for action, color in ACTION_COLORS.items():
        fig.add_trace(
            go.Bar(
                x=platforms,
                y=[by_platform_action[p].get(action, 0) for p in platforms],
                name=action.replace("_", " "),
                marker_color=color,
            )
        )
    fig.update_layout(
        title=f"Action taken, by platform ({month})",
        yaxis_title="% of decisions",
        barmode="stack",
        **CHART_LAYOUT,
    )
    return fig


def top_countries(scale_path: Path, month: str, top_n: int = 10) -> go.Figure:
    """Q6: top countries by country-specific decisions, all platforms, one month."""
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT country, sum(decisions) AS decisions
        FROM read_parquet('{scale_path.as_posix()}')
        WHERE month = '{month}' AND scope_kind = 'listed'
        GROUP BY 1 ORDER BY 2 DESC LIMIT {top_n}
    """).fetchall()
    fig = go.Figure(
        go.Bar(
            x=[r[0] for r in rows],
            y=[r[1] for r in rows],
            marker_color=[
                "#2a78d6" if r[0] == "DE" else "#86b6ef" for r in rows
            ],  # DE highlighted - own categorical hue, not a rainbow
            text=[f"{r[1]:,}" for r in rows],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=f"Top {top_n} countries by decisions ({month})",
        yaxis_title="Decisions",
        showlegend=False,
        **CHART_LAYOUT,
    )
    return fig
