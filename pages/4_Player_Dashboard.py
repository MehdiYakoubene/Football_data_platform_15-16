from __future__ import annotations

import pandas as pd
import streamlit as st

from src.utils.data_access import analytics_ready, load_filtered_table, load_table
from src.viz.charts import player_radar_chart, top_players_bar
from src.viz.pitch_plots import pass_map, shot_map


st.set_page_config(page_title="Player Dashboard", layout="wide")
st.title("Player Dashboard")

if not analytics_ready():
    st.warning("Lancez d'abord `python main.py pipeline --stage all`.")
    st.stop()

player_stats = load_table("player_match_stats")
player_profiles = load_table("player_profile_stats")
matches = load_table("dim_matches")

if player_stats.empty:
    st.info("Aucune statistique joueur disponible.")
    st.stop()

st.sidebar.header("Filtres joueur")
competition_filter = st.sidebar.multiselect("Competition", sorted(matches["competition_name"].dropna().unique())) if not matches.empty else []
season_options = matches.loc[matches["competition_name"].isin(competition_filter), "season_name"] if competition_filter else matches.get("season_name", [])
season_filter = st.sidebar.multiselect("Saison", sorted(season_options.dropna().unique())) if not matches.empty else []

match_scope = matches.copy()
if competition_filter:
    match_scope = match_scope[match_scope["competition_name"].isin(competition_filter)]
if season_filter:
    match_scope = match_scope[match_scope["season_name"].isin(season_filter)]

player_stats = player_stats[player_stats["match_id"].isin(match_scope["match_id"])] if not match_scope.empty else player_stats
if not player_profiles.empty:
    scoped_players = player_stats[["player_id", "team_id"]].drop_duplicates()
    player_profiles = player_profiles.merge(scoped_players, on=["player_id", "team_id"], how="inner")

if player_stats.empty:
    st.info("Aucun joueur dans le perimetre selectionne.")
    st.stop()

max_minutes = 0
if not player_profiles.empty and "minutes_estimated" in player_profiles.columns:
    max_minutes = int(player_profiles["minutes_estimated"].fillna(0).max())
elif "minutes_estimated" in player_stats.columns:
    max_minutes = int(player_stats.groupby("player_id")["minutes_estimated"].sum().fillna(0).max())

minute_step = 90
minute_default = 0
min_minutes = st.sidebar.slider(
    "Minutes minimum",
    min_value=0,
    max_value=max(max_minutes, minute_step),
    value=minute_default,
    step=minute_step,
    help="Filtre les classements et la liste des joueurs pour eviter les comparaisons sur un faible temps de jeu.",
)

if not player_profiles.empty and "minutes_estimated" in player_profiles.columns:
    player_profiles = player_profiles[player_profiles["minutes_estimated"].fillna(0) >= min_minutes]
    eligible_players = player_profiles[["player_id", "team_id"]].drop_duplicates()
    player_stats = player_stats.merge(eligible_players, on=["player_id", "team_id"], how="inner")
else:
    minutes_by_player = (
        player_stats.groupby(["player_id", "team_id"], dropna=False)["minutes_estimated"]
        .sum()
        .reset_index()
        if "minutes_estimated" in player_stats.columns
        else pd.DataFrame()
    )
    if not minutes_by_player.empty:
        eligible_players = minutes_by_player[minutes_by_player["minutes_estimated"].fillna(0) >= min_minutes][["player_id", "team_id"]]
        player_stats = player_stats.merge(eligible_players, on=["player_id", "team_id"], how="inner")

if player_stats.empty:
    st.info("Aucun joueur ne respecte le filtre de minutes minimum dans le perimetre selectionne.")
    st.stop()

