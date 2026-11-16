"""Download the DSA Transparency Database's published monthly aggregates.

These are the "complete" aggregated Parquet files (all platforms, all
decision grounds/categories), updated daily by the Commission by
appending to the current month's file - not the raw per-decision daily
dumps, which totals.py expects to already be present in data_dir
(downloaded separately; there is no documented stable URL for those).

URL pattern confirmed live against the real CloudFront host (not
guessed): https://dsa.pages.code.europa.eu/transparency-database/dsa-tdb/data_sources.html
"""

import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import requests

BASE_URL = (
    "https://d3vax7phxnku8l.cloudfront.net/agg/pqt/data/tdb_data/"
    "global___full/aggregations"
)


def log(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}), file=sys.stdout, flush=True)


def month_url(month: str) -> str:
    """month is 'YYYY-MM'. The published file is always dated the 1st."""
    return f"{BASE_URL}/aggregated-complete-{month}-01-parquet.zip"


def last_n_months(n: int, today: date | None = None) -> list[str]:
    """The last n months as 'YYYY-MM', oldest first, including the current month."""
    today = today or date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(months))


def download_month(month: str, agg_dir: Path, force: bool = False) -> Path:
    """Download and unzip one month's aggregate into agg_dir.

    The zip's own internal layout is
    aggregated-complete.parquet/created_at_month=<month>-01/*.parquet
    (confirmed live) - extracting straight into agg_dir preserves that,
    and scale.py's recursive **/*.parquet glob finds it regardless of
    nesting depth.

    Re-downloads the current month even when not forced, since the
    Commission appends to it daily - anything older is treated as
    finished and skipped unless force=True.
    """
    out = agg_dir / "aggregated-complete.parquet" / f"created_at_month={month}-01"
    current_month = f"{date.today():%Y-%m}"
    if out.exists() and month != current_month and not force:
        log("skipped", month=month, reason="already downloaded, not current month")
        return out

    agg_dir.mkdir(parents=True, exist_ok=True)
    zip_path = agg_dir / f"aggregated-complete-{month}-01-parquet.zip"
    resp = requests.get(month_url(month), timeout=120)
    if resp.status_code == 404:
        log("not_available", month=month)
        raise FileNotFoundError(f"No aggregate published yet for {month}")
    resp.raise_for_status()
    zip_path.write_bytes(resp.content)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(agg_dir)
    zip_path.unlink()
    log("downloaded", month=month, out_dir=str(out))
    return out


def download_months(months: list[str], agg_dir: Path, force: bool = False) -> list[Path]:
    paths = []
    for month in months:
        try:
            paths.append(download_month(month, agg_dir, force=force))
        except FileNotFoundError:
            continue  # future month, nothing published yet - not an error
    return paths
