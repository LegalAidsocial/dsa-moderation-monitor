"""Scale-up: monthly totals for six platforms x 27 EU countries.

Reads the published daily aggregates (dsa-tdb "complete" Parquet). Only totals are kept.
Writes two tables to the output folder:
  platform_monthly.parquet  decisions counted once (use for shares per platform)
  scale_totals.parquet/.csv one row per country (the CSV has exactly the template columns;
                            the Parquet also has scope_kind and automated_mode) (a decision that lists
                            several countries counts once in each, so country totals
                            add up to more than the number of decisions)
"""

import json
import sys
from pathlib import Path

import duckdb

from monitor.config import load_settings

EU27 = [
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
    "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
]  # fmt: skip
SPECIAL_SCOPES = ("EU", "EEA", "EEA_no_IS")  # count in all 27 countries

PLATFORM_RULES = {
    "TikTok": "contains(lower(platform_name), 'tiktok')",
    "Instagram": "contains(lower(platform_name), 'instagram')",
    "Facebook": "contains(lower(platform_name), 'facebook')",
    "YouTube": "contains(lower(platform_name), 'youtube')",
    "X": "(lower(platform_name) = 'x' OR starts_with(lower(platform_name), 'x ') "
    "OR contains(lower(platform_name), 'twitter'))",
    "Snapchat": "contains(lower(platform_name), 'snapchat')",
}

# Earlier daily-file result for TikTok, scope includes DE, 2026-10-31 (decisions per action)
KNOWN_TIKTOK_DE_20261031 = {
    "other": 1334816, "removal": 1260452, "account_action": 14364,
    "reduced_reach": 2380, "hiding": 340,
}  # fmt: skip


def log(event: str, **fields: object) -> None:
    """Print one JSON line per event."""
    print(json.dumps({"event": event, **fields}), file=sys.stdout, flush=True)


def _flag(cols: set[str], name: str) -> str:
    if name not in cols:
        return "FALSE"
    return f"lower(CAST({name} AS VARCHAR)) IN ('true', '1', 't', 'yes')"


def _filled(cols: set[str], name: str) -> str:
    if name not in cols:
        return "FALSE"
    return f"coalesce(CAST({name} AS VARCHAR), '') NOT IN ('', '[]')"


def _sql_parts(cols: set[str]) -> tuple[str, str]:
    """Return the SQL for the platform name and for the action, given the columns present."""
    platform = (
        "CASE "
        + " ".join(f"WHEN {rule} THEN '{name}'" for name, rule in PLATFORM_RULES.items())
        + " END"
    )
    action = (
        f"CASE WHEN {_flag(cols, 'DECISION_VISIBILITY_CONTENT_REMOVED')} THEN 'removal' "
        f"WHEN {_flag(cols, 'DECISION_VISIBILITY_CONTENT_DISABLED')} THEN 'hiding' "
        f"WHEN {_flag(cols, 'DECISION_VISIBILITY_CONTENT_DEMOTED')} THEN 'reduced_reach' "
        f"WHEN {_filled(cols, 'decision_account')} OR {_filled(cols, 'decision_provision')} "
        "THEN 'account_action' ELSE 'other' END"
    )
    return platform, action


