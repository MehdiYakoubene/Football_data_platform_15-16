from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingest.statsbomb_loader import StatsBombOpenDataLoader, select_competitions
from src.transform.build_dimensions import build_dim_competitions, build_dim_matches, build_dim_players, build_dim_teams
from src.transform.build_facts import add_turnover_flags
from src.transform.clean_events import clean_events
from src.utils.logging import configure_project_logging, get_logger
from src.utils.paths import ANALYTICS_DIR, DUCKDB_PATH, PROCESSED_DIR, ensure_data_dirs


logger = get_logger(__name__)
SCHEMA_VERSION = "1.2.0"
CLEAN_EVENT_REQUIRED_COLUMNS = {"pass_shot_assist", "pass_goal_assist"}
PIPELINE_PRESETS = {
    "top5-europe-2015-2016-ucl": [
        (2, 27),   # Premier League 2015/2016
        (9, 27),   # 1. Bundesliga 2015/2016
        (11, 27),  # La Liga 2015/2016
        (12, 27),  # Serie A 2015/2016
        (7, 27),   # Ligue 1 2015/2016
        (16, 27),  # Champions League 2015/2016
    ],
}
DEFAULT_PRESET = "top5-europe-2015-2016-ucl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Modern Football Data Platform analytics dataset.")
    parser.add_argument("--competition-id", type=int, default=None, help="StatsBomb competition_id to ingest.")
    parser.add_argument("--season-id", type=int, default=None, help="StatsBomb season_id to ingest.")
    parser.add_argument("--preset", choices=sorted(PIPELINE_PRESETS), default=DEFAULT_PRESET, help="Named dataset scope to ingest.")
    parser.add_argument("--competition-limit", type=int, default=None, help="Limit competition-season rows. Default: all.")
    parser.add_argument("--max-matches", type=int, default=0, help="Maximum matches per competition-season. Default 0 means all.")
    parser.add_argument("--demo", action="store_true", help="Fast demo build: first competition-season and 8 matches.")
    parser.add_argument("--refresh", action="store_true", help="Re-download JSON files even when cache exists.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers for match event/lineup ingestion.")
    parser.add_argument("--quiet", action="store_true", help="Do not print build logs in the terminal.")
    parser.add_argument("--log-file", default=None, help="Write build logs to this file, for example logs/build_dataset.log.")
    args = parser.parse_args()
    if args.demo:
        args.competition_limit = 1
        args.max_matches = 8
    return args


