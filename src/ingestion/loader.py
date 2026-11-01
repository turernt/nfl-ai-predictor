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
    return df[["team_abbr", "team_name", "team_nick", "team_conf", "team_division", "team_color", "team_logo_espn"]]


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
