from __future__ import annotations

from pathlib import Path
import json

import duckdb
import pandas as pd

from src.utils.paths import ANALYTICS_DIR, DUCKDB_PATH


TABLE_FILES = {
    "dim_competitions": ANALYTICS_DIR / "dim_competitions.csv",
    "dim_matches": ANALYTICS_DIR / "dim_matches.csv",
    "dim_teams": ANALYTICS_DIR / "dim_teams.csv",
    "dim_players": ANALYTICS_DIR / "dim_players.csv",
    "player_match_minutes": ANALYTICS_DIR / "player_match_minutes.csv",
    "fact_events": ANALYTICS_DIR / "fact_events.csv",
    "fact_shots": ANALYTICS_DIR / "fact_shots.csv",
    "fact_passes": ANALYTICS_DIR / "fact_passes.csv",
    "fact_carries": ANALYTICS_DIR / "fact_carries.csv",
    "fact_defensive_actions": ANALYTICS_DIR / "fact_defensive_actions.csv",
    "player_match_stats": ANALYTICS_DIR / "player_match_stats.csv",
    "player_profile_stats": ANALYTICS_DIR / "player_profile_stats.csv",
    "team_match_stats": ANALYTICS_DIR / "team_match_stats.csv",
}

MANIFEST_PATH = ANALYTICS_DIR / "build_manifest.json"


def analytics_ready() -> bool:
    return any(path.exists() for path in TABLE_FILES.values())


def duckdb_ready() -> bool:
    return DUCKDB_PATH.exists()


def load_table(name: str) -> pd.DataFrame:
    path = TABLE_FILES.get(name)
    if path is None:
        raise KeyError(f"Unknown analytics table: {name}")
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def table_path(name: str) -> Path:
    if name not in TABLE_FILES:
        raise KeyError(f"Unknown analytics table: {name}")
    return TABLE_FILES[name]


def duckdb_path() -> Path:
    return DUCKDB_PATH


def load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def query_df(sql: str, params: list[object] | tuple[object, ...] | None = None) -> pd.DataFrame:
    if not DUCKDB_PATH.exists():
        return pd.DataFrame()
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
        return conn.execute(sql, params or []).df()


def load_filtered_table(table: str, filters: dict[str, object], limit: int | None = None) -> pd.DataFrame:
    if table not in TABLE_FILES:
        raise KeyError(f"Unknown analytics table: {table}")

    clauses: list[str] = []
    params: list[object] = []
    for column, value in filters.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            values = list(value)
            if not values:
                continue
            placeholders = ", ".join(["?"] * len(values))
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)
        else:
            clauses.append(f"{column} = ?")
            params.append(value)

    where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
    return query_df(f"SELECT * FROM {table}{where_clause}{limit_clause}", params)
