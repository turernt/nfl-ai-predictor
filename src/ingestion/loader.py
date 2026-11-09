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


def load_player_stats(seasons: list[int]) -> pd.DataFrame:
    """Statistiques joueur par match (plusieurs saisons : le modèle de buteurs apprend sur l'historique)."""
    df = nfl.load_player_stats(seasons).to_pandas()
    for c in ("team", "opponent_team"):
        df[c] = df[c].replace(TEAM_ALIASES)
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
            "rusher_player_id", "receiver_player_id", "passer_player_id", "qb_dropback", "qb_epa",
            "two_point_attempt"]
    df = nfl.load_pbp(seasons).select(cols).to_pandas()   # colonnes choisies avant la conversion : moins de mémoire
    return _normalize(df, ["posteam", "defteam"])


def load_injuries_all(seasons: list[int]) -> pd.DataFrame | None:
    """Rapports de blessures de plusieurs saisons (statut de chaque joueur, semaine par semaine)."""
    try:
        df = nfl.load_injuries(seasons).to_pandas()
    except Exception as e:
        logger.warning("Rapports de blessures indisponibles : %s", e)
        return None
    df["team"] = df["team"].replace(TEAM_ALIASES)
    return df[["season", "week", "team", "gsis_id", "report_status"]]


def load_snaps(seasons: list[int]) -> tuple[pd.DataFrame | None, dict]:
    """Snaps joués par match et table de correspondance des identifiants (PFR -> GSIS)."""
    try:
        snaps = nfl.load_snap_counts(seasons).to_pandas()[["season", "week", "pfr_player_id", "offense_pct"]]
        ids = nfl.load_players().to_pandas()[["pfr_id", "gsis_id"]].dropna()
        return snaps, dict(zip(ids["pfr_id"], ids["gsis_id"]))
    except Exception as e:
        logger.warning("Snaps indisponibles : %s", e)
        return None, {}


def load_depth_chart(season: int) -> pd.DataFrame | None:
    """Dernière hiérarchie connue de chaque équipe (QB, RB, WR, TE), du titulaire au remplaçant."""
    try:
        df = nfl.load_depth_charts([season]).to_pandas()
    except Exception as e:
        logger.warning("Hiérarchie des postes indisponible : %s", e)
        return None
    if "dt" not in df.columns or "pos_rank" not in df.columns:
        return None
    df["team"] = df["team"].replace(TEAM_ALIASES)
    df = df[df["dt"] == df.groupby("team")["dt"].transform("max")]
    df = df[df["pos_abb"].isin(["QB", "RB", "WR", "TE"]) & df["gsis_id"].notna()]
    return df[["team", "gsis_id", "player_name", "pos_abb", "pos_rank", "dt"]].sort_values(["team", "pos_abb", "pos_rank"])


def load_roster_status(season: int) -> pd.DataFrame | None:
    """Statut d'effectif le plus récent de chaque joueur (ACT = actif, RES = réserve des blessés, DEV = réserve)."""
    try:
        df = nfl.load_rosters_weekly([season]).to_pandas()
    except Exception as e:
        logger.warning("Effectifs indisponibles : %s", e)
        return None
    df["team"] = df["team"].replace(TEAM_ALIASES)
    df = df[df["week"] == df.groupby("team")["week"].transform("max")]
    return df[["team", "gsis_id", "full_name", "position", "status"]].dropna(subset=["gsis_id"])


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
