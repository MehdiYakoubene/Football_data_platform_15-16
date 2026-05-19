from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.utils.data_access import TABLE_FILES, analytics_ready, load_manifest, query_df


st.set_page_config(page_title="Data Quality", layout="wide")
st.title("Data Quality")

if not analytics_ready():
    st.warning("Lancez d'abord `python scripts/build_dataset.py` pour charger tout le dataset.")
    st.stop()

manifest = load_manifest()
if manifest:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Schema", manifest.get("schema_version", "n/a"))
    col2.metric("Competitions-saisons", manifest.get("competition_seasons_loaded", "n/a"))
    col3.metric("Matchs charges", manifest.get("matches_loaded", "n/a"))
    col4.metric("Duree build", f"{manifest.get('duration_seconds', 'n/a')}s")

st.subheader("Volumes par table")
table_counts = manifest.get("table_counts", {}) if manifest else {}
if table_counts:
    counts_df = pd.DataFrame(
        [{"table": table, "rows": rows} for table, rows in table_counts.items() if table in TABLE_FILES]
    )
else:
    counts_df = pd.DataFrame(
        [{"table": table, "rows": query_df(f"SELECT COUNT(*) AS rows FROM {table}")["rows"].iloc[0]} for table in TABLE_FILES]
    )
st.dataframe(counts_df.sort_values("rows", ascending=False), width="stretch", hide_index=True)

st.subheader("Events par match")
events_per_match = query_df(
    """
    SELECT m.match_id,
           m.competition_name,
           m.season_name,
           m.match_date,
           m.home_team_name || ' - ' || m.away_team_name AS match_label,
           COUNT(e.event_uuid) AS event_count
    FROM dim_matches m
    LEFT JOIN fact_events e USING (match_id)
    GROUP BY 1, 2, 3, 4, 5
    ORDER BY event_count DESC
    """
)
if not events_per_match.empty:
    st.plotly_chart(px.histogram(events_per_match, x="event_count", nbins=30, title="Distribution du nombre d'evenements par match"), width="stretch")
    st.dataframe(events_per_match, width="stretch", hide_index=True)

st.subheader("Controles qualite")
duplicates = query_df(
    """
    SELECT
        COUNT(*) AS rows,
        COUNT(DISTINCT event_uuid) AS distinct_events,
        COUNT(*) - COUNT(DISTINCT event_uuid) AS duplicate_event_uuid
    FROM fact_events
    """
)

xg_coverage = query_df(
    """
    SELECT
        COUNT(*) AS shots,
        SUM(CASE WHEN shot_xg IS NOT NULL THEN 1 ELSE 0 END) AS shots_with_xg,
        ROUND(SUM(CASE WHEN shot_xg IS NOT NULL THEN 1 ELSE 0 END)::DOUBLE / NULLIF(COUNT(*), 0), 3) AS xg_coverage_rate
    FROM fact_shots
    """
)

col_left, col_right = st.columns(2)
if not duplicates.empty:
    col_left.metric("Doublons event_uuid", int(duplicates["duplicate_event_uuid"].iloc[0]))
if not xg_coverage.empty:
    col_right.metric("Couverture xG tirs", f"{xg_coverage['xg_coverage_rate'].iloc[0]:.1%}")

st.subheader("Null rates - colonnes cles")
null_rates = query_df(
    """
    SELECT 'event_uuid' AS column_name, AVG(CASE WHEN event_uuid IS NULL THEN 1 ELSE 0 END) AS null_rate FROM fact_events
    UNION ALL SELECT 'match_id', AVG(CASE WHEN match_id IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'event_type', AVG(CASE WHEN event_type IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'team_id', AVG(CASE WHEN team_id IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'player_id', AVG(CASE WHEN player_id IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'x', AVG(CASE WHEN x IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'norm_x', AVG(CASE WHEN norm_x IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'end_x', AVG(CASE WHEN end_x IS NULL THEN 1 ELSE 0 END) FROM fact_events
    UNION ALL SELECT 'norm_end_x', AVG(CASE WHEN norm_end_x IS NULL THEN 1 ELSE 0 END) FROM fact_events
    """
)
if not null_rates.empty:
    null_rates["null_rate"] = null_rates["null_rate"].astype(float)
    st.plotly_chart(px.bar(null_rates, x="column_name", y="null_rate", title="Taux de valeurs nulles"), width="stretch")
    st.dataframe(null_rates, width="stretch", hide_index=True)

st.caption("Les nulls sur `player_id` ou `end_x` sont attendus pour certains types d'evenements StatsBomb.")
