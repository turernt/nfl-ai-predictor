from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEB_DATA_DIR = ROOT / "web" / "data"

FIRST_SEASON = 2010        # saisons de "chauffe" pour stabiliser les Elo
BASE_ELO = 1505.0          # moyenne de long terme
K_FACTOR = 20.0
HFA = 35.0                 # avantage du terrain en points Elo (~1,4 pt), calé sur 2016-2025
REGRESSION = 0.4           # retour vers la moyenne entre deux saisons (calé sur 2016-2025)
ELO_PER_POINT = 25.0       # 25 points Elo ≈ 1 point de spread

# Franchises relocalisées : on fusionne l'historique sous l'abréviation actuelle
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}
