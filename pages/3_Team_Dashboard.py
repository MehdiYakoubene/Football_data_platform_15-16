from __future__ import annotations

import streamlit as st

from src.utils.data_access import analytics_ready, load_filtered_table, load_table
from src.viz.charts import comparative_bar
from src.viz.pitch_plots import location_heatmap


st.set_page_config(page_title="Team Dashboard", layout="wide")
st.title("Team Dashboard")

if not analytics_ready():
    st.warning("Lancez d'abord `python scripts/build_dataset.py` pour charger tout le dataset.")
    st.stop()

team_stats = load_table("team_match_stats")
matches = load_table("dim_matches")

if team_stats.empty:
    st.info("Aucune statistique equipe disponible.")
    st.stop()

st.sidebar.header("Filtres equipe")
competition_filter = st.sidebar.multiselect("Competition", sorted(matches["competition_name"].dropna().unique())) if not matches.empty else []
season_options = matches.loc[matches["competition_name"].isin(competition_filter), "season_name"] if competition_filter else matches.get("season_name", [])
season_filter = st.sidebar.multiselect("Saison", sorted(season_options.dropna().unique())) if not matches.empty else []

match_scope = matches.copy()
if competition_filter:
    match_scope = match_scope[match_scope["competition_name"].isin(competition_filter)]
if season_filter:
    match_scope = match_scope[match_scope["season_name"].isin(season_filter)]

team_stats = team_stats[team_stats["match_id"].isin(match_scope["match_id"])] if not match_scope.empty else team_stats
if team_stats.empty:
    st.info("Aucune equipe dans le perimetre selectionne.")
    st.stop()
teams = sorted(team_stats["team_name"].dropna().unique())
selected_team = st.selectbox("Equipe", teams)
view = team_stats[team_stats["team_name"].eq(selected_team)]

totals = view[["shots", "xg", "passes_attempted", "passes_completed", "progressive_passes", "passes_into_final_third", "progressive_carries", "defensive_actions", "ball_recoveries", "pressures", "turnovers"]].sum()

cols = st.columns(5)
cols[0].metric("Tirs", int(totals["shots"]))
cols[1].metric("xG", f"{totals['xg']:.2f}")
cols[2].metric("Passes reussies", int(totals["passes_completed"]))
cols[3].metric("Passes progressives", int(totals["progressive_passes"]))
cols[4].metric("Pressions", int(totals["pressures"]))

comparison = team_stats.groupby("team_name", as_index=False)[["xg", "shots", "progressive_passes", "defensive_actions"]].sum()
metric = st.selectbox("Metric comparative", ["xg", "shots", "progressive_passes", "defensive_actions"])
st.plotly_chart(comparative_bar(comparison.sort_values(metric, ascending=False), "team_name", metric, f"Comparaison equipes - {metric}"), width="stretch")

team_events = load_filtered_table("fact_events", {"team_name": selected_team, "match_id": view["match_id"].dropna().astype(int).tolist()}, limit=30000)
st.plotly_chart(location_heatmap(team_events, f"Heatmap evenements - {selected_team}"), width="stretch")

st.subheader("Matchs de l'equipe")
st.dataframe(view, width="stretch", hide_index=True)

