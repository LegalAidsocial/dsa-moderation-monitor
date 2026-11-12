"""Command line: `monitor build [--months N]`, `monitor update`, `monitor alerts`."""

import argparse

from monitor.alerts import find_alerts
from monitor.answers import answer_questions
from monitor.config import load_settings
from monitor.fetch import download_months, last_n_months
from monitor.scale import build_scale
from monitor.totals import build_totals

DEFAULT_MONTHS = 12


def _rebuild(months: list[str]) -> None:
    s = load_settings()
    download_months(months, s.agg_dir)
    build_totals(s.data_dir, s.out_dir, s.country, s.memory_limit)
    build_scale(s.agg_dir, s.out_dir, s.memory_limit)
    answer_questions(s.out_dir)


def build(months: int) -> None:
    """Rebuild everything from scratch, using the last `months` months."""
    _rebuild(last_n_months(months))


def update() -> None:
    """Add the newest month (re-fetched, since it's appended daily) and rebuild."""
    _rebuild(last_n_months(1))


def main() -> None:
    parser = argparse.ArgumentParser(prog="monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="rebuild everything from scratch")
    build_p.add_argument(
        "--months", type=int, default=DEFAULT_MONTHS, help="how many months back to fetch"
    )

    sub.add_parser("update", help="fetch the newest month and rebuild the report")
    sub.add_parser("alerts", help="flag sudden month-to-month changes")

    args = parser.parse_args()
    if args.command == "build":
        build(args.months)
    elif args.command == "update":
        update()
    elif args.command == "alerts":
        print(find_alerts(load_settings().out_dir))


if __name__ == "__main__":
    main()
