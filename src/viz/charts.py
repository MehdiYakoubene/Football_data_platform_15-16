from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.metrics.match_metrics import build_xg_timeline


def xg_timeline_chart(shots: pd.DataFrame) -> go.Figure:
    timeline = build_xg_timeline(shots)
    fig = go.Figure()
    if not timeline.empty:
        for team, group in timeline.groupby("team_name"):
            fig.add_trace(
                go.Scatter(
                    x=group["minute"],
                    y=group["cumulative_xg"],
                    mode="lines+markers",
                    name=str(team),
                    hovertemplate="%{x}' - xG cumule %{y:.2f}<extra></extra>",
                )
            )
    fig.update_layout(
        title="xG timeline",
        xaxis_title="Minute",
        yaxis_title="xG cumule",
        height=420,
        margin=dict(l=20, r=20, t=55, b=35),
    )
    return fig


def comparative_bar(df: pd.DataFrame, x: str, y: str, title: str) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = px.bar(df, x=x, y=y, color=x, title=title, text_auto=".2s")
    fig.update_layout(showlegend=False, height=420, margin=dict(l=20, r=20, t=55, b=80))
    return fig


def top_players_bar(df: pd.DataFrame, metric: str, title: str, top_n: int = 15) -> go.Figure:
    if df.empty or metric not in df.columns:
        return go.Figure()
    ranking = df.groupby(["player_id", "player_name"], as_index=False)[metric].sum().nlargest(top_n, metric)
    fig = px.bar(ranking, x=metric, y="player_name", orientation="h", title=title, text_auto=".2s")
    fig.update_layout(yaxis=dict(autorange="reversed"), height=520, margin=dict(l=20, r=20, t=55, b=35))
    return fig


def player_radar_chart(player_row: pd.Series, benchmark: pd.DataFrame, metrics: list[str], title: str) -> go.Figure:
    fig = go.Figure()
    if benchmark.empty or player_row.empty:
        return fig

    labels = [metric.replace("_pctile", "").replace("_per90", "").replace("_", " ").title() for metric in metrics]
    player_values = [float(player_row.get(metric, 0) or 0) for metric in metrics]
    avg_values = [float(benchmark.loc[benchmark["profile"].eq("Position average"), metric].iloc[0]) for metric in metrics]
    top_values = [float(benchmark.loc[benchmark["profile"].eq("Top 10 pct"), metric].iloc[0]) for metric in metrics]

    for name, values, color in (
        ("Joueur", player_values, "#1f77b4"),
        ("Moyenne poste", avg_values, "#8c8c8c"),
        ("Top 10 pct poste", top_values, "#2ca02c"),
    ):
        fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=labels + [labels[0]],
                fill="toself" if name == "Joueur" else None,
                name=name,
                line=dict(color=color),
            )
        )

    fig.update_layout(
        title=title,
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        height=520,
        margin=dict(l=30, r=30, t=60, b=30),
    )
    return fig
