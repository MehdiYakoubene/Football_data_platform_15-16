from __future__ import annotations

import pandas as pd


def build_xg_timeline(shots: pd.DataFrame) -> pd.DataFrame:
    if shots.empty:
        return pd.DataFrame(columns=["match_id", "team_name", "minute", "shot_xg", "cumulative_xg"])

    timeline = shots[["match_id", "team_name", "minute", "second", "shot_xg", "player_name", "shot_outcome"]].copy()
    timeline["shot_xg"] = timeline["shot_xg"].fillna(0.0)
    timeline = timeline.sort_values(["match_id", "team_name", "minute", "second"])
    timeline["cumulative_xg"] = timeline.groupby(["match_id", "team_name"])["shot_xg"].cumsum()
    return timeline
