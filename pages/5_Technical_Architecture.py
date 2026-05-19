from __future__ import annotations

import streamlit as st

from src.utils.data_access import TABLE_FILES, duckdb_path


st.set_page_config(page_title="Technical Architecture", layout="wide")
st.title("Technical Architecture")

st.markdown(
    """
Cette page explicite la logique data engineering du projet : separation des couches, cache local,
tables analytiques et couche dashboard. L'objectif est de montrer une mini plateforme industrialisable,
pas seulement un notebook exploratoire.
"""
)

st.subheader("Pipeline")
st.code(
    """
StatsBomb Open Data GitHub
        |
        v
data/raw/              cache JSON: competitions, matches, events, lineups
        |
        v
src/transform/         flatten JSON, normalisation attaque, flags metiers
        |
        v
data/processed/        clean_events.csv
        |
        v
data/analytics/        CSV, Parquet, DuckDB, manifest, data quality
        |
        v
Streamlit pages        dashboards staff / performance / recrutement
""",
    language="text",
)

st.subheader("Tables analytiques")
for name, path in TABLE_FILES.items():
    st.write(f"- `{name}` -> `{path}`")

st.subheader("DuckDB")
st.write(f"`{duckdb_path()}`")

st.subheader("Commandes de demo")
st.code(
    """
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py pipeline --stage status
python main.py pipeline --stage all --workers 12
python main.py app --debug
""",
    language="powershell",
)

st.caption("Perimetre par defaut : Top 5 Europe 2015/2016 + Champions League 2015/2016.")
