from __future__ import annotations

import pandas as pd

from src.transform.clean_events import DEFENSIVE_EVENT_TYPES, TURNOVER_EVENT_TYPES


CORE_EVENT_COLUMNS = [
    "event_uuid",
    "match_id",
    "event_index",
    "period",
    "timestamp",
    "minute",
    "second",
    "event_type",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "possession",
    "possession_team_id",
    "possession_team_name",
    "play_pattern",
    "x",
    "y",
    "end_x",
    "end_y",
    "under_pressure",
]


def build_fact_events(events: pd.DataFrame) -> pd.DataFrame:
    return events.reindex(columns=CORE_EVENT_COLUMNS).copy()


def build_fact_shots(events: pd.DataFrame) -> pd.DataFrame:
    columns = CORE_EVENT_COLUMNS + ["shot_xg", "shot_outcome", "shot_body_part", "shot_technique", "shot_type"]
    shots = events.loc[events["event_type"].eq("Shot")].reindex(columns=columns).copy()
    shots["is_goal"] = shots["shot_outcome"].eq("Goal")
    return shots


def build_fact_passes(events: pd.DataFrame) -> pd.DataFrame:
    columns = CORE_EVENT_COLUMNS + [
        "pass_complete",
        "pass_outcome",
        "pass_length",
        "pass_angle",
        "pass_height",
        "pass_type",
        "pass_recipient_id",
        "pass_recipient_name",
        "pass_shot_assist",
        "pass_goal_assist",
        "pass_progressive",
        "pass_into_final_third",
    ]
    return events.loc[events["event_type"].eq("Pass")].reindex(columns=columns).copy()


def build_fact_carries(events: pd.DataFrame) -> pd.DataFrame:
    columns = CORE_EVENT_COLUMNS + ["carry_progressive", "duration"]
    return events.loc[events["event_type"].eq("Carry")].reindex(columns=columns).copy()


def build_fact_defensive_actions(events: pd.DataFrame) -> pd.DataFrame:
    defensive = events.loc[events["event_type"].isin(DEFENSIVE_EVENT_TYPES), CORE_EVENT_COLUMNS].copy()
    defensive["is_ball_recovery"] = defensive["event_type"].eq("Ball Recovery")
    defensive["is_pressure"] = defensive["event_type"].eq("Pressure")
    return defensive


def add_turnover_flags(events: pd.DataFrame) -> pd.DataFrame:
    enriched = events.copy()
    enriched["is_turnover"] = enriched["event_type"].isin(TURNOVER_EVENT_TYPES) | (
        enriched["event_type"].eq("Pass") & enriched["pass_outcome"].notna()
    )
    return enriched
