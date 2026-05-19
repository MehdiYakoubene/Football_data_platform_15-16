from __future__ import annotations

import streamlit as st

from src.utils.data_access import analytics_ready, load_filtered_table, load_table
from src.viz.charts import xg_timeline_chart
from src.viz.pitch_plots import event_map, pass_map, shot_map


st.set_page_config(page_title="Match Dashboard", layout="wide")
st.title("Match Dashboard")

if not analytics_ready():
    st.warning("Lancez d'abord `python scripts/build_dataset.py` pour charger tout le dataset.")
    st.stop()

matches = load_table("dim_matches")

if matches.empty:
    st.info("Aucun match disponible.")
    st.stop()

st.sidebar.header("Filtres match")
competition = st.sidebar.selectbox("Competition", sorted(matches["competition_name"].dropna().unique()))
competition_matches = matches[matches["competition_name"].eq(competition)]
season = st.sidebar.selectbox("Saison", sorted(competition_matches["season_name"].dropna().unique()))
matches = competition_matches[competition_matches["season_name"].eq(season)].copy()

matches["match_label"] = (
    matches["match_date"].astype(str)
    + " | "
    + matches["home_team_name"].astype(str)
    + " "
    + matches["home_score"].astype(str)
    + "-"
    + matches["away_score"].astype(str)
    + " "
    + matches["away_team_name"].astype(str)
)
label = st.selectbox("Match", matches["match_label"].tolist())
match_id = int(matches.loc[matches["match_label"].eq(label), "match_id"].iloc[0])

match_stats = load_filtered_table("team_match_stats", {"match_id": match_id})
match_shots = load_filtered_table("fact_shots", {"match_id": match_id})
match_passes = load_filtered_table("fact_passes", {"match_id": match_id})
match_events = load_filtered_table("fact_events", {"match_id": match_id})

cols = st.columns(4)
cols[0].metric("Tirs", int(match_shots.shape[0]))
cols[1].metric("xG total", f"{match_shots['shot_xg'].fillna(0).sum():.2f}" if not match_shots.empty else "0.00")
cols[2].metric("Passes", int(match_passes.shape[0]))
cols[3].metric("Evenements", int(match_events.shape[0]))

st.plotly_chart(xg_timeline_chart(match_shots), width="stretch")

col_left, col_right = st.columns(2)
with col_left:
    st.plotly_chart(shot_map(match_shots, "Shot map du match"), width="stretch")
with col_right:
    team_names = sorted(match_events["team_name"].dropna().unique())
    if team_names:
        selected_team = st.selectbox("Equipe pour event map", team_names)
        st.plotly_chart(event_map(match_events[match_events["team_name"].eq(selected_team)], "Team event map"), width="stretch")

players = sorted(match_passes["player_name"].dropna().unique())
if players:
    selected_player = st.selectbox("Joueur pour pass map", players)
    player_passes = match_passes[match_passes["player_name"].eq(selected_player)].head(140)
    st.plotly_chart(pass_map(player_passes, f"Pass map - {selected_player}"), width="stretch")

st.subheader("Synthese equipe")
st.dataframe(match_stats, width="stretch", hide_index=True)

