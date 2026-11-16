"""Run build_totals on a tiny fake daily zip (offline)."""

import csv
import zipfile
from pathlib import Path

from monitor.totals import build_totals

HEADER = (
    "created_at,platform_name,territorial_scope,decision_ground,category,automated_detection,"
    "automated_decision,decision_visibility,decision_account,decision_provision,decision_facts\n"
)
ROWS = [
    (
        '2026-01-05 10:00:00,TikTok,"[""DE"",""FR""]",DECISION_GROUND_ILLEGAL_CONTENT,'
        "STATEMENT_CATEGORY_VIOLENCE,Yes,AUTOMATED_DECISION_NOT_AUTOMATED,"
        '"[""DECISION_VISIBILITY_CONTENT_REMOVED""]",,,"text, with comma"'
    ),
    (
        '2026-01-05 11:00:00,TikTok,"[""FR""]",DECISION_GROUND_ILLEGAL_CONTENT,'
        "STATEMENT_CATEGORY_VIOLENCE,Yes,AUTOMATED_DECISION_FULLY,"
        '"[""DECISION_VISIBILITY_CONTENT_REMOVED""]",,,x'
    ),
]


def make_zip(folder: Path) -> None:
    """Outer zip holding two inner `.csv.zip` chunks, like the real daily files."""
    inner = folder / "chunk.csv.zip"
    with zipfile.ZipFile(inner, "w") as zi:
        zi.writestr("chunk.csv", HEADER + "\n".join(ROWS) + "\n")
    with zipfile.ZipFile(folder / "sor-tiktok-2026-01-05-full.zip", "w") as z:
        z.write(inner, "sor-tiktok-2026-01-05-full-00000.csv.zip")
        z.write(inner, "sor-tiktok-2026-01-05-full-00001.csv.zip")
    inner.unlink()


def test_build_totals_filters_country_and_is_rerunnable(tmp_path: Path) -> None:
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    make_zip(data)
    assert build_totals(data, out, "DE") == 2
    with (out / "monthly_totals.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == [
        "month",
        "platform",
        "country",
        "decision_ground",
        "category",
        "automated_detection",
        "automated_decision",
        "action",
        "decisions",
    ]
    assert len(rows) == 1 and rows[0]["decisions"] == "2" and rows[0]["action"] == "removal"
    assert build_totals(data, out, "DE") == 0  # finished files are skipped