from __future__ import annotations

import streamlit as st

from src.utils.data_access import analytics_ready, load_table


st.set_page_config(page_title="Data Explorer", layout="wide")
st.title("Data Explorer")

if not analytics_ready():
    st.warning("Lancez d'abord `python scripts/build_dataset.py` pour charger tout le dataset.")
    st.stop()

competitions = load_table("dim_competitions")
matches = load_table("dim_matches")
teams = load_table("dim_teams")
players = load_table("dim_players")

st.sidebar.header("Filtres dataset")
competition_filter = st.sidebar.multiselect("Competition", sorted(matches["competition_name"].dropna().unique())) if not matches.empty else []
season_options = matches.loc[matches["competition_name"].isin(competition_filter), "season_name"] if competition_filter else matches.get("season_name", [])
season_filter = st.sidebar.multiselect("Saison", sorted(season_options.dropna().unique())) if not matches.empty else []

filtered_matches = matches.copy()
if competition_filter:
    filtered_matches = filtered_matches[filtered_matches["competition_name"].isin(competition_filter)]
if season_filter:
    filtered_matches = filtered_matches[filtered_matches["season_name"].isin(season_filter)]

scope_teams = set(filtered_matches["home_team_name"].dropna()) | set(filtered_matches["away_team_name"].dropna()) if not filtered_matches.empty else set()
filtered_teams = teams[teams["team_name"].isin(scope_teams)] if scope_teams else teams
filtered_players = players[players["team_name"].isin(scope_teams)] if scope_teams else players

tab_comp, tab_matches, tab_teams, tab_players = st.tabs(["Competitions", "Matches", "Teams", "Players"])

with tab_comp:
    st.dataframe(competitions, width="stretch", hide_index=True)

with tab_matches:
    st.dataframe(filtered_matches, width="stretch", hide_index=True)

with tab_teams:
    st.dataframe(filtered_teams, width="stretch", hide_index=True)

with tab_players:
    team_filter = st.multiselect("Equipe", sorted(filtered_players["team_name"].dropna().unique())) if not filtered_players.empty else []
    view = filtered_players[filtered_players["team_name"].isin(team_filter)] if team_filter else filtered_players
    st.dataframe(view, width="stretch", hide_index=True)

