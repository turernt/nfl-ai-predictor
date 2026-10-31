"""Probabilité qu'un joueur marque au moins un touchdown (rush ou réception).

Méthode :
1. Part de chaque joueur dans les touchdowns « offensifs » de son équipe (course + réception),
   lissée vers sa part d'opportunités (courses + cibles), avec plus de poids aux matchs récents.
2. Touchdowns attendus de l'équipe pour le match = son rythme habituel, ajusté par le score projeté.
3. Loi de Poisson : P(au moins 1 TD) = 1 - exp(-λ).
"""
import math

import pandas as pd

RECENCY = 0.85        # poids d'un match = 0,85 ^ (nombre de semaines écoulées)
PRIOR_TDS = 10.0      # lissage fort : les TD régressent beaucoup d’une semaine à l’autre
ACTIVE_WINDOW = 3     # joueur retenu s'il a joué l'un des 3 derniers matchs de son équipe
SKILL_POS = {"RB", "WR", "TE", "QB", "FB"}
OUT_STATUSES = {"Out", "Doubtful"}
CALIBRATION = 0.9     # prudence : les modèles de TD surestiment souvent les favoris


def build_player_table(stats: pd.DataFrame, week: int) -> pd.DataFrame:
    s = stats[(stats["week"] < week) & stats["position"].isin(SKILL_POS)].copy()
    if s.empty:
        return s
    s["w"] = RECENCY ** (week - 1 - s["week"])
    s["tds"] = s["rushing_tds"].fillna(0) + s["receiving_tds"].fillna(0)
    s["opp"] = s["carries"].fillna(0) + s["targets"].fillna(0)

    # Équipe actuelle = équipe du dernier match joué ; on écarte les joueurs inactifs
    last = s.sort_values("week").groupby("player_id").tail(1)[["player_id", "team", "week"]]
    team_weeks = s.groupby("team")["week"].apply(lambda w: sorted(w.unique())[-ACTIVE_WINDOW:])
    active = last[last.apply(lambda r: r["week"] in team_weeks.get(r["team"], []), axis=1)]
    s = s.merge(active[["player_id", "team"]], on=["player_id", "team"])

    agg = s.groupby(["player_id", "team"]).agg(
        name=("player_display_name", "last"), position=("position", "last"),
        headshot=("headshot_url", "last"),
        w_tds=("tds", lambda x: (x * s.loc[x.index, "w"]).sum()),
        w_opp=("opp", lambda x: (x * s.loc[x.index, "w"]).sum()),
        tds=("tds", "sum"), games=("week", "nunique"),
    ).reset_index()

    team = agg.groupby("team")[["w_tds", "w_opp"]].sum().rename(columns=lambda c: "team_" + c)
    agg = agg.join(team, on="team")
    opp_share = agg["w_opp"] / agg["team_w_opp"].where(agg["team_w_opp"] > 0)
    agg["share"] = ((agg["w_tds"] + PRIOR_TDS * opp_share.fillna(0)) / (agg["team_w_tds"] + PRIOR_TDS)).fillna(0)
    return agg


def team_td_rates(stats: pd.DataFrame, sched: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """TD offensifs et points marqués par match, pondérés par la récence."""
    s = stats[stats["week"] < week]
    tds = (s.assign(t=s["rushing_tds"].fillna(0) + s["receiving_tds"].fillna(0))
             .groupby(["team", "week"])["t"].sum().reset_index())
    played = sched[(sched["season"] == season) & (sched["week"] < week)].dropna(subset=["home_score"])
    pts = pd.concat([
        played[["home_team", "week", "home_score"]].set_axis(["team", "week", "pts"], axis=1),
        played[["away_team", "week", "away_score"]].set_axis(["team", "week", "pts"], axis=1),
    ])
    df = pts.merge(tds, on=["team", "week"], how="left").fillna({"t": 0})
    df["w"] = RECENCY ** (week - 1 - df["week"])
    g = df.groupby("team")
    return pd.DataFrame({
        "tds_pg": g.apply(lambda x: (x["t"] * x["w"]).sum() / x["w"].sum()),
        "pts_pg": g.apply(lambda x: (x["pts"] * x["w"]).sum() / x["w"].sum()),
    })


def likely_scorers(players: pd.DataFrame, rates: pd.DataFrame, team: str, exp_points: float,
                   injuries: dict, top: int = 3) -> list[dict]:
    if players.empty or team not in rates.index:
        return []
    r = rates.loc[team]
    # TD par point marqué de l'équipe, ramené vers la moyenne NFL (~0,105) pour limiter le bruit
    td_per_pt = (r["tds_pg"] + 0.105 * 40) / (r["pts_pg"] + 40) if r["pts_pg"] > 0 else 0.105
    team_tds = td_per_pt * exp_points
    p = players[players["team"] == team].copy()
    p["status"] = p["player_id"].map(injuries)
    p = p[~p["status"].isin(OUT_STATUSES)]
    p["prob"] = 1 - (-(CALIBRATION * team_tds * p["share"])).apply(math.exp)
    p = p.sort_values("prob", ascending=False).head(top)
    return [{
        "name": row.name_, "team": team, "position": row.position,
        "headshot": row.headshot if isinstance(row.headshot, str) else None,
        "prob": round(row.prob * 100, 1), "season_tds": int(row.tds),
        "status": row.status if isinstance(row.status, str) else None,
    } for row in p.rename(columns={"name": "name_"}).itertuples()]