def build_scale(agg_dir: Path, out_dir: Path, memory_limit: str = "4GB") -> dict[str, int]:
    """Build the platform and country tables. Returns a few counts for checking."""
    out_dir.mkdir(parents=True, exist_ok=True)
    src = f"read_parquet('{(agg_dir / '**' / '*.parquet').as_posix()}', hive_partitioning = true, union_by_name = true)"
    con = duckdb.connect()
    con.execute(f"PRAGMA memory_limit='{memory_limit}'")
    con.execute(f"PRAGMA temp_directory='{(out_dir / 'duckdb_tmp').as_posix()}'")
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    platform_sql, action_sql = _sql_parts(cols)
    log(
        "columns_missing",
        missing=[
            c for c in ("DECISION_VISIBILITY_CONTENT_REMOVED", "decision_account") if c not in cols
        ],
    )

    con.execute(f"""
        CREATE TABLE stage AS
        SELECT month, platform, scope, decision_ground, category, automated_detection,
               automated_mode, action, sum(n) AS decisions
        FROM (
            SELECT left(CAST(created_at AS VARCHAR), 7) AS month,
                   {platform_sql} AS platform,
                   coalesce(territorial_scope, '') AS scope,
                   lower(replace(CAST(decision_ground AS VARCHAR), 'DECISION_GROUND_', '')) AS decision_ground,
                   lower(replace(CAST(category AS VARCHAR), 'STATEMENT_CATEGORY_', '')) AS category,
                   CASE WHEN lower(CAST(automated_detection AS VARCHAR)) IN ('yes', 'true', '1')
                        THEN 'yes' ELSE 'no' END AS automated_detection,
                   CASE WHEN upper(CAST(automated_decision AS VARCHAR)) LIKE '%NOT_AUTOMATED%'
                          OR lower(CAST(automated_decision AS VARCHAR)) IN ('no', 'false', '0')
                        THEN 'none'
                        WHEN upper(CAST(automated_decision AS VARCHAR)) LIKE '%PARTIALLY%' THEN 'partially'
                        ELSE 'fully' END AS automated_mode,
                   {action_sql} AS action,
                   "count" AS n
            FROM {src}
        ) WHERE platform IS NOT NULL
        GROUP BY ALL""")

    eu_list = "[" + ", ".join(f"'{c}'" for c in EU27) + "]"
    special = ", ".join(f"'{s}'" for s in SPECIAL_SCOPES)
    con.execute(f"""
        CREATE TABLE by_country AS
        SELECT month, platform, country, scope_kind, decision_ground, category,
               automated_detection, automated_mode,
               CASE WHEN automated_mode = 'none' THEN 'no' ELSE 'yes' END AS automated_decision,
               action, CAST(sum(decisions) AS BIGINT) AS decisions
        FROM (
            SELECT *, CASE WHEN scope IN ({special}) THEN 'eu_wide' ELSE 'listed' END AS scope_kind,
                   UNNEST(CASE WHEN scope IN ({special}) THEN {eu_list}
                               ELSE string_split(scope, '_') END) AS country
            FROM stage
        ) WHERE country IN ({", ".join(f"'{c}'" for c in EU27)})
        GROUP BY ALL ORDER BY ALL""")
    con.execute("""
        CREATE TABLE by_platform AS
        SELECT month, platform, decision_ground, category, automated_detection, automated_mode,
               CASE WHEN automated_mode = 'none' THEN 'no' ELSE 'yes' END AS automated_decision,
               action, CAST(sum(decisions) AS BIGINT) AS decisions
        FROM stage GROUP BY ALL ORDER BY ALL""")

    for table, name in (("by_platform", "platform_monthly"), ("by_country", "scale_totals")):
        con.execute(
            f"COPY {table} TO '{(out_dir / (name + '.parquet')).as_posix()}' (FORMAT PARQUET)"
        )
    template_csv = """
        SELECT month, platform, country, decision_ground, category, automated_detection,
               automated_decision, action, sum(decisions) AS decisions
        FROM by_country GROUP BY ALL ORDER BY ALL"""
    con.execute(
        f"COPY ({template_csv}) TO '{(out_dir / 'scale_totals.csv').as_posix()}' (HEADER, DELIMITER ',')"
    )

    counts = {
        "platform_rows": con.execute("SELECT count(*) FROM by_platform").fetchall()[0][0],
        "country_rows": con.execute("SELECT count(*) FROM by_country").fetchall()[0][0],
        "countries": con.execute("SELECT count(DISTINCT country) FROM by_country").fetchall()[0][0],
        "decisions": int(
            con.execute("SELECT coalesce(sum(decisions), 0) FROM by_platform").fetchall()[0][0]
        ),
        "eu_wide": int(
            con.execute(
                "SELECT coalesce(sum(decisions), 0) FROM stage WHERE scope IN ('EU', 'EEA', 'EEA_no_IS')"
            ).fetchall()[0][0]
        ),
        "empty_scope": int(
            con.execute(
                "SELECT coalesce(sum(decisions), 0) FROM stage WHERE scope = ''"
            ).fetchall()[0][0]
        ),
    }
    log("written", out_dir=str(out_dir), **counts)

    print("\nPlatform names matched (raw name -> six):")
    for row in con.execute(f"""
        SELECT platform_name, {platform_sql} AS six, CAST(sum("count") AS BIGINT)
        FROM {src} GROUP BY 1, 2 HAVING six IS NOT NULL ORDER BY 2, 3 DESC""").fetchall():
        print("  ", row)

    print("\nDecisions per platform and month:")
    for row in con.execute(
        "SELECT platform, month, sum(decisions) FROM by_platform GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall():
        print("  ", row)

    check_tiktok(con, src, action_sql)
    con.close()
    return counts


def check_tiktok(con: duckdb.DuckDBPyConnection, src: str, action_sql: str) -> None:
    """Compare with the earlier daily-file result (TikTok, DE in scope, 2026-10-31)."""
    rows = con.execute(f"""
        SELECT {action_sql} AS action, CAST(sum("count") AS BIGINT)
        FROM {src}
        WHERE contains(lower(platform_name), 'tiktok')
          AND left(CAST(created_at AS VARCHAR), 10) = '2026-10-31'
          AND (territorial_scope IN ('EU', 'EEA', 'EEA_no_IS')
               OR list_contains(string_split(territorial_scope, '_'), 'DE'))
        GROUP BY 1""").fetchall()
    if not rows:
        print("\nCheck skipped: 2026-10-31 not in these files.")
        return
    got = dict(rows)
    ok = got == KNOWN_TIKTOK_DE_20261031
    print(f"\nCheck vs daily-file result, TikTok DE 2026-10-31: {'MATCH' if ok else 'DIFFERENT'}")
    if not ok:
        for action in sorted(set(got) | set(KNOWN_TIKTOK_DE_20261031)):
            print(
                f"   {action}: aggregates {got.get(action, 0)} | daily files {KNOWN_TIKTOK_DE_20261031.get(action, 0)}"
            )


def main() -> None:
    """Entry point: python -m monitor.scale"""
    s = load_settings()
    build_scale(s.agg_dir, s.out_dir, s.memory_limit)


if __name__ == "__main__":
    main()