# Modern Football Data Platform

Mini data platform football construite avec Python, pandas, DuckDB et Streamlit a partir de StatsBomb Open Data.

Ce projet a ete concu comme un projet portfolio pour des postes de **Performance Data Analyst**, **Data Engineer Sport**, **Football Data Scientist** ou **Data Scout**. L'objectif n'est pas de proposer un notebook isole, mais de montrer une chaine data complete : ingestion, transformation, modele analytique, KPIs documentes et dashboards exploitables.

## Resume executif

Modern Football Data Platform transforme les donnees brutes StatsBomb Open Data en tables analytiques propres, puis les expose dans une application Streamlit multipage. Le projet couvre le **Top 5 Europe 2015/2016** et la **Champions League 2015/2016**.

La logique produit est volontairement simple :

```text
StatsBomb Open Data
        |
        v
Ingestion locale des JSON
        |
        v
Nettoyage et flatten des events
        |
        v
Tables analytiques CSV / Parquet / DuckDB
        |
        v
Dashboards Streamlit
```

## Pourquoi ce projet interesse un club ?

**Analyse match**  
Un staff peut analyser un match a travers la timeline xG, la shot map, la pass map, la repartition spatiale des evenements et les KPIs equipe.

**Monitoring performance**  
Une cellule performance peut suivre les joueurs et equipes via des indicateurs standardises : tirs, xG, passes progressives, passes vers le dernier tiers, actions defensives, pressions, pertes de balle et activite dans la surface.

**Scouting joueur**  
Une cellule recrutement peut comparer les joueurs par famille de poste grace aux per90, aux percentiles, au radar joueur, aux key passes, a l'xG assisted et aux actions dans la surface.

## Apercu visuel


- Home : [docs/screenshots/home.png](docs/screenshots/home.png)
- Match Dashboard : [docs/screenshots/match_dashboard.png](docs/screenshots/match_dashboard.png)
[docs/screenshots/match_dashboard.png](docs/screenshots/match_dashboard2.png)
- Team Dashboard : [docs/screenshots/team_dashboard.png](docs/screenshots/team_dashboard.png)
- Player Dashboard : [docs/screenshots/player_dashboard.png](docs/screenshots/player_dashboard.png)
[docs/screenshots/player_dashboard.png](docs/screenshots/player_dashboard2.png)
- Data Quality : [docs/screenshots/data_quality.png](docs/screenshots/data_quality.png)


## Perimetre des donnees

Source principale : **StatsBomb Open Data**.

Perimetre par defaut du pipeline :

| Competition | Saison |
| --- | --- |
| Premier League | 2015/2016 |
| 1. Bundesliga | 2015/2016 |
| La Liga | 2015/2016 |
| Serie A | 2015/2016 |
| Ligue 1 | 2015/2016 |
| Champions League | 2015/2016 |

Le projet utilise uniquement des donnees publiques et gratuites :

- `competitions.json`
- `matches/{competition_id}/{season_id}.json`
- `events/{match_id}.json`
- `lineups/{match_id}.json`

Aucune donnee n'est inventee. Les valeurs manquantes sont conservees ou documentees.

## Stack technique

- Python
- pandas / numpy
- DuckDB
- Parquet via pyarrow
- Streamlit
- Plotly
- matplotlib / mplsoccer
- unittest

## Architecture du projet

