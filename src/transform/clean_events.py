from __future__ import annotations

import math
from typing import Any

import pandas as pd


PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
GOAL_CENTER = (PITCH_LENGTH, PITCH_WIDTH / 2)


def nested_id(value: Any) -> int | None:
    return value.get("id") if isinstance(value, dict) else None


def nested_name(value: Any) -> str | None:
    return value.get("name") if isinstance(value, dict) else None


def coord(location: Any, index: int) -> float | None:
    if isinstance(location, list) and len(location) > index:
        value = location[index]
        return float(value) if value is not None else None
    return None


def distance_to_goal(x: float | None, y: float | None) -> float | None:
    if x is None or y is None or pd.isna(x) or pd.isna(y):
        return None
    return math.dist((float(x), float(y)), GOAL_CENTER)


def normalize_x(x: float | None, flip: bool) -> float | None:
    if x is None or pd.isna(x):
        return None
    return PITCH_LENGTH - float(x) if flip else float(x)


def normalize_y(y: float | None, flip: bool) -> float | None:
    if y is None or pd.isna(y):
        return None
    return PITCH_WIDTH - float(y) if flip else float(y)


def is_progressive(start_x: float | None, start_y: float | None, end_x: float | None, end_y: float | None) -> bool:
    """Approximation: action is progressive when distance to goal falls by at least 25%."""
    start_distance = distance_to_goal(start_x, start_y)
    end_distance = distance_to_goal(end_x, end_y)
    if start_distance is None or end_distance is None or start_distance == 0:
        return False
    return (start_distance - end_distance) / start_distance >= 0.25


def infer_attack_direction(events: pd.DataFrame) -> pd.DataFrame:
    """Add normalized coordinates so each team-period attacks toward x=120.

    StatsBomb event data is often already oriented for analysis. This inference keeps
    that behavior when shots are mostly near x=120, and flips only team-periods that
    look oriented toward x=0 based on shots or average ball movement.
    """
    if events.empty:
        return events

    enriched = events.copy()
    enriched["attack_direction_inferred"] = "left_to_right"
    enriched["coordinates_flipped"] = False

    for keys, group in enriched.groupby(["match_id", "team_id", "period"], dropna=False):
        flip = False
        shot_x = group.loc[group["event_type"].eq("Shot"), "x"].dropna()
        if not shot_x.empty:
            flip = bool(shot_x.median() < PITCH_LENGTH / 2)
        else:
            movement = group.loc[group["event_type"].isin(["Pass", "Carry"]), ["x", "end_x"]].dropna()
            if not movement.empty:
                flip = bool((movement["end_x"] - movement["x"]).median() < 0)

        mask = (
            enriched["match_id"].eq(keys[0])
            & enriched["team_id"].eq(keys[1])
            & enriched["period"].eq(keys[2])
        )
        enriched.loc[mask, "coordinates_flipped"] = flip
        enriched.loc[mask, "attack_direction_inferred"] = "right_to_left" if flip else "left_to_right"

    enriched["norm_x"] = [normalize_x(x, flip) for x, flip in zip(enriched["x"], enriched["coordinates_flipped"])]
    enriched["norm_y"] = [normalize_y(y, flip) for y, flip in zip(enriched["y"], enriched["coordinates_flipped"])]
    enriched["norm_end_x"] = [normalize_x(x, flip) for x, flip in zip(enriched["end_x"], enriched["coordinates_flipped"])]
    enriched["norm_end_y"] = [normalize_y(y, flip) for y, flip in zip(enriched["end_y"], enriched["coordinates_flipped"])]
    return enriched


def add_progression_flags(events: pd.DataFrame) -> pd.DataFrame:
    enriched = events.copy()
    enriched["carry_progressive"] = enriched.apply(
        lambda row: bool(
            row["event_type"] == "Carry"
            and is_progressive(row["norm_x"], row["norm_y"], row["norm_end_x"], row["norm_end_y"])
        ),
        axis=1,
    )
    enriched["pass_progressive"] = enriched.apply(
        lambda row: bool(
            row["event_type"] == "Pass"
            and is_progressive(row["norm_x"], row["norm_y"], row["norm_end_x"], row["norm_end_y"])
        ),
        axis=1,
    )
    enriched["pass_into_final_third"] = enriched.apply(
        lambda row: bool(
            row["event_type"] == "Pass"
            and pd.notna(row["norm_x"])
            and pd.notna(row["norm_end_x"])
            and row["norm_x"] < 80 <= row["norm_end_x"]
        ),
        axis=1,
    )
    return enriched


