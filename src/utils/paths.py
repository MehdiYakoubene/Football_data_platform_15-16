from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYTICS_DIR = DATA_DIR / "analytics"
DUCKDB_PATH = ANALYTICS_DIR / "football_analytics.duckdb"


def ensure_data_dirs() -> None:
    """Create the local data directories used by the platform."""
    for path in (RAW_DIR, PROCESSED_DIR, ANALYTICS_DIR):
        path.mkdir(parents=True, exist_ok=True)
