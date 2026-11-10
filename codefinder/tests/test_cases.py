"""Run codefinder against tests/data/test-cases.csv (offline, no network)."""

import csv
from pathlib import Path
from typing import Any

import pytest

from codefinder import find_codes

CASES_FILE = Path(__file__).parent / "data" / "test-cases.csv"


def load_cases() -> list[tuple[str, bool, frozenset[str], str]]:
    """Read the CSV (UTF-8, BOM tolerated) into test parameters."""
    with CASES_FILE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        (
            row["text"],
            row["should_match"].strip().lower() == "yes",
            frozenset(
                c.strip().lower() for c in row["expected_codes"].split(";") if c.strip()
            ),
            row["note"],
        )
        for row in rows
    ]


def found_names(result: Any) -> set[str]:
    """Turn find_codes() output into a set of lowercase code names.

    Adjust this one function if find_codes returns something other than a
    list of strings or objects with a .code / .name attribute.
    """
    names: set[str] = set()
    for item in result or []:
        if isinstance(item, str):
            names.add(item.lower())
        else:
            value = getattr(item, "code", None) or getattr(item, "name", None)
            if value:
                names.add(str(value).lower())
    return names


CASES = load_cases()


def test_case_file_size() -> None:
    """Guard the SCRUM-49 targets: 300+ cases, 100+ negatives."""
    negatives = [c for c in CASES if not c[1]]
    assert len(CASES) >= 300
    assert len(negatives) >= 100


@pytest.mark.parametrize(
    ("text", "should_match", "expected", "note"),
    CASES,
    ids=[f"{i:03d}-{c[3][:30]}" for i, c in enumerate(CASES)],
)
def test_find_codes(
    text: str, should_match: bool, expected: frozenset[str], note: str
) -> None:
    names = found_names(find_codes(text))
    if should_match:
        assert names, f"missed ({note}): {text!r}"
        if expected:
            assert expected & names, (
                f"wrong code ({note}): expected {set(expected)}, got {names}"
            )
    else:
        assert not names, f"false positive ({note}): {text!r} -> {names}"