def clean_events(events: list[dict[str, Any]], match_id: int) -> pd.DataFrame:
    """Flatten relevant StatsBomb event fields into an analytics-ready event table."""
    rows: list[dict[str, Any]] = []

    for event in events:
        event_type = nested_name(event.get("type"))
        start_x = coord(event.get("location"), 0)
        start_y = coord(event.get("location"), 1)
        pass_payload = event.get("pass") if isinstance(event.get("pass"), dict) else {}
        shot_payload = event.get("shot") if isinstance(event.get("shot"), dict) else {}
        carry_payload = event.get("carry") if isinstance(event.get("carry"), dict) else {}

        pass_end_x = coord(pass_payload.get("end_location"), 0)
        pass_end_y = coord(pass_payload.get("end_location"), 1)
        carry_end_x = coord(carry_payload.get("end_location"), 0)
        carry_end_y = coord(carry_payload.get("end_location"), 1)
        shot_end_x = coord(shot_payload.get("end_location"), 0)
        shot_end_y = coord(shot_payload.get("end_location"), 1)

        end_x = pass_end_x if event_type == "Pass" else carry_end_x if event_type == "Carry" else shot_end_x
        end_y = pass_end_y if event_type == "Pass" else carry_end_y if event_type == "Carry" else shot_end_y

        pass_outcome = nested_name(pass_payload.get("outcome"))
        pass_recipient = pass_payload.get("recipient") if isinstance(pass_payload.get("recipient"), dict) else {}

        rows.append(
            {
                "event_uuid": event.get("id"),
                "match_id": match_id,
                "event_index": event.get("index"),
                "period": event.get("period"),
                "timestamp": event.get("timestamp"),
                "minute": event.get("minute"),
                "second": event.get("second"),
                "event_type_id": nested_id(event.get("type")),
                "event_type": event_type,
                "possession": event.get("possession"),
                "possession_team_id": nested_id(event.get("possession_team")),
                "possession_team_name": nested_name(event.get("possession_team")),
                "play_pattern": nested_name(event.get("play_pattern")),
                "team_id": nested_id(event.get("team")),
                "team_name": nested_name(event.get("team")),
                "player_id": nested_id(event.get("player")),
                "player_name": nested_name(event.get("player")),
                "position": nested_name(event.get("position")),
                "x": start_x,
                "y": start_y,
                "end_x": end_x,
                "end_y": end_y,
                "duration": event.get("duration"),
                "under_pressure": bool(event.get("under_pressure", False)),
                "shot_xg": shot_payload.get("statsbomb_xg"),
                "shot_outcome": nested_name(shot_payload.get("outcome")),
                "shot_body_part": nested_name(shot_payload.get("body_part")),
                "shot_technique": nested_name(shot_payload.get("technique")),
                "shot_type": nested_name(shot_payload.get("type")),
                "pass_outcome": pass_outcome,
                "pass_complete": bool(event_type == "Pass" and pass_outcome is None),
                "pass_length": pass_payload.get("length"),
                "pass_angle": pass_payload.get("angle"),
                "pass_height": nested_name(pass_payload.get("height")),
                "pass_type": nested_name(pass_payload.get("type")),
                "pass_recipient_id": pass_recipient.get("id"),
                "pass_recipient_name": pass_recipient.get("name"),
                "pass_shot_assist": bool(pass_payload.get("shot_assist", False)),
                "pass_goal_assist": bool(pass_payload.get("goal_assist", False)),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return add_progression_flags(infer_attack_direction(frame))


TURNOVER_EVENT_TYPES = {"Dispossessed", "Miscontrol", "Error"}
DEFENSIVE_EVENT_TYPES = {
    "Pressure",
    "Ball Recovery",
    "Interception",
    "Block",
    "Clearance",
    "Duel",
    "Dribbled Past",
    "Foul Committed",
}
