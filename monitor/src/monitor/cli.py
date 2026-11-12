"""Command line: `monitor build`."""

import argparse

from monitor.config import load_settings
from monitor.totals import build_totals


def main() -> None:
    """Entry point for the `monitor` command."""
    parser = argparse.ArgumentParser(prog="monitor")
    parser.add_argument("command", choices=["build"], help="build monthly totals")
    parser.parse_args()
    s = load_settings()
    build_totals(s.data_dir, s.out_dir, s.country, s.memory_limit)