ranking_source = player_profiles if not player_profiles.empty else player_stats
ranking_metrics = (
    [
        "xg_per90",
        "shots_per90",
        "progressive_passes_per90",
        "passes_into_final_third_per90",
        "defensive_actions_per90",
        "pressures_per90",
        "key_passes_per90",
        "xg_assisted_per90",
        "touches_in_box_per90",
    ]
    if not player_profiles.empty
    else ["xg", "shots", "passes_completed", "progressive_passes", "defensive_actions", "pressures", "turnovers"]
)
metric = st.selectbox("Classement", ranking_metrics)
st.caption(f"Filtre actif : joueurs avec au moins {min_minutes} minutes estimees dans le perimetre selectionne.")
st.plotly_chart(top_players_bar(ranking_source, metric, f"Top joueurs - {metric}"), width="stretch")

players = sorted(player_stats["player_name"].dropna().unique())
selected_player = st.selectbox("Joueur", players)
profile = player_stats[player_stats["player_name"].eq(selected_player)]
totals = profile[
    [
        "shots",
        "xg",
        "passes_attempted",
        "passes_completed",
        "progressive_passes",
        "passes_into_final_third",
        "progressive_carries",
        "defensive_actions",
        "pressures",
        "turnovers",
    ]
].sum()

cols = st.columns(5)
cols[0].metric("Tirs", int(totals["shots"]))
cols[1].metric("xG", f"{totals['xg']:.2f}")
cols[2].metric("Passes reussies", int(totals["passes_completed"]))
cols[3].metric("Passes progressives", int(totals["progressive_passes"]))
cols[4].metric("Actions defensives", int(totals["defensive_actions"]))

if not player_profiles.empty:
    selected_profiles = player_profiles[player_profiles["player_name"].eq(selected_player)].copy()
    if not selected_profiles.empty:
        selected_profile = selected_profiles.sort_values("minutes_estimated", ascending=False).iloc[0]
        radar_metrics = [
            "shots_per90_pctile",
            "xg_per90_pctile",
            "progressive_passes_per90_pctile",
            "passes_into_final_third_per90_pctile",
            "defensive_actions_per90_pctile",
            "pressures_per90_pctile",
            "key_passes_per90_pctile",
            "touches_in_box_per90_pctile",
        ]
        family = selected_profile["position_family"]
        family_profiles = player_profiles[player_profiles["position_family"].eq(family)]
        benchmark = pd.DataFrame(
            [
                {"profile": "Position average", **{metric_name: family_profiles[metric_name].mean() for metric_name in radar_metrics}},
                {"profile": "Top 10 pct", **{metric_name: family_profiles[metric_name].quantile(0.9) for metric_name in radar_metrics}},
            ]
        )

        st.subheader("Radar percentiles par famille de poste")
        st.caption("Les valeurs sont des percentiles dans la famille de poste estimee. Les minutes sont approximees par presence dans l'event data.")
        st.plotly_chart(player_radar_chart(selected_profile, benchmark, radar_metrics, f"{selected_player} vs {family}"), width="stretch")

        profile_cols = [
            "player_name",
            "team_name",
            "primary_position",
            "position_family",
            "matches",
            "minutes_estimated",
            "xg_per90",
            "shots_per90",
            "progressive_passes_per90",
            "passes_into_final_third_per90",
            "defensive_actions_per90",
            "pressures_per90",
            "key_passes_per90",
            "xg_assisted_per90",
            "touches_in_box_per90",
        ]
        st.dataframe(selected_profiles.reindex(columns=profile_cols), width="stretch", hide_index=True)

col_left, col_right = st.columns(2)
with col_left:
    player_shots = load_filtered_table("fact_shots", {"player_name": selected_player, "match_id": profile["match_id"].dropna().astype(int).tolist()})
    st.plotly_chart(shot_map(player_shots, f"Shot map - {selected_player}"), width="stretch")
with col_right:
    player_passes = load_filtered_table("fact_passes", {"player_name": selected_player, "match_id": profile["match_id"].dropna().astype(int).tolist()}, limit=160)
    st.plotly_chart(pass_map(player_passes, f"Pass map - {selected_player}"), width="stretch")

st.subheader("Match logs")
st.dataframe(profile, width="stretch", hide_index=True)
