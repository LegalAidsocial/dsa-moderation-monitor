"""SCRUM-62/63: flag sudden changes month to month, with a short explanation.

Reads platform_monthly.parquet (written by monitor.scale). Three kinds of
change, matching the brief's own examples ("a category doubling, or
automation dropping"):
  - a platform's total decisions jump or drop by PLATFORM_PCT or more
  - a category's decisions jump or drop by CATEGORY_PCT or more, once it's
    big enough to matter (at least CATEGORY_MIN_DECISIONS in one month)
  - a platform's automated-decision share moves by AUTOMATION_POINTS or
    more percentage points
"""

from datetime import date
from pathlib import Path

import duckdb

PLATFORM_PCT = 50.0
CATEGORY_PCT = 50.0
CATEGORY_MIN_DECISIONS = 100_000
AUTOMATION_POINTS = 20.0


def find_alerts(out_dir: Path, today: date | None = None) -> str:
    """Compare completed months only - verified live that the current
    calendar month always looks like a huge false "drop" against a
    finished month simply because it isn't over yet (confirmed against
    real Oct/Nov 2026 data: every platform showed an 80-90% apparent
    drop that was purely partial-month data, not a real change).
    """
    current_month = f"{(today or date.today()):%Y-%m}"
    plat = (
        f"(SELECT * FROM read_parquet('{(out_dir / 'platform_monthly.parquet').as_posix()}') "
        f"WHERE month != '{current_month}') AS plat"
    )
    con = duckdb.connect()
    lines: list[str] = []

    for platform, prev_month, month, prev, cur in con.execute(f"""
        WITH t AS (SELECT platform, month, sum(decisions) AS d FROM {plat} GROUP BY 1, 2),
             s AS (SELECT platform, month, d, lag(month) OVER w AS prev_month, lag(d) OVER w AS prev
                   FROM t WINDOW w AS (PARTITION BY platform ORDER BY month))
        SELECT platform, prev_month, month, prev, d FROM s
        WHERE prev IS NOT NULL AND prev > 0 AND abs(d - prev) >= {PLATFORM_PCT / 100} * prev
        ORDER BY platform, month"""
    ).fetchall():
        pct = round(100.0 * (cur - prev) / prev, 1)
        verb = "jumped" if pct > 0 else "dropped"
        lines.append(
            f"ALERT: {platform} total decisions {verb} {abs(pct)}% "
            f"({prev_month}: {prev:,} -> {month}: {cur:,})"
        )

    for platform, category, prev_month, month, prev, cur in con.execute(f"""
        WITH t AS (SELECT platform, category, month, sum(decisions) AS d FROM {plat} GROUP BY 1, 2, 3),
             s AS (SELECT platform, category, month, d, lag(month) OVER w AS prev_month, lag(d) OVER w AS prev
                   FROM t WINDOW w AS (PARTITION BY platform, category ORDER BY month))
        SELECT platform, category, prev_month, month, prev, d FROM s
        WHERE prev IS NOT NULL AND greatest(prev, d) >= {CATEGORY_MIN_DECISIONS}
          AND abs(d - prev) >= {CATEGORY_PCT / 100} * prev
        ORDER BY platform, category, month"""
    ).fetchall():
        pct = round(100.0 * (cur - prev) / prev, 1)
        verb = "doubled" if pct >= 100 else "jumped" if pct > 0 else "dropped"
        lines.append(
            f"ALERT: {platform}/{category} decisions {verb} {abs(pct)}% "
            f"({prev_month}: {prev:,} -> {month}: {cur:,})"
        )

    for platform, prev_month, month, prev, cur in con.execute(f"""
        WITH t AS (
            SELECT platform, month,
                   coalesce(100.0 * sum(decisions) FILTER (WHERE automated_mode != 'none') / sum(decisions), 0)
                       AS automated_pct
            FROM {plat} GROUP BY 1, 2
        ), s AS (
            SELECT platform, month, automated_pct,
                   lag(month) OVER w AS prev_month, lag(automated_pct) OVER w AS prev
            FROM t WINDOW w AS (PARTITION BY platform ORDER BY month)
        )
        SELECT platform, prev_month, month, prev, automated_pct FROM s
        WHERE prev IS NOT NULL AND abs(automated_pct - prev) >= {AUTOMATION_POINTS}
        ORDER BY platform, month"""
    ).fetchall():
        verb = "dropped" if cur < prev else "rose"
        lines.append(
            f"ALERT: {platform} automated-decision share {verb} from "
            f"{round(prev, 1)}% ({prev_month}) to {round(cur, 1)}% ({month})"
        )

    return "\n".join(lines) if lines else "No sudden changes detected."


def main() -> None:
    from monitor.config import load_settings

    print(find_alerts(load_settings().out_dir))


if __name__ == "__main__":
    main()
