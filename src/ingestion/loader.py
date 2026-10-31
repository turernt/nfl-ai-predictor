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
