from __future__ import annotations

import pandas as pd


def build_team_match_stats(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    grouped = events.groupby(["match_id", "team_id", "team_name"], dropna=False)
    stats = grouped.agg(
        total_events=("event_uuid", "count"),
        possessions=("possession", "nunique"),
        shots=("event_type", lambda s: int((s == "Shot").sum())),
        xg=("shot_xg", "sum"),
        passes_attempted=("event_type", lambda s: int((s == "Pass").sum())),
        passes_completed=("pass_complete", "sum"),
        progressive_passes=("pass_progressive", "sum"),
        passes_into_final_third=("pass_into_final_third", "sum"),
        carries=("event_type", lambda s: int((s == "Carry").sum())),
        progressive_carries=("carry_progressive", "sum"),
        defensive_actions=("event_type", lambda s: int(s.isin(["Pressure", "Ball Recovery", "Interception", "Block", "Clearance", "Duel"]).sum())),
        ball_recoveries=("event_type", lambda s: int((s == "Ball Recovery").sum())),
        pressures=("event_type", lambda s: int((s == "Pressure").sum())),
        turnovers=("is_turnover", "sum"),
    )
    stats = stats.reset_index()
    stats["pass_completion_pct"] = (stats["passes_completed"] / stats["passes_attempted"]).where(stats["passes_attempted"] > 0).round(3)
    return stats.sort_values(["match_id", "team_name"])
