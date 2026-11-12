"""Answer the six questions from the tables written by monitor.scale."""

from pathlib import Path

import duckdb

from monitor.config import load_settings


def _table(con: duckdb.DuckDBPyConnection, title: str, sql: str, lines: list[str]) -> None:
    rows = con.execute(sql).fetchall()
    if title:
        lines.append(f"\n## {title}\n")
    if not rows:
        lines.append("(no rows)")
        return
    for row in rows:
        lines.append("  " + " | ".join("" if v is None else str(v) for v in row))


def answer_questions(out_dir: Path) -> str:
    """Return a text report; also written to answers.md in out_dir."""
    plat = f"read_parquet('{(out_dir / 'platform_monthly.parquet').as_posix()}')"
    ctry = f"read_parquet('{(out_dir / 'scale_totals.parquet').as_posix()}')"
    con = duckdb.connect()
    first, last = con.execute(f"SELECT min(month), max(month) FROM {plat}").fetchall()[0]
    lines = [
        "# Six questions (TikTok, Instagram, Facebook, YouTube, X, Snapchat; EU countries)",
        f"Months covered: {first} to {last}. Counts are decisions in the published aggregates.",
        (
            "Platform-level answers count each decision once. Country-level answers count a "
            "decision in every country it lists, so country totals exceed the number of decisions."
        ),
    ]
    _table(
        con,
        "1. Decisions per month and platform",
        f"""
        SELECT month, platform, sum(decisions) AS decisions FROM {plat}
        GROUP BY 1, 2 ORDER BY 1, 3 DESC""",
        lines,
    )
    _table(
        con,
        "1a. Month-to-month changes of 50% or more in total decisions per platform",
        f"""
        WITH t AS (
            SELECT platform, month, sum(decisions) AS d FROM {plat} GROUP BY 1, 2
        ), s AS (
            SELECT platform, month, d, lag(month) OVER w AS prev_month, lag(d) OVER w AS prev
            FROM t WINDOW w AS (PARTITION BY platform ORDER BY month)
        )
        SELECT platform, prev_month || ' -> ' || month AS months, prev AS before, d AS after,
               round(100.0 * (d - prev) / prev, 1) AS change_pct
        FROM s WHERE prev IS NOT NULL AND abs(d - prev) >= 0.5 * prev
        ORDER BY platform, month""",
        lines,
    )
    _table(
        con,
        f"1b. Top 10 countries by country-specific decisions (all six platforms, {last})",
        f"""
        SELECT country, sum(decisions) AS decisions FROM {ctry}
        WHERE month = '{last}' AND scope_kind = 'listed'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10""",
        lines,
    )
    _table(
        con,
        f"1c. EU/EEA-wide decisions by platform ({last}); not specific to any one country",
        f"""
        SELECT platform, CAST(coalesce(sum(decisions) FILTER (WHERE scope_kind = 'eu_wide'), 0) / 27 AS BIGINT) AS decisions
        FROM {ctry} WHERE month = '{last}' GROUP BY 1 ORDER BY 2 DESC""",
        lines,
    )
    _table(
        con,
        "2. Share illegal content vs own rules, per platform (%)",
        f"""
        SELECT platform,
               coalesce(round(100.0 * sum(decisions) FILTER (WHERE decision_ground = 'illegal_content') / sum(decisions), 1), 0) AS illegal_pct,
               coalesce(round(100.0 * sum(decisions) FILTER (WHERE decision_ground = 'incompatible_content') / sum(decisions), 1), 0) AS own_rules_pct
        FROM {plat} GROUP BY 1 ORDER BY 1""",
        lines,
    )
    # Long table for charts: one row per month, platform, category.
    con.execute(f"""
        CREATE TABLE trends AS
        SELECT month, platform, category, sum(decisions) AS decisions,
               round(100.0 * sum(decisions) / sum(sum(decisions)) OVER (PARTITION BY month, platform), 2)
                   AS share_pct
        FROM {plat} GROUP BY 1, 2, 3 ORDER BY 2, 3, 1""")
    con.execute(
        f"COPY trends TO '{(out_dir / 'category_trends.csv').as_posix()}' (HEADER, DELIMITER ',')"
    )
    months = [r[0] for r in con.execute("SELECT DISTINCT month FROM trends ORDER BY 1").fetchall()]
    lines.append("\n## 3a. Top 5 categories per platform, decisions per month in thousands\n")
    lines.append("  months: " + " ".join(months))
    _table(
        con,
        "",
        """
        WITH top AS (
            SELECT platform, category, sum(decisions) AS total,
                   row_number() OVER (PARTITION BY platform ORDER BY sum(decisions) DESC) AS rk
            FROM trends GROUP BY 1, 2
        ), grid AS (
            SELECT t.platform, t.category, t.rk, m.month FROM top t
            CROSS JOIN (SELECT DISTINCT month FROM trends) m WHERE t.rk <= 5
        )
        SELECT g.platform, g.category,
               list(CAST(round(coalesce(r.decisions, 0) / 1000.0) AS BIGINT) ORDER BY g.month) AS thousands
        FROM grid g LEFT JOIN trends r
          ON r.platform = g.platform AND r.category = g.category AND r.month = g.month
        GROUP BY g.platform, g.category, g.rk ORDER BY g.platform, g.rk""",
        lines,
    )
    _table(
        con,
        "3b. Biggest month-to-month changes within a category (at least 100,000 decisions in one month)",
        """
        WITH s AS (
            SELECT platform, category, month, decisions,
                   lag(month) OVER w AS prev_month, lag(decisions) OVER w AS prev
            FROM trends WINDOW w AS (PARTITION BY platform, category ORDER BY month)
        )
        SELECT platform, category, prev_month || ' -> ' || month AS months, prev AS before,
               decisions AS after, round(100.0 * (decisions - prev) / nullif(prev, 0), 1) AS change_pct
        FROM s WHERE prev IS NOT NULL AND greatest(decisions, prev) >= 100000
        ORDER BY abs(decisions - prev) DESC LIMIT 12""",
        lines,
    )
    _table(
        con,
        "4. Automation per platform (%): detection, and decision fully / partially / not automated",
        f"""
        SELECT platform,
               coalesce(round(100.0 * sum(decisions) FILTER (WHERE automated_detection = 'yes') / sum(decisions), 1), 0) AS detected_automatically_pct,
               coalesce(round(100.0 * sum(decisions) FILTER (WHERE automated_mode = 'fully') / sum(decisions), 1), 0) AS decision_fully_pct,
               coalesce(round(100.0 * sum(decisions) FILTER (WHERE automated_mode = 'partially') / sum(decisions), 1), 0) AS decision_partially_pct,
               coalesce(round(100.0 * sum(decisions) FILTER (WHERE automated_mode = 'none') / sum(decisions), 1), 0) AS decision_by_people_pct
        FROM {plat} GROUP BY 1 ORDER BY 1""",
        lines,
    )
    _table(
        con,
        "5. Action taken, per platform (% of decisions)",
        f"""
        SELECT platform, action,
               round(100.0 * sum(decisions) / sum(sum(decisions)) OVER (PARTITION BY platform), 1) AS pct
        FROM {plat} GROUP BY 1, 2 ORDER BY 1, 3 DESC""",
        lines,
    )
    _table(
        con,
        f"6. Platform comparison in Germany, {last}: all decisions that include DE | only DE-specific",
        f"""
        SELECT platform, sum(decisions) AS including_eu_wide,
               coalesce(sum(decisions) FILTER (WHERE scope_kind = 'listed'), 0) AS de_specific
        FROM {ctry} WHERE country = 'DE' AND month = '{last}' GROUP BY 1 ORDER BY 2 DESC""",
        lines,
    )
    text = "\n".join(lines)
    (out_dir / "answers.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    """Entry point: python -m monitor.answers"""
    print(answer_questions(load_settings().out_dir))


if __name__ == "__main__":
    main()