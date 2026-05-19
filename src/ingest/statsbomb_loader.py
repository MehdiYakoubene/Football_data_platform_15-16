from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.utils.logging import get_logger
from src.utils.paths import RAW_DIR, ensure_data_dirs


logger = get_logger(__name__)


class StatsBombLoaderError(RuntimeError):
    """Raised when a StatsBomb Open Data file cannot be read or downloaded."""


@dataclass(frozen=True)
class StatsBombOpenDataLoader:
    """Read StatsBomb Open Data from a local cache, downloading missing JSON files."""

    raw_dir: Path = RAW_DIR
    base_url: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    timeout: int = 45

    def __post_init__(self) -> None:
        ensure_data_dirs()

    def load_competitions(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self._load_json("competitions.json", refresh=refresh)

    def load_matches(self, competition_id: int, season_id: int, refresh: bool = False) -> list[dict[str, Any]]:
        rel_path = f"matches/{competition_id}/{season_id}.json"
        return self._load_json(rel_path, refresh=refresh)

    def load_events(self, match_id: int, refresh: bool = False) -> list[dict[str, Any]]:
        return self._load_json(f"events/{match_id}.json", refresh=refresh)

    def load_lineups(self, match_id: int, refresh: bool = False) -> list[dict[str, Any]]:
        return self._load_json(f"lineups/{match_id}.json", refresh=refresh)

    def _load_json(self, relative_path: str, refresh: bool = False) -> list[dict[str, Any]]:
        local_path = self.raw_dir / relative_path
        if local_path.exists() and not refresh:
            return self._read_local_json(local_path)

        try:
            return self._download_json(relative_path, local_path)
        except requests.RequestException as exc:
            if local_path.exists():
                logger.warning("Network failed for %s, falling back to cache.", relative_path)
                return self._read_local_json(local_path)
            raise StatsBombLoaderError(f"Could not download {relative_path}. Check your connection or pre-populate data/raw.") from exc

    @staticmethod
    def _read_local_json(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise StatsBombLoaderError(f"Expected a JSON list in {path}")
        return data

    def _download_json(self, relative_path: str, local_path: Path) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{relative_path}"
        logger.info("Downloading %s", url)
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise StatsBombLoaderError(f"Expected a JSON list at {url}")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        with local_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=True)
        return data


def select_competitions(
    competitions: list[dict[str, Any]],
    competition_id: int | None = None,
    season_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter competition-season rows while keeping deterministic ordering."""
    selected = []
    for row in competitions:
        if competition_id is not None and int(row.get("competition_id", -1)) != competition_id:
            continue
        if season_id is not None and int(row.get("season_id", -1)) != season_id:
            continue
        selected.append(row)

    selected = sorted(
        selected,
        key=lambda item: (
            str(item.get("competition_name", "")),
            str(item.get("season_name", "")),
            int(item.get("competition_id", 0)),
            int(item.get("season_id", 0)),
        ),
    )
    return selected[:limit] if limit is not None else selected
