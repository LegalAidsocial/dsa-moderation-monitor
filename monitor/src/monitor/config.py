"""Settings, read from environment variables only."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """All settings for a run."""

    data_dir: Path
    agg_dir: Path
    out_dir: Path
    country: str
    memory_limit: str


def load_settings() -> Settings:
    """Build Settings from MONITOR_* environment variables."""
    return Settings(
        data_dir=Path(os.environ.get("MONITOR_DATA_DIR", "data")),
        agg_dir=Path(os.environ.get("MONITOR_AGG_DIR", "data/agg")),
        out_dir=Path(os.environ.get("MONITOR_OUT_DIR", "out")),
        country=os.environ.get("MONITOR_COUNTRY", "DE"),
        memory_limit=os.environ.get("MONITOR_MEMORY_LIMIT", "4GB"),
    )