def select_competitions_for_args(competitions: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    explicit_filters = args.competition_id is not None or args.season_id is not None or args.competition_limit is not None
    if getattr(args, "preset", None) and not explicit_filters:
        requested_pairs = set(PIPELINE_PRESETS[args.preset])
        selected = [
            row
            for row in competitions
            if (int(row.get("competition_id", -1)), int(row.get("season_id", -1))) in requested_pairs
        ]
        selected_pairs = {(int(row["competition_id"]), int(row["season_id"])) for row in selected}
        missing_pairs = requested_pairs - selected_pairs
        if missing_pairs:
            raise ValueError(f"Preset {args.preset} is missing competition-season pairs in competitions.json: {sorted(missing_pairs)}")
        return sorted(selected, key=lambda row: PIPELINE_PRESETS[args.preset].index((int(row["competition_id"]), int(row["season_id"]))))

    return select_competitions(
        competitions,
        competition_id=args.competition_id,
        season_id=args.season_id,
        limit=args.competition_limit,
    )


def attach_competition_context(match: dict[str, Any], competition_row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(match)
    enriched.setdefault("competition_id", competition_row.get("competition_id"))
    enriched.setdefault("season_id", competition_row.get("season_id"))
    enriched.setdefault("competition_name", competition_row.get("competition_name"))
    enriched.setdefault("season_name", competition_row.get("season_name"))
    return enriched


def time_to_minute(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        minutes, seconds = str(value).split(":", maxsplit=1)
        return int(minutes) + int(seconds) / 60
    except (ValueError, TypeError):
        return None


def build_player_match_minutes(lineup_files: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for lineup_file in lineup_files:
        match_id = lineup_file["match_id"]
        for team in lineup_file.get("lineups", []):
            for player in team.get("lineup", []):
                for position in player.get("positions", []):
                    rows.append(
                        {
                            "match_id": match_id,
                            "team_id": team.get("team_id"),
                            "team_name": team.get("team_name"),
                            "player_id": player.get("player_id"),
                            "player_name": player.get("player_name"),
                            "position": position.get("position"),
                            "from_minute": time_to_minute(position.get("from")),
                            "to_minute": time_to_minute(position.get("to")),
                            "start_reason": position.get("start_reason"),
                            "end_reason": position.get("end_reason"),
                        }
                    )
    return pd.DataFrame(rows)


def limited_matches(matches: list[dict[str, Any]], max_matches: int) -> list[dict[str, Any]]:
    sorted_matches = sorted(matches, key=lambda row: (str(row.get("match_date", "")), int(row.get("match_id", 0))))
    return sorted_matches if max_matches == 0 else sorted_matches[:max_matches]


def write_csv(name: str, df: pd.DataFrame, folder: Path = ANALYTICS_DIR) -> None:
    path = folder / f"{name}.csv"
    df.to_csv(path, index=False)
    logger.info("Wrote %s rows to %s", len(df), path.relative_to(PROJECT_ROOT))


def append_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def processed_match_path(match_id: int) -> Path:
    return PROCESSED_DIR / "matches" / f"{match_id}_events.csv"


def process_match(
    loader: StatsBombOpenDataLoader,
    match_id: int,
    refresh: bool = False,
) -> dict[str, Any]:
    event_cache_path = processed_match_path(match_id)

    cache_is_usable = event_cache_path.exists() and not refresh
    if cache_is_usable:
        clean_event_frame = pd.read_csv(event_cache_path)
        cache_is_usable = CLEAN_EVENT_REQUIRED_COLUMNS.issubset(clean_event_frame.columns)
    if not cache_is_usable:
        events = loader.load_events(match_id, refresh=refresh)
        clean_event_frame = add_turnover_flags(clean_events(events, match_id))
        event_cache_path.parent.mkdir(parents=True, exist_ok=True)
        clean_event_frame.to_csv(event_cache_path, index=False)

    lineups = loader.load_lineups(match_id, refresh=refresh)

    return {
        "match_id": match_id,
        "clean_events": clean_event_frame,
        "lineups": {"match_id": match_id, "lineups": lineups},
    }


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def export_table(conn: duckdb.DuckDBPyConnection, name: str) -> int:
    csv_path = ANALYTICS_DIR / f"{name}.csv"
    parquet_path = ANALYTICS_DIR / f"{name}.parquet"
    conn.execute(f"COPY {name} TO '{sql_path(csv_path)}' (HEADER, DELIMITER ',')")
    conn.execute(f"COPY {name} TO '{sql_path(parquet_path)}' (FORMAT PARQUET)")
    row_count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    logger.info("Wrote %s rows to %s and %s", row_count, csv_path.relative_to(PROJECT_ROOT), parquet_path.relative_to(PROJECT_ROOT))
    return int(row_count)


def write_manifest(manifest: dict[str, Any]) -> None:
    path = ANALYTICS_DIR / "build_manifest.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=True)
    logger.info("Wrote build manifest to %s", path.relative_to(PROJECT_ROOT))


def write_duckdb_and_exports(
    tables: dict[str, pd.DataFrame],
    clean_events_path: Path,
    manifest_context: dict[str, Any],
    started_perf: float,
) -> None:
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()

    with duckdb.connect(str(DUCKDB_PATH)) as conn:
        for name, df in tables.items():
            conn.register("_df", df)
            conn.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _df")
            conn.unregister("_df")

        conn.execute(
            f"""
            CREATE OR REPLACE TABLE clean_events AS
            SELECT * FROM read_csv_auto('{sql_path(clean_events_path)}', header=true)
            """
        )

        conn.execute(
            """
            CREATE OR REPLACE TABLE fact_events AS
            SELECT event_uuid, match_id, event_index, period, timestamp, minute, second, event_type,
                   team_id, team_name, player_id, player_name, position, possession, possession_team_id,
                   possession_team_name, play_pattern, x, y, end_x, end_y,
                   norm_x, norm_y, norm_end_x, norm_end_y,
                   attack_direction_inferred, coordinates_flipped, under_pressure
            FROM clean_events
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE fact_shots AS
            SELECT event_uuid, match_id, event_index, period, timestamp, minute, second, event_type,
                   team_id, team_name, player_id, player_name, position, possession, possession_team_id,
                   possession_team_name, play_pattern, x, y, end_x, end_y,
                   norm_x, norm_y, norm_end_x, norm_end_y,
                   attack_direction_inferred, coordinates_flipped, under_pressure,
                   shot_xg, shot_outcome, shot_body_part, shot_technique, shot_type,
                   shot_outcome = 'Goal' AS is_goal
            FROM clean_events
            WHERE event_type = 'Shot'
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE fact_passes AS
            SELECT event_uuid, match_id, event_index, period, timestamp, minute, second, event_type,
                   team_id, team_name, player_id, player_name, position, possession, possession_team_id,
                   possession_team_name, play_pattern, x, y, end_x, end_y,
                   norm_x, norm_y, norm_end_x, norm_end_y,
                   attack_direction_inferred, coordinates_flipped, under_pressure,
                   pass_complete, pass_outcome, pass_length, pass_angle, pass_height, pass_type,
                   pass_recipient_id, pass_recipient_name, pass_shot_assist, pass_goal_assist,
                   pass_progressive, pass_into_final_third
            FROM clean_events
            WHERE event_type = 'Pass'
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE fact_carries AS
            SELECT event_uuid, match_id, event_index, period, timestamp, minute, second, event_type,
                   team_id, team_name, player_id, player_name, position, possession, possession_team_id,
                   possession_team_name, play_pattern, x, y, end_x, end_y,
                   norm_x, norm_y, norm_end_x, norm_end_y,
                   attack_direction_inferred, coordinates_flipped, under_pressure,
                   carry_progressive, duration
            FROM clean_events
            WHERE event_type = 'Carry'
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE fact_defensive_actions AS
            SELECT event_uuid, match_id, event_index, period, timestamp, minute, second, event_type,
                   team_id, team_name, player_id, player_name, position, possession, possession_team_id,
                   possession_team_name, play_pattern, x, y, end_x, end_y,
                   norm_x, norm_y, norm_end_x, norm_end_y,
                   attack_direction_inferred, coordinates_flipped, under_pressure,
                   event_type = 'Ball Recovery' AS is_ball_recovery,
                   event_type = 'Pressure' AS is_pressure
            FROM clean_events
            WHERE event_type IN ('Pressure', 'Ball Recovery', 'Interception', 'Block', 'Clearance', 'Duel', 'Dribbled Past', 'Foul Committed')
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE player_match_stats AS
            WITH event_features AS (
                SELECT c.*,
                       c.event_type = 'Pass' AND COALESCE(c.pass_shot_assist, FALSE) AS is_key_pass,
                       (
                           SELECT s.shot_xg
                           FROM clean_events s
                           WHERE s.match_id = c.match_id
                             AND s.team_id = c.team_id
                             AND s.possession = c.possession
                             AND s.event_type = 'Shot'
                             AND s.event_index > c.event_index
                           ORDER BY s.event_index
                           LIMIT 1
                       ) AS assisted_shot_xg
                FROM clean_events c
            ),
            match_duration AS (
                SELECT match_id, MAX(minute) + 1 AS match_minutes
                FROM clean_events
                GROUP BY match_id
            ),
            lineup_minutes AS (
                SELECT l.match_id,
                       l.team_id,
                       l.player_id,
                       MODE(l.position) AS lineup_position,
                       SUM(GREATEST(COALESCE(l.to_minute, d.match_minutes) - COALESCE(l.from_minute, 0), 0)) AS lineup_minutes
                FROM player_match_minutes l
                LEFT JOIN match_duration d USING (match_id)
                GROUP BY l.match_id, l.team_id, l.player_id
            ),
            event_stats AS (
                SELECT match_id, team_id, team_name, player_id, player_name,
                       MODE(position) AS event_position,
                       COUNT(DISTINCT minute) AS event_minutes,
                       COUNT(*) AS total_events,
                       SUM(CASE WHEN event_type = 'Shot' THEN 1 ELSE 0 END) AS shots,
                       SUM(COALESCE(shot_xg, 0)) AS xg,
                       SUM(CASE WHEN event_type = 'Shot' AND norm_x >= 102 AND norm_y BETWEEN 18 AND 62 THEN 1 ELSE 0 END) AS shots_in_box,
                       SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) AS passes_attempted,
                       SUM(CASE WHEN pass_complete THEN 1 ELSE 0 END) AS passes_completed,
                       SUM(CASE WHEN pass_progressive THEN 1 ELSE 0 END) AS progressive_passes,
                       SUM(CASE WHEN pass_into_final_third THEN 1 ELSE 0 END) AS passes_into_final_third,
                       SUM(CASE WHEN event_type = 'Pass' AND norm_end_x >= 102 AND norm_end_y BETWEEN 18 AND 62 THEN 1 ELSE 0 END) AS passes_into_box,
                       SUM(CASE WHEN is_key_pass THEN 1 ELSE 0 END) AS key_passes,
                       SUM(CASE WHEN is_key_pass THEN COALESCE(assisted_shot_xg, 0) ELSE 0 END) AS xg_assisted,
                       SUM(CASE WHEN event_type = 'Carry' THEN 1 ELSE 0 END) AS carries,
                       SUM(CASE WHEN carry_progressive THEN 1 ELSE 0 END) AS progressive_carries,
                       SUM(CASE WHEN event_type = 'Carry' AND norm_end_x >= 102 AND norm_end_y BETWEEN 18 AND 62 THEN 1 ELSE 0 END) AS carries_into_box,
                       SUM(CASE WHEN norm_x >= 102 AND norm_y BETWEEN 18 AND 62 THEN 1 ELSE 0 END) AS touches_in_box,
                       SUM(CASE WHEN event_type IN ('Pressure', 'Ball Recovery', 'Interception', 'Block', 'Clearance', 'Duel') THEN 1 ELSE 0 END) AS defensive_actions,
                       SUM(CASE WHEN event_type = 'Ball Recovery' THEN 1 ELSE 0 END) AS ball_recoveries,
                       SUM(CASE WHEN event_type = 'Pressure' THEN 1 ELSE 0 END) AS pressures,
                       SUM(CASE WHEN is_turnover THEN 1 ELSE 0 END) AS turnovers,
                       CASE
                           WHEN SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) > 0
                           THEN ROUND(SUM(CASE WHEN pass_complete THEN 1 ELSE 0 END)::DOUBLE / SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END), 3)
                           ELSE NULL
                       END AS pass_completion_pct
                FROM event_features
                WHERE player_id IS NOT NULL
                GROUP BY match_id, team_id, team_name, player_id, player_name
            )
            SELECT e.match_id, e.team_id, e.team_name, e.player_id, e.player_name,
                   COALESCE(l.lineup_position, e.event_position) AS primary_position,
                   CASE
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%goalkeeper%' THEN 'Goalkeeper'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%back%' THEN 'Defender'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%defensive midfield%' THEN 'Midfielder'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%center midfield%' THEN 'Midfielder'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%midfield%' THEN 'Midfielder'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%wing%' THEN 'Forward'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%forward%' THEN 'Forward'
                       WHEN LOWER(COALESCE(l.lineup_position, e.event_position)) LIKE '%striker%' THEN 'Forward'
                       ELSE 'Other'
                   END AS position_family,
                   ROUND(COALESCE(l.lineup_minutes, e.event_minutes), 2) AS minutes_estimated,
                   e.total_events, e.shots, e.xg, e.shots_in_box, e.passes_attempted, e.passes_completed,
                   e.progressive_passes, e.passes_into_final_third, e.passes_into_box, e.key_passes,
                   e.xg_assisted, e.carries, e.progressive_carries, e.carries_into_box, e.touches_in_box,
                   e.defensive_actions, e.ball_recoveries, e.pressures, e.turnovers, e.pass_completion_pct
            FROM event_stats e
            LEFT JOIN lineup_minutes l
              ON e.match_id = l.match_id
             AND e.team_id = l.team_id
             AND e.player_id = l.player_id
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE player_profile_stats AS
            WITH base AS (
                SELECT player_id,
                       player_name,
                       team_id,
                       team_name,
                       MODE(primary_position) AS primary_position,
                       MODE(position_family) AS position_family,
                       COUNT(DISTINCT match_id) AS matches,
                       SUM(minutes_estimated) AS minutes_estimated,
                       SUM(shots) AS shots,
                       SUM(xg) AS xg,
                       SUM(progressive_passes) AS progressive_passes,
                       SUM(passes_into_final_third) AS passes_into_final_third,
                       SUM(defensive_actions) AS defensive_actions,
                       SUM(pressures) AS pressures,
                       SUM(key_passes) AS key_passes,
                       SUM(xg_assisted) AS xg_assisted,
                       SUM(touches_in_box) AS touches_in_box,
                       SUM(passes_into_box) AS passes_into_box,
                       SUM(carries_into_box) AS carries_into_box,
                       SUM(shots_in_box) AS shots_in_box
                FROM player_match_stats
                GROUP BY player_id, player_name, team_id, team_name
            ),
            per90 AS (
                SELECT *,
                       CASE WHEN minutes_estimated > 0 THEN shots * 90.0 / minutes_estimated ELSE NULL END AS shots_per90,
                       CASE WHEN minutes_estimated > 0 THEN xg * 90.0 / minutes_estimated ELSE NULL END AS xg_per90,
                       CASE WHEN minutes_estimated > 0 THEN progressive_passes * 90.0 / minutes_estimated ELSE NULL END AS progressive_passes_per90,
                       CASE WHEN minutes_estimated > 0 THEN passes_into_final_third * 90.0 / minutes_estimated ELSE NULL END AS passes_into_final_third_per90,
                       CASE WHEN minutes_estimated > 0 THEN defensive_actions * 90.0 / minutes_estimated ELSE NULL END AS defensive_actions_per90,
                       CASE WHEN minutes_estimated > 0 THEN pressures * 90.0 / minutes_estimated ELSE NULL END AS pressures_per90,
                       CASE WHEN minutes_estimated > 0 THEN key_passes * 90.0 / minutes_estimated ELSE NULL END AS key_passes_per90,
                       CASE WHEN minutes_estimated > 0 THEN xg_assisted * 90.0 / minutes_estimated ELSE NULL END AS xg_assisted_per90,
                       CASE WHEN minutes_estimated > 0 THEN touches_in_box * 90.0 / minutes_estimated ELSE NULL END AS touches_in_box_per90,
                       CASE WHEN minutes_estimated > 0 THEN passes_into_box * 90.0 / minutes_estimated ELSE NULL END AS passes_into_box_per90,
                       CASE WHEN minutes_estimated > 0 THEN carries_into_box * 90.0 / minutes_estimated ELSE NULL END AS carries_into_box_per90,
                       CASE WHEN minutes_estimated > 0 THEN shots_in_box * 90.0 / minutes_estimated ELSE NULL END AS shots_in_box_per90
                FROM base
            )
            SELECT *,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY shots_per90) AS shots_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY xg_per90) AS xg_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY progressive_passes_per90) AS progressive_passes_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY passes_into_final_third_per90) AS passes_into_final_third_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY defensive_actions_per90) AS defensive_actions_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY pressures_per90) AS pressures_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY key_passes_per90) AS key_passes_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY xg_assisted_per90) AS xg_assisted_per90_pctile,
                   PERCENT_RANK() OVER (PARTITION BY position_family ORDER BY touches_in_box_per90) AS touches_in_box_per90_pctile
            FROM per90
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE TABLE team_match_stats AS
            SELECT match_id, team_id, team_name,
                   COUNT(*) AS total_events,
                   COUNT(DISTINCT possession) AS possessions,
                   SUM(CASE WHEN event_type = 'Shot' THEN 1 ELSE 0 END) AS shots,
                   SUM(COALESCE(shot_xg, 0)) AS xg,
                   SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) AS passes_attempted,
                   SUM(CASE WHEN pass_complete THEN 1 ELSE 0 END) AS passes_completed,
                   SUM(CASE WHEN pass_progressive THEN 1 ELSE 0 END) AS progressive_passes,
                   SUM(CASE WHEN pass_into_final_third THEN 1 ELSE 0 END) AS passes_into_final_third,
                   SUM(CASE WHEN event_type = 'Carry' THEN 1 ELSE 0 END) AS carries,
                   SUM(CASE WHEN carry_progressive THEN 1 ELSE 0 END) AS progressive_carries,
                   SUM(CASE WHEN event_type IN ('Pressure', 'Ball Recovery', 'Interception', 'Block', 'Clearance', 'Duel') THEN 1 ELSE 0 END) AS defensive_actions,
                   SUM(CASE WHEN event_type = 'Ball Recovery' THEN 1 ELSE 0 END) AS ball_recoveries,
                   SUM(CASE WHEN event_type = 'Pressure' THEN 1 ELSE 0 END) AS pressures,
                   SUM(CASE WHEN is_turnover THEN 1 ELSE 0 END) AS turnovers,
                   CASE
                       WHEN SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) > 0
                       THEN ROUND(SUM(CASE WHEN pass_complete THEN 1 ELSE 0 END)::DOUBLE / SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END), 3)
                       ELSE NULL
                   END AS pass_completion_pct
            FROM clean_events
            GROUP BY match_id, team_id, team_name
            """
        )

        table_counts: dict[str, int] = {}
        for name in (
            "dim_competitions",
            "dim_matches",
            "dim_teams",
            "dim_players",
            "player_match_minutes",
            "fact_events",
            "fact_shots",
            "fact_passes",
            "fact_carries",
            "fact_defensive_actions",
            "player_match_stats",
            "player_profile_stats",
            "team_match_stats",
        ):
            table_counts[name] = export_table(conn, name)

        events_per_match = conn.execute(
            """
            SELECT MIN(event_count), AVG(event_count), MAX(event_count)
            FROM (
                SELECT match_id, COUNT(*) AS event_count
                FROM fact_events
                GROUP BY match_id
            )
            """
        ).fetchone()
        manifest = {
            **manifest_context,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(time.perf_counter() - started_perf, 2),
            "schema_version": SCHEMA_VERSION,
            "duckdb_path": str(DUCKDB_PATH.relative_to(PROJECT_ROOT)),
            "table_counts": table_counts,
            "events_per_match": {
                "min": int(events_per_match[0] or 0),
                "avg": float(events_per_match[1] or 0),
                "max": int(events_per_match[2] or 0),
            },
        }
        write_manifest(manifest)
    logger.info("Wrote DuckDB database to %s", DUCKDB_PATH.relative_to(PROJECT_ROOT))


def build_dataset(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    started = time.perf_counter()
    started_at_utc = datetime.now(timezone.utc).isoformat()
    ensure_data_dirs()
    loader = StatsBombOpenDataLoader()

    competitions = loader.load_competitions(refresh=args.refresh)
    selected_competitions = select_competitions_for_args(competitions, args)
    if not selected_competitions:
        raise ValueError("No competition-season found for the provided filters.")

    all_matches: list[dict[str, Any]] = []
    match_ids: list[int] = []
    lineup_files: list[dict[str, Any]] = []
    clean_events_path = PROCESSED_DIR / "clean_events.csv"
    if clean_events_path.exists():
        clean_events_path.unlink()

    for competition in selected_competitions:
        competition_id = int(competition["competition_id"])
        season_id = int(competition["season_id"])
        logger.info("Loading matches for %s / %s", competition.get("competition_name"), competition.get("season_name"))
        matches = loader.load_matches(competition_id, season_id, refresh=args.refresh)
        matches = [attach_competition_context(match, competition) for match in limited_matches(matches, args.max_matches)]
        all_matches.extend(matches)
        match_ids.extend(int(match["match_id"]) for match in matches)

    total_matches = len(match_ids)
    workers = max(1, int(getattr(args, "workers", 8)))
    logger.info("Processing %s matches with %s workers.", total_matches, workers)

    if workers == 1:
        results = (
            process_match(loader, match_id, refresh=args.refresh)
            for match_id in match_ids
        )
        for index, result in enumerate(results, start=1):
            append_csv(result["clean_events"], clean_events_path)
            lineup_files.append(result["lineups"])
            logger.info("Processed match_id=%s (%s/%s)", result["match_id"], index, total_matches)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(process_match, loader, match_id, args.refresh)
                for match_id in match_ids
            ]
            for index, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                append_csv(result["clean_events"], clean_events_path)
                lineup_files.append(result["lineups"])
                logger.info("Processed match_id=%s (%s/%s)", result["match_id"], index, total_matches)

    dim_competitions = build_dim_competitions(selected_competitions)
    dim_matches = build_dim_matches(all_matches)
    empty_events = pd.DataFrame(columns=["team_id", "team_name", "player_id", "player_name", "match_id"])
    dim_teams = build_dim_teams(dim_matches, empty_events)
    dim_players = build_dim_players(lineup_files, empty_events)
    player_match_minutes = build_player_match_minutes(lineup_files)

    tables = {
        "dim_competitions": dim_competitions,
        "dim_matches": dim_matches,
        "dim_teams": dim_teams,
        "dim_players": dim_players,
        "player_match_minutes": player_match_minutes,
    }

    for name, df in tables.items():
        write_csv(name, df)
    manifest_context = {
        "started_at_utc": started_at_utc,
        "build_mode": "demo" if args.demo else "full_or_filtered",
        "args": vars(args),
        "source": "StatsBomb Open Data",
        "competition_seasons_loaded": len(selected_competitions),
        "matches_loaded": len(all_matches),
        "competitions": [
            {
                "competition_id": row.get("competition_id"),
                "season_id": row.get("season_id"),
                "competition_name": row.get("competition_name"),
                "season_name": row.get("season_name"),
            }
            for row in selected_competitions
        ],
    }
    write_duckdb_and_exports(tables, clean_events_path, manifest_context, started)
    return tables


def main() -> None:
    args = parse_args()
    configure_project_logging(quiet=args.quiet, log_file=args.log_file)
    build_dataset(args)


if __name__ == "__main__":
    main()
