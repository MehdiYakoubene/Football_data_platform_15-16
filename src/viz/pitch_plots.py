from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


PITCH_LENGTH = 120
PITCH_WIDTH = 80


def coord_column(df: pd.DataFrame, normalized: str, raw: str) -> str:
    return normalized if normalized in df.columns else raw


def add_pitch_layout(fig: go.Figure, title: str | None = None) -> go.Figure:
    line_color = "#d6dde5"
    shapes = [
        dict(type="rect", x0=0, y0=0, x1=PITCH_LENGTH, y1=PITCH_WIDTH, line=dict(color=line_color, width=2)),
        dict(type="line", x0=60, y0=0, x1=60, y1=PITCH_WIDTH, line=dict(color=line_color, width=1)),
        dict(type="circle", x0=50, y0=30, x1=70, y1=50, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=0, y0=18, x1=18, y1=62, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=102, y0=18, x1=120, y1=62, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=0, y0=30, x1=6, y1=50, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=114, y0=30, x1=120, y1=50, line=dict(color=line_color, width=1)),
    ]
    fig.update_layout(
        title=title,
        shapes=shapes,
        plot_bgcolor="#0e1b2a",
        paper_bgcolor="#0e1b2a",
        font=dict(color="#f7fafc"),
        height=520,
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis=dict(range=[0, PITCH_LENGTH], visible=False, fixedrange=True),
        yaxis=dict(range=[PITCH_WIDTH, 0], visible=False, fixedrange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def shot_map(shots: pd.DataFrame, title: str = "Shot map") -> go.Figure:
    fig = go.Figure()
    if not shots.empty:
        x_col = coord_column(shots, "norm_x", "x")
        y_col = coord_column(shots, "norm_y", "y")
        size = shots["shot_xg"].fillna(0.02).clip(lower=0.02) * 55 + 8
        fig.add_trace(
            go.Scatter(
                x=shots[x_col],
                y=shots[y_col],
                mode="markers",
                marker=dict(size=size, color=shots["shot_xg"].fillna(0), colorscale="YlOrRd", showscale=True, colorbar=dict(title="xG")),
                text=shots["player_name"],
                customdata=shots[["team_name", "minute", "shot_outcome", "shot_xg"]].fillna(""),
                hovertemplate="<b>%{text}</b><br>%{customdata[0]} - %{customdata[1]}'<br>%{customdata[2]}<br>xG %{customdata[3]}<extra></extra>",
            )
        )
    return add_pitch_layout(fig, title)


def pass_map(passes: pd.DataFrame, title: str = "Pass map") -> go.Figure:
    fig = go.Figure()
    x_col = coord_column(passes, "norm_x", "x")
    y_col = coord_column(passes, "norm_y", "y")
    end_x_col = coord_column(passes, "norm_end_x", "end_x")
    end_y_col = coord_column(passes, "norm_end_y", "end_y")
    for _, row in passes.dropna(subset=[x_col, y_col, end_x_col, end_y_col]).iterrows():
        color = "#35d07f" if bool(row.get("pass_complete")) else "#ff6b6b"
        width = 2.5 if bool(row.get("pass_progressive")) else 1.2
        fig.add_trace(
            go.Scatter(
                x=[row[x_col], row[end_x_col]],
                y=[row[y_col], row[end_y_col]],
                mode="lines",
                line=dict(color=color, width=width),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return add_pitch_layout(fig, title)


def event_map(events: pd.DataFrame, title: str = "Team event map") -> go.Figure:
    fig = go.Figure()
    if not events.empty:
        x_col = coord_column(events, "norm_x", "x")
        y_col = coord_column(events, "norm_y", "y")
        fig.add_trace(
            go.Scatter(
                x=events[x_col],
                y=events[y_col],
                mode="markers",
                marker=dict(size=7, color="#74c0fc", opacity=0.65),
                text=events["event_type"],
                customdata=events[["player_name", "minute"]].fillna(""),
                hovertemplate="<b>%{text}</b><br>%{customdata[0]} - %{customdata[1]}'<extra></extra>",
            )
        )
    return add_pitch_layout(fig, title)


def location_heatmap(events: pd.DataFrame, title: str = "Heatmap") -> go.Figure:
    fig = go.Figure()
    if not events.empty:
        x_col = coord_column(events, "norm_x", "x")
        y_col = coord_column(events, "norm_y", "y")
        fig.add_trace(
            go.Histogram2dContour(
                x=events[x_col],
                y=events[y_col],
                colorscale="Viridis",
                contours=dict(coloring="heatmap"),
                ncontours=15,
                showscale=False,
                hoverinfo="skip",
            )
        )
    return add_pitch_layout(fig, title)