```text
modern-football-data-platform/
|-- app.py
|-- main.py
|-- pages/
|   |-- 1_Data_Explorer.py
|   |-- 2_Match_Dashboard.py
|   |-- 3_Team_Dashboard.py
|   |-- 4_Player_Dashboard.py
|   |-- 5_Technical_Architecture.py
|   `-- 6_Data_Quality.py
|-- src/
|   |-- ingest/
|   |-- transform/
|   |-- metrics/
|   |-- viz/
|   `-- utils/
|-- scripts/
|   `-- build_dataset.py
|-- tests/
|-- data/
|   |-- raw/
|   |-- processed/
|   `-- analytics/
|-- requirements.txt
`-- README.md
```

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Utilisation

### Lancer le pipeline data

```bash
python main.py pipeline --stage all
```

### Verifier l'etat du dataset

```bash
python main.py pipeline --stage status
```

### Lancer l'application

```bash
python main.py app --debug
```

### Lancer les tests

```bash
python -m unittest discover -s tests -v
```

## Fonctionnement du pipeline

Le pipeline est volontairement simple : une commande construit toutes les tables necessaires a Streamlit.

```bash
python main.py pipeline --stage all
```

Cette commande execute toute la chaine :

```text
1. Ingestion StatsBomb Open Data
2. Nettoyage et flatten des JSON
3. Normalisation des coordonnees
4. Construction des tables analytiques
5. Export CSV / Parquet / DuckDB
6. Affichage des donnees dans Streamlit
```

### 1. Ingestion

Le pipeline recupere les fichiers JSON StatsBomb Open Data correspondant au perimetre du projet. Les fichiers sont stockes dans `data/raw/` pour eviter de les telecharger a chaque execution.

Fichiers charges :

- competitions ;
- matches ;
- events ;
- lineups.

### 2. Transformation

Les events StatsBomb contiennent de nombreux champs imbriques. Le pipeline extrait les informations utiles : match, equipe, joueur, minute, type d'action, possession, coordonnees, resultat de passe, xG, pression, etc.

Les coordonnees sont aussi normalisees pour que l'equipe analysee attaque vers `x=120`. Cette normalisation rend les passes progressives, carries progressifs et entrees dans le dernier tiers plus comparables.

### 3. Tables analytiques

Les donnees nettoyees sont transformees en dimensions, facts et tables de metrics. Ces tables alimentent directement Streamlit.

### 4. Stockage local

Les tables sont exportees dans `data/analytics/` en trois formats :

- CSV : lisible facilement par un recruteur ou dans Excel.
- Parquet : format analytique plus performant.
- DuckDB : moteur local rapide pour l'application Streamlit.

### 5. Manifest

Chaque build genere `data/analytics/build_manifest.json` avec la date, le perimetre charge, le nombre de matchs, les volumes par table, la duree d'execution et la version de schema.

### 6. Streamlit

L'application lit les tables DuckDB / analytics et applique les filtres directement dans les dashboards.

## Tables produites

Dimensions :

- `dim_competitions`
- `dim_matches`
- `dim_teams`
- `dim_players`

Facts :

- `fact_events`
- `fact_shots`
- `fact_passes`
- `fact_carries`
- `fact_defensive_actions`

Tables metier :

- `player_match_minutes`
- `player_match_stats`
- `player_profile_stats`
- `team_match_stats`

## Modele analytique simplifie

```text
dim_competitions
        |
        v
dim_matches ---- fact_events
        |             |
        |             |-- fact_shots
        |             |-- fact_passes
        |             |-- fact_carries
        |             `-- fact_defensive_actions
        |
        |-- team_match_stats
        `-- player_match_stats ---- player_profile_stats
