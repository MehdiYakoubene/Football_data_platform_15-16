from __future__ import annotations

from typing import Any

import pandas as pd

from src.transform.clean_events import nested_name


def value_from(value: Any, *keys: str) -> Any:
    if not isinstance(value, dict):
        return None
    for key in keys:
        if key in value:
            return value[key]
    return None


def build_dim_competitions(competitions: list[dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "competition_id",
        "season_id",
        "competition_name",
        "season_name",
        "country_name",
        "competition_gender",
        "match_updated",
        "match_available",
    ]
    return pd.DataFrame(competitions).reindex(columns=columns).drop_duplicates()


def build_dim_matches(match_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for match in match_rows:
        rows.append(
            {
                "match_id": match.get("match_id"),
                "competition_id": value_from(match.get("competition"), "competition_id", "id") or match.get("competition_id"),
                "season_id": value_from(match.get("season"), "season_id", "id") or match.get("season_id"),
                "competition_name": value_from(match.get("competition"), "competition_name", "name") or match.get("competition_name"),
                "season_name": value_from(match.get("season"), "season_name", "name") or match.get("season_name"),
                "match_date": match.get("match_date"),
                "kick_off": match.get("kick_off"),
                "home_team_id": value_from(match.get("home_team"), "home_team_id", "id"),
                "home_team_name": value_from(match.get("home_team"), "home_team_name", "name"),
                "away_team_id": value_from(match.get("away_team"), "away_team_id", "id"),
                "away_team_name": value_from(match.get("away_team"), "away_team_name", "name"),
                "home_score": match.get("home_score"),
                "away_score": match.get("away_score"),
                "match_status": match.get("match_status"),
                "last_updated": match.get("last_updated"),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["match_id"]).sort_values("match_date")


def build_dim_teams(matches: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    match_teams = pd.concat(
        [
            matches[["home_team_id", "home_team_name"]].rename(columns={"home_team_id": "team_id", "home_team_name": "team_name"}),
            matches[["away_team_id", "away_team_name"]].rename(columns={"away_team_id": "team_id", "away_team_name": "team_name"}),
        ],
        ignore_index=True,
    )
    event_teams = events[["team_id", "team_name"]] if not events.empty else pd.DataFrame(columns=["team_id", "team_name"])
    return (
        pd.concat([match_teams, event_teams], ignore_index=True)
        .dropna(subset=["team_id"])
        .drop_duplicates(subset=["team_id"])
        .sort_values("team_name")
    )


def build_dim_players(lineups: list[dict[str, Any]], events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for lineup_file in lineups:
        match_id = lineup_file.get("match_id")
        for team in lineup_file.get("lineups", []):
            for player in team.get("lineup", []):
                rows.append(
                    {
                        "player_id": player.get("player_id"),
                        "player_name": player.get("player_name"),
                        "player_nickname": player.get("player_nickname"),
                        "country_name": nested_name(player.get("country")),
                        "team_id": team.get("team_id"),
                        "team_name": team.get("team_name"),
                        "match_id": match_id,
                    }
                )

    lineup_players = pd.DataFrame(rows)
    event_players = (
        events[["player_id", "player_name", "team_id", "team_name", "match_id"]].assign(player_nickname=None, country_name=None)
        if not events.empty
        else pd.DataFrame(columns=["player_id", "player_name", "team_id", "team_name", "match_id", "player_nickname", "country_name"])
    )
    players = pd.concat([lineup_players, event_players], ignore_index=True)
    if players.empty:
        return players
    return (
        players.dropna(subset=["player_id"])
        .sort_values(["player_name", "match_id"])
        .drop_duplicates(subset=["player_id", "team_id"], keep="first")
        .sort_values("player_name")
    )
