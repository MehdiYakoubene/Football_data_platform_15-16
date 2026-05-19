from __future__ import annotations

import streamlit as st

from src.utils.data_access import analytics_ready, duckdb_path


st.set_page_config(page_title="Modern Football Data Platform", layout="wide")

st.title("Modern Football Data Platform")
st.caption("Mini data platform football basee sur StatsBomb Open Data")

if not analytics_ready():
    st.warning("Aucune table analytique detectee. Lancez le pipeline avant la demo Streamlit.")
    st.code("python main.py pipeline --stage all", language="bash")

st.markdown(
    """
Cette application montre une chaine data complete orientee club : ingestion des JSON StatsBomb,
normalisation des evenements, modele analytique, KPIs footballistiques et dashboards exploitables
par un staff performance, une cellule recrutement ou une equipe data sport.
"""
)

col1, col2, col3 = st.columns(3)
col1.metric("Source principale", "StatsBomb Open Data")
col2.metric("Stockage", "CSV + Parquet + DuckDB")
col3.metric("Niveau attendu", "Portfolio pro")

st.subheader("Architecture produit")
st.markdown(
    """
1. **Ingestion** : competitions, matches, events et lineups avec cache local.
2. **Transformations** : flatten des nested JSON, coordonnees x/y, types d'actions, resultats et valeurs manquantes.
3. **Modele analytique** : dimensions, facts evenements, shots, passes, carries et actions defensives.
4. **Metrics layer** : KPIs joueur, equipe et match documentes.
5. **Qualite & manifest** : controles de volumetrie, nulls, doublons et couverture xG.
6. **Dashboards** : exploration, analyse match, equipe, joueur et architecture technique.
"""
)

st.subheader("Definitions metier")
st.markdown(
    """
- **xG** : valeur `shot.statsbomb_xg` fournie par StatsBomb quand disponible.
- **Coordonnees normalisees** : le sens d'attaque est infere par equipe/periode pour attaquer vers x=120.
- **Passe progressive** : approximation documentee, reduction d'au moins 25 % de la distance au centre du but adverse sur coordonnees normalisees.
- **Passe vers le dernier tiers** : passe dont le depart est avant x=80 et l'arrivee a x>=80 sur un terrain StatsBomb 120x80 normalise.
- **Carry progressif** : meme logique que la passe progressive, appliquee a une conduite de balle.
- **Perte de balle** : `Dispossessed`, `Miscontrol`, `Error`, ou passe incomplete.
"""
)

st.info(f"Base DuckDB generee : `{duckdb_path()}`")
