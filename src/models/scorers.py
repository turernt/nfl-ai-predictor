"""Probabilité qu'un joueur marque au moins un touchdown (course ou réception).

Version 2 : le modèle apprend sur l'historique match par match de chaque joueur.
1. Journal joueur-match : courses, cibles, touchdowns et « TD attendus » (xTD). Chaque course ou cible
   pèse selon sa position sur le terrain (une course sur la ligne d'un yard vaut 0,58 TD, une cible
   à 20 yards de l'en-but 0,10).
2. Part du joueur dans les TD de son équipe : TD réels lissés vers la part de xTD, saison en cours et
   saison précédente, les matchs récents pesant plus lourd. Les forfaits sont retirés et leur part est
   redistribuée aux joueurs du même groupe de poste.
3. TD attendus de l'équipe d'après le score projeté par les cotes.
4. Régression logistique sur ces éléments, le temps de jeu (part des snaps), le poste, le scénario du
   match (équipe favorite ou non) et le statut « incertain ». Elle est réajustée à chaque mise à jour sur
   toutes les prédictions passées (deux saisons précédentes et saison en cours).

Test hors échantillon (mêmes joueurs, ancien modèle contre nouveau) : perte logarithmique 0,535 → 0,516
sur 2025 (3 500 cas) et 0,535 → 0,504 sur 2026 (1 663 cas).
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RECENCY = 0.85        # poids d'un match = 0,85 ^ (nombre de semaines écoulées)
PREV_GAP = 4          # la saison précédente compte comme 4 semaines de plus d'ancienneté
PRIOR_TDS = 6.0       # lissage : équivalent de 6 TD répartis selon la part de xTD
ACTIVE_WINDOW = 3     # joueur retenu s'il a joué l'un des 3 derniers matchs de son équipe
SNAP_RECENCY = 0.7    # le temps de jeu récent compte davantage
SNAP_DEFAULT = 0.45   # part des snaps supposée quand elle est inconnue
SKILL_POS = {"RB", "WR", "TE", "QB", "FB"}
OUT_STATUSES = {"Out", "Doubtful"}
CALIBRATION = 0.85    # échelle des touchdowns attendus
TD_PER_POINT = 0.105  # TD offensifs par point marqué, moyenne NFL
TRAIN_TOP = 8         # la régression est ajustée sur les 8 premiers candidats de chaque équipe
MIN_TRAIN_ROWS = 2000
RIDGE = 1.0

FEATURES = ["z", "is_qb", "is_rb", "is_te", "rb_m", "wr_m", "qb_m", "snap", "xpg", "quest", "lpts"]
# Coefficients de repli (ajustés sur 2023-2026), utilisés si l'ajustement en direct est impossible
DEFAULT_COEFS = [-1.585, 0.322, -0.582, 0.426, -0.123, 0.056, -0.025, -0.039, 1.739, 0.286, -0.420, 1.208]

# P(touchdown) d'une course / d'une cible selon la distance à l'en-but (1 à 99 yards), mesurée sur 2022-2025
XTD_RUSH = [0.58, 0.449, 0.356, 0.26, 0.223, 0.189, 0.149, 0.115, 0.099, 0.084, 0.077, 0.071, 0.059, 0.054, 0.048,
            0.043, 0.04, 0.035, 0.033, 0.03, 0.026, 0.024, 0.022, 0.019, 0.017, 0.016, 0.014, 0.013, 0.012, 0.011,
            0.011, 0.01, 0.009, 0.009, 0.009, 0.008, 0.008, 0.008, 0.008, 0.008] + [0.007] * 8 + [0.006] * 2 \
           + [0.005] + [0.004] * 3 + [0.003] * 16 + [0.002] * 14 + [0.001] * 15
XTD_REC = [0.559, 0.507, 0.461, 0.467, 0.409, 0.375, 0.325, 0.29, 0.258, 0.239, 0.214, 0.186, 0.168, 0.154, 0.136,
           0.13, 0.126, 0.111, 0.1, 0.1, 0.089, 0.082, 0.078, 0.071, 0.066, 0.062, 0.059, 0.052, 0.048, 0.046,
           0.042, 0.039, 0.038, 0.035, 0.033, 0.031, 0.028, 0.026, 0.025, 0.024, 0.022, 0.02, 0.019, 0.017, 0.016,
           0.015, 0.014, 0.013, 0.012, 0.012, 0.01, 0.01, 0.01, 0.009, 0.009, 0.008, 0.008, 0.008] + [0.007] * 5 \
          + [0.006] * 2 + [0.005] * 3 + [0.004] * 7 + [0.003] * 24


def player_weeks(stats: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    """Journal joueur-match (toutes saisons chargées) avec les TD attendus tirés du play-by-play."""
    p = pbp[pbp["play_type"].isin(["pass", "run"]) & (pbp["two_point_attempt"] != 1)]
    yl = p["yardline_100"].clip(1, 99).fillna(50).astype(int) - 1
    rush = p.assign(x=np.array(XTD_RUSH)[yl])[p["rusher_player_id"].notna()]
    rec = p.assign(x=np.array(XTD_REC)[yl])[p["receiver_player_id"].notna()]
    rx = rush.groupby(["season", "week", "rusher_player_id"])["x"].sum().rename("rush_x")
    cx = rec.groupby(["season", "week", "receiver_player_id"])["x"].sum().rename("rec_x")
    rx.index.names = cx.index.names = ["season", "week", "player_id"]
    s = stats[stats["position"].isin(SKILL_POS)].copy()
    s = s.join(rx, on=["season", "week", "player_id"]).join(cx, on=["season", "week", "player_id"])
    for c in ("rush_x", "rec_x", "carries", "targets", "rushing_tds", "receiving_tds",
              "rushing_yards", "receiving_yards", "receptions"):
        s[c] = s[c].fillna(0)
    s["x"] = s["rush_x"] + s["rec_x"]
    s["tds"] = s["rushing_tds"] + s["receiving_tds"]
    return s


def snap_table(snaps: pd.DataFrame | None, pfr_to_gsis: dict) -> pd.Series:
    """Part des snaps offensifs, indexée par (saison, semaine, joueur)."""
    if snaps is None or snaps.empty:
        return pd.Series(dtype=float)
    s = snaps.assign(player_id=snaps["pfr_player_id"].map(pfr_to_gsis)).dropna(subset=["player_id"])
    sn = s.set_index(["season", "week", "player_id"])["offense_pct"]
    return sn[~sn.index.duplicated()]


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = RIDGE) -> np.ndarray:
    """Régression logistique (Newton) avec une légère pénalité sur les coefficients."""
    X = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(X.shape[1])
    R = np.eye(X.shape[1]) * l2
    R[0, 0] = 0
    for _ in range(60):
        q = 1 / (1 + np.exp(-X @ b))
        w = q * (1 - q)
        step = np.linalg.solve((X * w[:, None]).T @ X + R, X.T @ (y - q) - R @ b)
        b += step
        if np.abs(step).max() < 1e-9:
            break
    return b


class ScorerModel:
    """Construit les candidats semaine par semaine, s'ajuste sur le passé et prédit la suite."""

    def __init__(self, pw: pd.DataFrame, snaps: pd.Series, sched: pd.DataFrame, injuries: pd.DataFrame | None):
        self.pw, self.sn, self.sched = pw, snaps, sched
        self.inj = injuries if injuries is not None else pd.DataFrame(columns=["season", "week", "gsis_id", "report_status"])
        self.seasons = sorted(pw["season"].unique())
        self._frames, self._coefs = {}, {}
        self.train_rows = 0

    # ----- données de base
    def statuses(self, season: int, week: int) -> dict:
        d = self.inj[(self.inj["season"] == season) & (self.inj["week"] == week) & self.inj["report_status"].notna()]
        return dict(zip(d["gsis_id"], d["report_status"]))

    def _history(self, season: int, week: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        pw = self.pw
        cur = pw[(pw["season"] == season) & (pw["week"] < week)]
        cur = cur.assign(age=week - 1 - cur["week"])
        prev = pw[pw["season"] == season - 1]
        prev = prev.assign(age=(week - 1) + PREV_GAP + (18 - prev["week"].clip(upper=18)))
        h = pd.concat([cur, prev], ignore_index=True)
        h["w"] = RECENCY ** h["age"]
        return h, cur

    def _team_td_per_point(self, cur: pd.DataFrame, season: int, week: int) -> dict:
        """TD offensifs par point marqué, par équipe, ramené vers la moyenne NFL pour limiter le bruit."""
        tds = cur.groupby(["team", "week"])["tds"].sum()
        g = self.sched[(self.sched["season"] == season) & (self.sched["week"] < week)].dropna(subset=["home_score"])
        pts = pd.concat([
            g[["home_team", "week", "home_score"]].set_axis(["team", "week", "pts"], axis=1),
            g[["away_team", "week", "away_score"]].set_axis(["team", "week", "pts"], axis=1)])
        if pts.empty:
            return {}
        pts = pts.join(tds.rename("t"), on=["team", "week"]).fillna({"t": 0})
        pts["w"] = RECENCY ** (week - 1 - pts["week"])
        out = {}
        for team, x in pts.groupby("team"):
            tds_pg, pts_pg = (x["t"] * x["w"]).sum() / x["w"].sum(), (x["pts"] * x["w"]).sum() / x["w"].sum()
            out[team] = (tds_pg + TD_PER_POINT * 40) / (pts_pg + 40) if pts_pg > 0 else TD_PER_POINT
        return out

    # ----- candidats d'une semaine
    def players(self, season: int, week: int, statuses: dict | None = None, roster: dict | None = None) -> pd.DataFrame:
        """Une ligne par joueur susceptible de jouer, avec ses indicateurs avant la semaine `week`.

        roster (semaine à venir uniquement) : {équipe: {player_id, ...}} = joueurs de l'effectif actif.
        Il écarte ceux qui ne sont plus dans l'effectif et réintègre ceux qui reviennent de blessure.
        """
        h, cur = self._history(season, week)
        if cur.empty:
            return pd.DataFrame()
        statuses = self.statuses(season, week) if statuses is None else statuses
        last = cur.sort_values("week").groupby("player_id").tail(1).set_index("player_id")
        team_weeks = cur.groupby("team")["week"].apply(lambda w: set(sorted(w.unique())[-ACTIVE_WINDOW:]))
        recent = pd.Series([wk in team_weeks.get(t, ()) for t, wk in zip(last["team"], last["week"])], index=last.index)
        team = last["team"].copy()
        keep = recent.copy()
        if roster:
            where = {pid: t for t, ids in roster.items() for pid in ids}
            on_roster = pd.Series(last.index.map(where), index=last.index)
            known = set(roster)                     # équipes dont l'effectif est connu
            team = on_roster.where(on_roster.notna(), team)
            keep = np.where(last["team"].isin(known) | on_roster.notna(), on_roster.notna(), recent)
            keep = pd.Series(keep, index=last.index)
        a = last.loc[keep, ["player_display_name", "position", "headshot_url", "week"]].rename(
            columns={"player_display_name": "name", "headshot_url": "headshot", "week": "last_week"})
        a["team"] = team[keep]
        hh = h[h["player_id"].isin(a.index)]
        cols = ["x", "tds", "rush_x", "rec_x"]
        ws = hh[cols].multiply(hh["w"], axis=0).assign(player_id=hh["player_id"].values, g=hh["w"].values)
        a = a.join(ws.groupby("player_id").sum())
        c = cur[cur["player_id"].isin(a.index)]
        a["season_tds"] = c.groupby("player_id")["tds"].sum().reindex(a.index).fillna(0).astype(int)
        a["games"] = c.groupby("player_id").size().reindex(a.index).fillna(0).astype(int)
        # temps de jeu : part des snaps offensifs, pondérée par la récence
        if len(self.sn):
            keys = list(zip([season] * len(c), c["week"].astype(int), c["player_id"]))
            cs = c.assign(sn=self.sn.reindex(keys).values, w=SNAP_RECENCY ** (week - 1 - c["week"])).dropna(subset=["sn"])
            a["snap"] = ((cs["sn"] * cs["w"]).groupby(cs["player_id"]).sum()
                         / cs["w"].groupby(cs["player_id"]).sum()).reindex(a.index)
        else:
            a["snap"] = np.nan
        a["status"] = a.index.map(statuses)
        a["out"] = a["status"].isin(OUT_STATUSES)
        # part des TD de l'équipe : TD réels lissés vers la part de xTD
        tot = a.groupby("team")[["tds", "x"]].transform("sum")
        xshare = (a["x"] / tot["x"].where(tot["x"] > 0)).fillna(0)
        a["share"] = (a["tds"] + PRIOR_TDS * xshare) / (tot["tds"] + PRIOR_TDS)
        # composition : la part des forfaits est redistribuée dans leur groupe de poste
        key = a["team"] + "|" + a["position"].replace({"FB": "RB", "TE": "WR"})
        full = a.groupby(key)["share"].transform("sum")
        left = a["share"].where(~a["out"], 0).groupby(key).transform("sum")
        a["share"] = np.where(left > 0, a["share"] * full / left.where(left > 0, 1), a["share"])
        a["td_per_pt"] = a["team"].map(self._team_td_per_point(cur, season, week)).fillna(TD_PER_POINT)
        return a[~a["out"]]

    @staticmethod
    def with_game(players: pd.DataFrame, team: str, exp_points: float, margin: float) -> pd.DataFrame:
        """Ajoute le contexte du match (points attendus, marge attendue) et les variables du modèle."""
        d = players[players["team"] == team].copy()
        if d.empty:
            return d
        lam = d["td_per_pt"] * exp_points * d["share"]
        raw = (1 - np.exp(-CALIBRATION * lam)).clip(1e-4, 1 - 1e-4)
        pos = d["position"].replace({"FB": "RB"})
        m = margin / 7.0
        d["lam"] = lam
        d["z"] = np.log(raw / (1 - raw))
        d["is_qb"], d["is_rb"], d["is_te"] = (pos == "QB") * 1.0, (pos == "RB") * 1.0, (pos == "TE") * 1.0
        d["rb_m"], d["qb_m"] = d["is_rb"] * m, d["is_qb"] * m
        d["wr_m"] = pos.isin(["WR", "TE"]) * m
        d["snap"] = d["snap"].fillna(SNAP_DEFAULT)
        d["xpg"] = np.log(d["x"] / d["g"].clip(lower=1e-6) + 0.02)
        d["quest"] = (d["status"] == "Questionable") * 1.0
        d["lpts"] = np.log(max(exp_points, 3.0) / 22)
        return d

    def frame(self, season: int, week: int) -> pd.DataFrame:
        """Candidats d'une semaine déjà jouée, avec le résultat (a marqué ou non). Sert à l'apprentissage."""
        if (season, week) in self._frames:
            return self._frames[(season, week)]
        g = self.sched[(self.sched["season"] == season) & (self.sched["week"] == week)].dropna(subset=["home_score"])
        rows = []
        pl = self.players(season, week) if len(g) else pd.DataFrame()
        if not pl.empty:
            for x in g.itertuples():
                home_pts, away_pts, margin = line_points(x.spread_line, x.total_line)
                for team, pts, mg in ((x.home_team, home_pts, margin), (x.away_team, away_pts, -margin)):
                    d = self.with_game(pl, team, pts, mg)
                    if len(d):
                        rows.append(d.assign(game_id=x.game_id))
        if rows:
            out = pd.concat(rows)
            act = self.pw[(self.pw["season"] == season) & (self.pw["week"] == week)].set_index("player_id")["tds"]
            out["y"] = (out.index.map(act).fillna(0) > 0).astype(int)
            out["rank"] = out.groupby(["game_id", "team"])["lam"].rank(ascending=False, method="first")
        else:
            out = pd.DataFrame()
        self._frames[(season, week)] = out
        return out

    # ----- apprentissage continu
    def coefs(self, season: int, week: int) -> np.ndarray:
        """Coefficients ajustés sur toutes les semaines jouées avant (saison, semaine)."""
        if (season, week) in self._coefs:
            return self._coefs[(season, week)]
        frames = []
        for s in (season - 2, season - 1, season):
            if s - 1 not in self.seasons:       # il faut la saison précédente pour l'historique des joueurs
                continue
            weeks = self.sched[(self.sched["season"] == s) & (self.sched["game_type"] == "REG")]["week"].unique()
            for w in sorted(weeks):
                if s == season and w >= week:
                    break
                f = self.frame(s, int(w))
                if len(f):
                    frames.append(f[f["rank"] <= TRAIN_TOP])
        b = np.array(DEFAULT_COEFS)
        n = sum(len(f) for f in frames)
        if n >= MIN_TRAIN_ROWS:
            tr = pd.concat(frames)
            try:
                b = fit_logistic(tr[FEATURES].values.astype(float), tr["y"].values.astype(float))
            except np.linalg.LinAlgError:
                logger.warning("Ajustement du modèle de buteurs impossible : coefficients par défaut")
                n = 0
        else:
            n = 0
        self.train_rows = n
        self._coefs[(season, week)] = b
        return b

    def predict(self, d: pd.DataFrame, season: int, week: int) -> pd.Series:
        b = self.coefs(season, week)
        z = b[0] + d[FEATURES].values.astype(float) @ b[1:]
        return pd.Series(1 / (1 + np.exp(-z)), index=d.index)

    # ----- journal des derniers matchs (affiché sur le site)
    def form(self, player_id: str, season: int, week: int, n: int = 5) -> list[dict]:
        c = self.pw[(self.pw["player_id"] == player_id) & (self.pw["season"] == season) & (self.pw["week"] < week)]
        out = []
        for r in c.sort_values("week").tail(n).itertuples():
            sn = self.sn.get((season, int(r.week), player_id)) if len(self.sn) else None
            out.append({"week": int(r.week), "opp": r.opponent_team, "car": int(r.carries), "tgt": int(r.targets),
                        "rec": int(r.receptions), "yds": int(r.rushing_yards + r.receiving_yards),
                        "td": int(r.tds), "snap": None if sn is None or pd.isna(sn) else round(float(sn) * 100)})
        return out


def line_points(spread_line, total_line, default_total: float = 44.0) -> tuple[float, float, float]:
    """Points attendus (domicile, extérieur) et marge du domicile d'après les lignes nflverse."""
    margin = 0.0 if pd.isna(spread_line) else float(spread_line)     # > 0 : domicile favori
    total = default_total if pd.isna(total_line) else float(total_line)
    return total / 2 + margin / 2, total / 2 - margin / 2, margin


def likely_scorers(model: ScorerModel, players: pd.DataFrame, season: int, week: int, team: str,
                   exp_points: float, margin: float, top: int = 6, depth: dict | None = None,
                   with_form: bool = True) -> list[dict]:
    if players is None or players.empty:
        return []
    d = model.with_game(players, team, exp_points, margin)
    if d.empty:
        return []
    d["prob"] = model.predict(d, season, week)
    d = d.sort_values("prob", ascending=False).head(top)
    out = []
    for pid, r in d.iterrows():
        form = model.form(pid, season, week) if with_form else []
        item = {
            "player_id": pid, "name": r["name"], "team": team, "position": r["position"],
            "headshot": r["headshot"] if isinstance(r["headshot"], str) else None,
            "prob": round(float(r["prob"]) * 100, 1), "season_tds": int(r["season_tds"]),
            "status": r["status"] if isinstance(r["status"], str) else None,
        }
        if with_form:
            item.update({
                "games": int(r["games"]),
                "snap": None if pd.isna(r["snap"]) else round(float(r["snap"]) * 100),
                "xtd": round(float(r["x"] / max(r["g"], 1e-6)), 2),
                "depth": (depth or {}).get(pid),
                "form": form,
                "scored_last": sum(1 for f in form if f["td"] > 0),
            })
        out.append(item)
    return out
