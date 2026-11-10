"""Benchmark codefinder.find_codes. Run: uv run python benchmark.py

Prints the median texts-per-second for two text sets and appends one row per set
to benchmark_results.csv, so before/after numbers are on record.
"""

import csv
import datetime
import os
import platform
import random
import statistics
import time
from pathlib import Path

from codefinder import find_codes

SEED = 42
N_TEXTS = 10_000
REPEATS = 5
POSITIVE_SHARE = 0.03  # share of comment-like texts that contain a code
CASES = Path(__file__).parent / "tests" / "data" / "test-cases.csv"
RESULTS = Path(__file__).parent / "benchmark_results.csv"

WORDS = [
    "ich",
    "du",
    "wir",
    "ihr",
    "das",
    "ist",
    "nicht",
    "aber",
    "auch",
    "noch",
    "schon",
    "mal",
    "immer",
    "wieder",
    "heute",
    "gestern",
    "morgen",
    "video",
    "richtig",
    "gut",
    "schlecht",
    "krass",
    "genau",
    "stimmt",
    "leider",
    "danke",
    "bitte",
    "warum",
    "wieso",
    "wann",
    "deutschland",
    "berlin",
    "hamburg",
    "münchen",
    "politik",
    "regierung",
    "wahl",
    "partei",
    "bürger",
    "land",
    "leute",
    "the",
    "this",
    "that",
    "really",
    "good",
    "bad",
    "people",
    "time",
    "just",
    "like",
    "love",
    "hate",
    "watch",
    "share",
    "follow",
    "bus",
    "linie",
    "zimmer",
    "euro",
    "preis",
    "kosten",
    "jahre",
    "alt",
    "uhr",
    "minute",
    "spiel",
    "team",
    "sieg",
    "finale",
    "oma",
    "opa",
    "hund",
    "katze",
    "kinder",
    "schule",
    "arbeit",
    "wetter",
    "sonne",
    "regen",
    "urlaub",
    "fußball",
    "musik",
]
EMOJI = ["😂", "🔥", "👍", "😍", "🙏", "🇩🇪", "❤️", "🖤", "😡", "🎉"]


def load_cases() -> tuple[list[str], list[str]]:
    """Return (all test-case texts, positive test-case texts)."""
    with CASES.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    texts = [r["text"] for r in rows]
    positives = [r["text"] for r in rows if r["should_match"].strip().lower() == "yes"]
    return texts, positives


def make_comments(positives: list[str]) -> list[str]:
    """Comment-like texts: 8-60 words, numbers, emoji, hashtags; a few contain a code."""
    rng = random.Random(SEED)
    out: list[str] = []
    for _ in range(N_TEXTS):
        parts = [rng.choice(WORDS) for _ in range(rng.randint(8, 60))]
        for _ in range(rng.randint(0, 3)):
            parts.insert(rng.randrange(len(parts)), str(rng.randint(1, 2030)))
        for _ in range(rng.randint(0, 3)):
            parts.insert(rng.randrange(len(parts)), rng.choice(EMOJI))
        if rng.random() < 0.3:
            parts.append("#" + rng.choice(WORDS))
        if rng.random() < POSITIVE_SHARE:
            parts.insert(rng.randrange(len(parts)), rng.choice(positives))
        out.append(" ".join(parts))
    return out


def run(name: str, texts: list[str]) -> float:
    """Time find_codes over texts, REPEATS times. Return the median texts per second."""
    for t in texts[:200]:  # warm-up: loads rules, fills caches
        find_codes(t)
    rates = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        for t in texts:
            find_codes(t)
        rates.append(len(texts) / (time.perf_counter() - start))
    median = statistics.median(rates)
    avg_chars = sum(map(len, texts)) / len(texts)
    print(f"{name}: {len(texts)} texts, avg {avg_chars:.0f} chars")
    print(f"  median {median:,.0f}/s  (min {min(rates):,.0f}, max {max(rates):,.0f})")
    return median


def main() -> None:
    cases, positives = load_cases()
    short = (cases * (N_TEXTS // len(cases) + 1))[:N_TEXTS]
    sets = {"test-case strings": short, "comment-like texts": make_comments(positives)}
    label = (
        input("Label for this run (for example 'before' or 'after'): ").strip() or "run"
    )
    machine = f"{platform.processor() or platform.machine()} | {os.cpu_count()} cores | Python {platform.python_version()}"
    print(f"\n{machine}\n")
    new_file = not RESULTS.exists()
    with RESULTS.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(
                ["date", "label", "text_set", "texts", "median_per_second", "machine"]
            )
        for name, texts in sets.items():
            rate = run(name, texts)
            w.writerow(
                [datetime.date.today(), label, name, len(texts), round(rate), machine]
            )
    print(f"\nTarget: 10,000 per second. Results saved in {RESULTS.name}.")


if __name__ == "__main__":
    main()
