"""month_url/last_n_months are pure functions - test offline, no network.
download_month's actual HTTP call was verified live by hand against the
real CloudFront host (large files, not something to re-download in CI).
"""

from datetime import date

from monitor.fetch import last_n_months, month_url


def test_month_url():
    assert month_url("2026-10") == (
        "https://d3vax7phxnku8l.cloudfront.net/agg/pqt/data/tdb_data/"
        "global___full/aggregations/aggregated-complete-2026-10-01-parquet.zip"
    )


def test_last_n_months_oldest_first():
    assert last_n_months(3, today=date(2026, 11, 12)) == ["2026-09", "2026-10", "2026-11"]


def test_last_n_months_crosses_year_boundary():
    assert last_n_months(3, today=date(2026, 1, 15)) == ["2025-11", "2025-12", "2026-01"]


def test_last_n_months_single():
    assert last_n_months(1, today=date(2026, 11, 12)) == ["2026-11"]
