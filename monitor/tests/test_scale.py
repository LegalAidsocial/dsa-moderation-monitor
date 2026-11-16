"""Run build_scale on a tiny fake aggregate Parquet set (offline)."""

from pathlib import Path

import duckdb

from monitor.scale import build_scale


def make_aggregates(folder: Path) -> None:
    part = folder / "created_at_month=2026-10-01"
    part.mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE t AS SELECT * FROM (VALUES
            (DATE '2026-10-31', 'TikTok', 'EU', 'DECISION_GROUND_ILLEGAL_CONTENT', 'STATEMENT_CATEGORY_VIOLENCE',
             'Yes', 'AUTOMATED_DECISION_FULLY', true, false, false, NULL, NULL, 10),
            (DATE '2026-10-31', 'TikTok', 'DE_FR', 'DECISION_GROUND_INCOMPATIBLE_CONTENT', 'STATEMENT_CATEGORY_SCAMS_AND_FRAUD',
             'No', 'AUTOMATED_DECISION_NOT_AUTOMATED', false, false, true, NULL, NULL, 4),
            (DATE '2026-10-31', 'Twitter', 'ES', 'DECISION_GROUND_ILLEGAL_CONTENT', 'STATEMENT_CATEGORY_VIOLENCE',
             'Yes', 'AUTOMATED_DECISION_FULLY', false, false, false, 'DECISION_ACCOUNT_SUSPENDED', NULL, 3),
            (DATE '2026-10-31', 'Wikipedia', 'EU', 'DECISION_GROUND_ILLEGAL_CONTENT', 'STATEMENT_CATEGORY_VIOLENCE',
             'Yes', 'AUTOMATED_DECISION_FULLY', true, false, false, NULL, NULL, 99),
            (DATE '2026-10-31', 'TikTok', '', 'DECISION_GROUND_ILLEGAL_CONTENT', 'STATEMENT_CATEGORY_VIOLENCE',
             'Yes', 'AUTOMATED_DECISION_FULLY', true, false, false, NULL, NULL, 2)
        ) v(created_at, platform_name, territorial_scope, decision_ground, category, automated_detection,
            automated_decision, DECISION_VISIBILITY_CONTENT_REMOVED, DECISION_VISIBILITY_CONTENT_DISABLED,
            DECISION_VISIBILITY_CONTENT_DEMOTED, decision_account, decision_provision, "count")"""
    )
    con.execute(f"COPY t TO '{(part / 'part-0.parquet').as_posix()}' (FORMAT PARQUET)")


def test_build_scale(tmp_path: Path) -> None:
    agg, out = tmp_path / "agg", tmp_path / "out"
    make_aggregates(agg)
    counts = build_scale(agg, out)
    assert counts["countries"] == 27  # the EU scope reaches all 27 countries
    assert counts["decisions"] == 19  # other platforms (Wikipedia) are left out
    assert counts["empty_scope"] == 2
    con = duckdb.connect()
    src = f"read_parquet('{(out / 'scale_totals.parquet').as_posix()}')"
    de = dict(
        con.execute(
            f"SELECT action, sum(decisions) FROM {src} WHERE platform='TikTok' AND country='DE' GROUP BY 1"
        ).fetchall()
    )
    assert de == {"removal": 10, "reduced_reach": 4}
    x = con.execute(
        f"SELECT action, sum(decisions) FROM {src} WHERE platform='X' GROUP BY 1"
    ).fetchall()
    assert x == [("account_action", 3)]
    header = (out / "scale_totals.csv").read_text().splitlines()[0]
    assert header == (
        "month,platform,country,decision_ground,category,automated_detection,"
        "automated_decision,action,decisions"
    )
    kinds = dict(con.execute(f"SELECT scope_kind, sum(decisions) FROM {src} GROUP BY 1").fetchall())
    assert kinds["eu_wide"] == 10 * 27


def test_answer_questions_runs(tmp_path: Path) -> None:
    from monitor.answers import answer_questions

    agg, out = tmp_path / "agg", tmp_path / "out"
    make_aggregates(agg)
    build_scale(agg, out)
    text = answer_questions(out)
    assert "1. Decisions per month and platform" in text
    assert (out / "answers.md").exists()
    assert (out / "category_trends.csv").exists()
    assert "3a. Top 5 categories" in text