import logging
import pandas as pd
import nflreadpy as nfl

from src.config import TEAM_ALIASES

logger = logging.getLogger(__name__)


def _normalize(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        df[c] = df[c].replace(TEAM_ALIASES)
    return df


def load_schedules(seasons: list[int]) -> pd.DataFrame:
    logger.info("Chargement des calendriers %s-%s", seasons[0], seasons[-1])
    df = nfl.load_schedules(seasons).to_pandas()
    df = _normalize(df, ["home_team", "away_team"])
    return df.sort_values(["season", "week", "gameday", "gametime"]).reset_index(drop=True)


def load_teams() -> pd.DataFrame:
    df = nfl.load_teams().to_pandas()
    df = df[~df["team_abbr"].isin(TEAM_ALIASES.keys())]
    return df[["team_abbr", "team_name", "team_nick", "team_conf", "team_division", "team_color", "team_color2", "team_logo_espn"]]


def load_player_stats(season: int) -> pd.DataFrame:
    df = nfl.load_player_stats([season]).to_pandas()
    df["team"] = df["team"].replace(TEAM_ALIASES)
    return df


def load_injury_report(season: int, week: int) -> dict:
    """{player_id: statut} pour la semaine à venir (vide si indisponible)."""
    try:
        df = nfl.load_injuries([season]).to_pandas()
    except Exception as e:  # le rapport n'existe pas toujours (intersaison, début de saison)
        logger.warning("Rapport de blessures indisponible : %s", e)
        return {}
    df = df[(df["week"] == week) & df["report_status"].notna()]
    return dict(zip(df["gsis_id"], df["report_status"]))


def load_pbp(seasons: list[int]) -> pd.DataFrame:
    cols = ["season", "week", "season_type", "posteam", "defteam", "epa", "play_type", "yardline_100",
            "rusher_player_id", "receiver_player_id", "passer_player_id", "qb_dropback", "qb_epa"]
    df = nfl.load_pbp(seasons).to_pandas()[cols]
    return _normalize(df, ["posteam", "defteam"])


STATUS_ORDER = {"Out": 0, "Doubtful": 1, "Questionable": 2}
INJURY_FR = {"knee": "genou", "hamstring": "ischio-jambiers", "ankle": "cheville", "shoulder": "épaule", "hip": "hanche",
             "groin": "aine", "foot": "pied", "concussion": "commotion", "calf": "mollet", "quadricep": "quadriceps",
             "quadriceps": "quadriceps", "back": "dos", "illness": "maladie", "hand": "main", "wrist": "poignet",
             "elbow": "coude", "chest": "thorax", "ribs": "côtes", "neck": "cou", "toe": "orteil", "achilles": "tendon d’Achille",
             "thigh": "cuisse", "personal matter": "raisons personnelles", "not injury related": "hors blessure",
             "abdomen": "abdomen", "oblique": "oblique", "finger": "doigt", "thumb": "pouce", "pectoral": "pectoral",
             "heel": "talon", "shin": "tibia", "head": "tête", "face": "visage", "eye": "œil", "glute": "fessier"}
POS_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "T": 4, "G": 5, "C": 5, "DE": 6, "DT": 6, "LB": 7, "CB": 7, "S": 8}


def load_injury_details(season: int, week: int) -> dict:
    """{équipe: [{name, position, status, injury}]} pour la semaine, les plus importants d'abord."""
    try:
        df = nfl.load_injuries([season]).to_pandas()
    except Exception as e:
        logger.warning("Rapport de blessures indisponible : %s", e)
        return {}
    df = df[(df["week"] == week) & df["report_status"].isin(STATUS_ORDER.keys())].copy()
    df["team"] = df["team"].replace(TEAM_ALIASES)
    df["_s"] = df["report_status"].map(STATUS_ORDER)
    df["_p"] = df["position"].map(POS_ORDER).fillna(9)
    out = {}
    for team, grp in df.sort_values(["_s", "_p"]).groupby("team"):
        out[team] = [{"name": r.full_name, "position": r.position, "status": r.report_status,
                      "injury": INJURY_FR.get(r.report_primary_injury.lower(), r.report_primary_injury.lower())
                      if isinstance(r.report_primary_injury, str) else None}
                     for r in grp.itertuples()]
    return out
