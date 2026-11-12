"""Stream daily zip files into monthly totals. Only aggregates are kept."""

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import duckdb

COLUMNS = (
    "month, platform, country, decision_ground, category, "
    "automated_detection, automated_decision, action"
)

AGGREGATE = """
    SELECT '{src}' AS src,
           strftime(try_cast(left(created_at, 10) AS DATE), '%Y-%m') AS month,
           platform_name AS platform,
           '{country}' AS country,
           lower(replace(decision_ground, 'DECISION_GROUND_', '')) AS decision_ground,
           lower(replace(category, 'STATEMENT_CATEGORY_', '')) AS category,
           CASE WHEN lower(automated_detection) IN ('yes', 'true') THEN 'yes' ELSE 'no' END
               AS automated_detection,
           CASE WHEN upper(automated_decision) LIKE '%NOT_AUTOMATED%' THEN 'no' ELSE 'yes' END
               AS automated_decision,
           CASE WHEN decision_visibility LIKE '%REMOVED%' THEN 'removal'
                WHEN decision_visibility LIKE '%DISABLED%' THEN 'hiding'
                WHEN decision_visibility LIKE '%DEMOTED%' THEN 'reduced_reach'
                WHEN coalesce(decision_account, '') NOT IN ('', '[]')
                  OR coalesce(decision_provision, '') NOT IN ('', '[]') THEN 'account_action'
                ELSE 'other' END AS action,
           count(*) AS decisions
    FROM read_csv('{csv}', header = true, all_varchar = true, null_padding = true)
    WHERE territorial_scope LIKE '%"{country}"%'
    GROUP BY ALL"""


def log(event: str, **fields: object) -> None:
    """Print one JSON line per event."""
    print(json.dumps({"event": event, **fields}), file=sys.stdout, flush=True)


def inner_files(outer: zipfile.ZipFile, name: str, tmp: Path) -> list[Path]:
    """Extract one entry of the outer zip to tmp. Return the CSV files it holds.

    The daily files are zips of zips: the outer zip holds many `*.csv.zip` chunks.
    Plain `.csv` entries are accepted too.
    """
    path = Path(outer.extract(name, tmp))
    if path.suffix.lower() != ".zip":
        return [path] if path.suffix.lower() == ".csv" else []
    inner_dir = tmp / (path.name + "_x")
    with zipfile.ZipFile(path) as inner:
        inner.extractall(inner_dir)
    path.unlink()
    return sorted(inner_dir.rglob("*.csv"))


def build_totals(data_dir: Path, out_dir: Path, country: str, memory_limit: str = "4GB") -> int:
    """Aggregate every new chunk in data_dir; write monthly Parquet and CSV.

    Works one chunk at a time and records each finished chunk, so a stopped run resumes.
    Returns the number of chunks processed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(out_dir / "work.duckdb"))
    con.execute(f"PRAGMA memory_limit='{memory_limit}'")
    con.execute(f"PRAGMA temp_directory='{(out_dir / 'duckdb_tmp').as_posix()}'")
    con.execute(
        """CREATE TABLE IF NOT EXISTS partial (
            src VARCHAR, month VARCHAR, platform VARCHAR, country VARCHAR,
            decision_ground VARCHAR, category VARCHAR, automated_detection VARCHAR,
            automated_decision VARCHAR, action VARCHAR, decisions BIGINT)"""
    )
    done = {r[0] for r in con.execute("SELECT DISTINCT src FROM partial").fetchall()}
    processed = 0
    for z in sorted(data_dir.glob("*.zip")):
        with zipfile.ZipFile(z) as outer:
            for name in sorted(i.filename for i in outer.infolist() if not i.is_dir()):
                src = f"{z.name}/{name}"
                if src in done:
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    csvs = inner_files(outer, name, Path(tmp))
                    con.execute("BEGIN")
                    for f in csvs:
                        con.execute(
                            "INSERT INTO partial "
                            + AGGREGATE.format(src=src, country=country, csv=f.as_posix())
                        )
                    con.execute("COMMIT")
                processed += 1
                log("done", file=src)
    monthly = f"""SELECT {COLUMNS}, sum(decisions) AS decisions
                  FROM partial GROUP BY ALL ORDER BY ALL"""
    con.execute(
        f"COPY ({monthly}) TO '{(out_dir / 'monthly_totals.parquet').as_posix()}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY ({monthly}) TO '{(out_dir / 'monthly_totals.csv').as_posix()}' (HEADER, DELIMITER ',')"
    )
    con.close()
    log("written", out_dir=str(out_dir))
    return processed