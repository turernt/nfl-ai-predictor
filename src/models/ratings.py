"""Ajustements au-delà de l'Elo : efficacité EPA, quarterback titulaire, repos.

Tous les ajustements sont exprimés en points, positifs = avantage à l'équipe à domicile.
"""
import math

import pandas as pd

PLAYS_PER_GAME = 60          # jeux offensifs par équipe et par match
EPA_RECENCY = 0.90           # poids d'un jeu = 0,90 ^ (semaines écoulées)
PRIOR_SEASON_WEIGHT = 0.35   # poids des jeux de la saison précédente
EPA_HFA = 1.5                # avantage du terrain moderne, en points
QB_DROPBACKS = 35            # dropbacks par match pour un QB titulaire
QB_PRIOR_N = 200             # lissage : 200 dropbacks « fictifs »
QB_PRIOR_EPA = -0.05         # niveau d'un remplaçant sans historique (EPA/dropback)
REST_PT_PER_DAY = 0.15
REST_CAP = 1.5


def _plays(pbp: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    p = pbp[(pbp["play_type"].isin(["pass", "run"])) & pbp["epa"].notna() & pbp["posteam"].notna()]
    cur = p[(p["season"] == season) & (p["week"] < week)]
    prev = p[p["season"] == season - 1]
    cur = cur.assign(w=EPA_RECENCY ** (week - 1 - cur["week"]))
    prev = prev.assign(w=PRIOR_SEASON_WEIGHT * EPA_RECENCY ** 6)
    return pd.concat([cur, prev])


def epa_ratings(pbp: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """EPA/jeu pondéré en attaque et en défense (encaissé), par équipe."""
    p = _plays(pbp, season, week)
    p = p.assign(we=p["epa"] * p["w"])
    off = p.groupby("posteam")[["we", "w"]].sum()
    dfn = p.groupby("defteam")[["we", "w"]].sum()
    r = pd.DataFrame({"off": off["we"] / off["w"], "def": dfn["we"] / dfn["w"]})
    r["net"] = r["off"] - r["def"]
    r["off_rank"] = r["off"].rank(ascending=False).astype(int)
    r["def_rank"] = r["def"].rank(ascending=True).astype(int)
    return r


def epa_margin(r: pd.DataFrame, home: str, away: str, neutral: bool) -> float:
    if home not in r.index or away not in r.index:
        return 0.0
    # attaque de l'un contre défense de l'autre, ramené à la moyenne
    home_pp = (r.at[home, "off"] + r.at[away, "def"]) / 2
    away_pp = (r.at[away, "off"] + r.at[home, "def"]) / 2
    return (home_pp - away_pp) * PLAYS_PER_GAME + (0 if neutral else EPA_HFA)


def qb_table(pbp: pd.DataFrame, season: int, week: int) -> tuple[pd.DataFrame, dict, float]:
    """Valeur de chaque QB (points par match vs moyenne) et valeur habituelle de chaque équipe."""
    p = _plays(pbp, season, week)
    db = p[(p["qb_dropback"] == 1) & p["qb_epa"].notna() & p["passer_player_id"].notna()]
    if db.empty:
        return pd.DataFrame(), {}, 0.0
    lg = (db["qb_epa"] * db["w"]).sum() / db["w"].sum()
    g = db.assign(we=db["qb_epa"] * db["w"]).groupby("passer_player_id")[["we", "w"]].sum()
    n = db.groupby("passer_player_id").size()
    shrunk = (g["we"] + QB_PRIOR_N * QB_PRIOR_EPA) / (g["w"] + QB_PRIOR_N)
    qbs = pd.DataFrame({"value": (shrunk - lg) * QB_DROPBACKS, "dropbacks": n})
    # Valeur habituelle d'une équipe = moyenne de ses QB pondérée par les dropbacks de la saison
    cur = db[db["season"] == season]
    team_base = {}
    for team, grp in cur.groupby("posteam"):
        share = grp.groupby("passer_player_id")["w"].sum()
        team_base[team] = float((qbs.loc[share.index, "value"] * share).sum() / share.sum())
    replacement = (QB_PRIOR_EPA - lg) * QB_DROPBACKS
    return qbs, team_base, replacement


def qb_adjustment(qbs: pd.DataFrame, team_base: dict, replacement: float,
                  team: str, qb_id) -> float:
    """Écart (points) entre le QB annoncé et le niveau habituel de l'équipe."""
    if not isinstance(qb_id, str) or team not in team_base:
        return 0.0
    value = qbs.at[qb_id, "value"] if qb_id in qbs.index else replacement
    return float(value - team_base[team])


def rest_adjustment(home_rest, away_rest) -> float:
    if pd.isna(home_rest) or pd.isna(away_rest):
        return 0.0
    return max(-REST_CAP, min(REST_CAP, (home_rest - away_rest) * REST_PT_PER_DAY))


def win_prob(spread: float, sd: float = 13.5) -> float:
    """Probabilité de victoire à domicile pour un spread (négatif = domicile favori)."""
    return 0.5 * (1 + math.erf((-spread / sd) / math.sqrt(2)))