```

## KPIs documentes

| KPI | Definition |
| --- | --- |
| Tirs | Nombre d'evenements `Shot`. |
| xG | Somme de `shot.statsbomb_xg` quand disponible. |
| Passes tentees | Nombre d'evenements `Pass`. |
| Passes reussies | Passes sans `pass.outcome`, convention StatsBomb pour une passe complete. |
| Passes progressives | Approximation : reduction d'au moins 25 % de la distance au centre du but adverse, sur coordonnees normalisees. |
| Passes vers le dernier tiers | Passe dont le depart est avant x=80 et l'arrivee a x>=80 sur terrain StatsBomb 120x80 normalise. |
| Carries progressifs | Meme logique que les passes progressives, appliquee aux conduites de balle. |
| Actions defensives | `Pressure`, `Ball Recovery`, `Interception`, `Block`, `Clearance`, `Duel`, `Dribbled Past`, `Foul Committed`. |
| Ball recoveries | Nombre d'evenements `Ball Recovery`. |
| Pressures | Nombre d'evenements `Pressure`. |
| Pertes de balle | `Dispossessed`, `Miscontrol`, `Error`, ou passe incomplete. |
| Key passes | Passe marquee `pass.shot_assist` par StatsBomb. |
| xG assisted | Somme du xG du tir associe a une key pass dans la meme possession. |
| Touches in box | Evenements avec coordonnee normalisee dans la surface adverse. |
| Passes into box | Passes dont la destination normalisee entre dans la surface adverse. |
| Carries into box | Carries dont la destination normalisee entre dans la surface adverse. |
| Minutes estimees | Minutes issues des intervalles `lineups.positions`; fallback sur les minutes d'events si indisponible. |
| Per90 | KPI rapporte a 90 minutes estimees. |
| Percentiles poste | Percentiles calcules par famille de poste : Goalkeeper, Defender, Midfielder, Forward, Other. |

## Application Streamlit

L'application est organisee en plusieurs pages.

| Page | Objectif |
| --- | --- |
| Home | Presenter le projet, le perimetre et les definitions metier. |
| Data Explorer | Explorer competitions, matchs, equipes et joueurs. |
| Match Dashboard | Analyser un match : xG timeline, shot map, event map, pass map. |
| Team Dashboard | Suivre les KPIs d'une equipe. |
| Player Dashboard | Analyser un joueur : filtre minutes minimum, per90, percentiles poste, radar, shot map, pass map. |
| Technical Architecture | Montrer le fonctionnement data engineering. |
| Data Quality | Controler volumes, doublons, nulls, couverture xG et manifest. |

Les dashboards interrogent DuckDB pour filtrer les donnees sans charger inutilement toutes les grosses tables en memoire.

## Data quality

La page Data Quality permet de verifier rapidement :

- le nombre de competitions-saisons chargees ;
- le nombre de matchs ;
- le nombre de lignes par table ;
- la distribution des events par match ;
- les doublons sur `event_uuid` ;
- la couverture xG des tirs ;
- les taux de nulls sur les colonnes critiques.

Cette partie est importante pour montrer une posture data engineer : le projet ne se limite pas a produire des visualisations, il verifie aussi que la couche analytique est exploitable.

## Evolutions possibles

### 1. Full build documente

Le pipeline peut etre execute sur le perimetre complet Top 5 Europe + Champions League 2015/2016. Le manifest permet ensuite de documenter les volumes reels : competitions, matchs, evenements et duree d'execution.

Commande :

```bash
python main.py pipeline --stage all --workers 12 --quiet --log-file logs/build_dataset.log
python main.py pipeline --stage status
```

### 2. Analyses metier integrees

La plateforme peut etre enrichie avec des cas d'usage rediges :

- exemple d'analyse match ;
- exemple de profil joueur interessant ;
- exemple de comparaison equipe.

Ces analyses permettent de relier les KPIs a des decisions football concretes.

### 3. Scouting joueur avance

Evolutions possibles :

- familles de postes plus fines : centre-back, full-back, defensive midfielder, central midfielder, attacking midfielder, winger, striker ;
- comparaison joueur vs moyenne poste vs top 10 % ;
- texte automatique "forces / points de vigilance" base sur les percentiles.

### 4. Couverture de tests

Tests complementaires possibles :

- calcul des key passes et xG assisted ;
- calcul des percentiles par poste ;
- calcul des minutes estimees ;
- normalisation du sens d'attaque ;
- non-regression sur un petit match de reference.

### 5. Pipeline incremental

Une version ulterieure pourrait separer plus clairement les etapes :

- `ingest` : telecharger uniquement les JSON manquants ;
- `transform` : reconstruire les facts ;
- `metrics` : reconstruire uniquement les aggregats ;
- `all` : tout reconstruire.

### 6. Conteneurisation

Un Dockerfile simple pourrait rendre la demo plus reproductible et faciliter le lancement sur une autre machine.

## Limites connues

- StatsBomb Open Data ne couvre pas toutes les competitions et toutes les saisons de maniere uniforme.
- Les minutes sont estimees depuis les lineups et les events ; elles sont suffisantes pour une demo portfolio, mais doivent etre validees avant un usage club reel.
- Les metrics progressives sont des approximations documentees, basees sur les coordonnees event data.
- Le projet n'est pas un modele predictif ; il s'agit d'une plateforme analytique orientee exploration, monitoring et scouting.

## Positionnement portfolio

Ce projet montre plusieurs competences importantes pour un poste data dans le football :

- ingestion de donnees JSON semi-structurees ;
- modelisation analytique ;
- transformation de donnees evenements ;
- gestion du cache et des outputs ;
- creation de KPIs footballistiques ;
- stockage local performant avec DuckDB et Parquet ;
- dashboards Streamlit orientes utilisateurs ;
- documentation metier et technique ;
- tests unitaires.

Le projet illustre une capacite a construire une petite plateforme data football propre, maintenable et exploitable par un staff ou une cellule recrutement.
