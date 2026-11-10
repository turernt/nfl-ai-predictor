import json
import logging
import shutil
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.config import DATA_DIR, WEB_DATA_DIR, FIRST_SEASON, HFA, ELO_PER_POINT
from src.ingestion.loader import (load_schedules, load_teams, load_player_stats, load_injury_report, load_pbp,
                                  load_injuries_all, load_snaps, load_depth_chart, load_roster_status)
from src.models.elo_engine import NFLEloModel, confidence_label
from src.models.ratings import (epa_ratings, epa_margin, qb_table, qb_adjustment, rest_adjustment, win_prob)
from src.models.scorers import ScorerModel, likely_scorers, player_weeks, snap_table, FEATURES
from src.models import lineup as lineup_mod
from src.ingestion.odds import get_odds, consensus, find as find_odds
from src.models.season_sim import simulate
from src.models.devig import shin, quarter_kelly
from src.models import market_ratings
from src.ingestion.loader import load_injury_details
from src.ingestion.weather import forecast, kickoff_utc
from src.tracking import update_log, summarize

ROUNDS = {"WC": "Wild Card", "DIV": "Tour de division", "CON": "Finale de conférence", "SB": "Super Bowl"}

logger = logging.getLogger(__name__)

DEFAULT_TOTAL = 44.0     # total de points moyen en NFL, utilisé sans ligne des bookmakers
ELO_WEIGHT = 0.5         # modèle maison = 50 % Elo + 50 % EPA, puis QB et repos
# Étude 2023-2026 (899 matchs) : les cotes du marché prédisent mieux que le modèle maison et que
# tout mélange des deux (Brier 0,213 contre 0,215 pour 2/3-1/3). La probabilité affichée est donc
# celle des cotes (marge du bookmaker retirée) ; le modèle maison sert de second avis.
MARKET_WEIGHT = 1.0
TIERS = [(0.8, "Très sûr"), (0.7, "Sûr"), (0.6, "Probable"), (0.5, "Serré")]
VALUE_MIN_EV = 0.03      # cote française signalée si elle dépasse le juste prix d'au moins 3 %
STALE_GAME = timedelta(hours=36)   # match sans score 36 h après le coup d'envoi : reporté ou annulé, ignoré


def no_vig_prob(home_ml, away_ml) -> float | None:
    """Probabilité de victoire à domicile tirée des cotes américaines, marge retirée."""
    if pd.isna(home_ml) or pd.isna(away_ml):
        return None
    imp = lambda o: 100 / (o + 100) if o > 0 else -o / (-o + 100)
    return shin([imp(home_ml), imp(away_ml)])[0]   # méthode de Shin (voir src/models/devig.py)


def readable_on_dark(c1, c2) -> str:
    """Couleur d'équipe lisible sur fond sombre : la secondaire si la principale est trop foncée."""
    def lum(c):
        try:
            r, g, b = (int(str(c).lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except (ValueError, TypeError):
            return 0.0
        f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    if lum(c1) >= 0.06 or not isinstance(c2, str):
        return c1
    return c2 if lum(c2) > lum(c1) else c1


def _dec(ml) -> float | None:
    """Cote américaine -> cote décimale (marge du bookmaker incluse)."""
    if pd.isna(ml):
        return None
    return round(1 + ml / 100 if ml > 0 else 1 + 100 / -ml, 3)


def _units(bets) -> dict:
    """Bilan à mise fixe (1 unité par pari) aux vraies cotes, marge comprise."""
    bets = [b for b in bets if b["pick_odds"] and b["correct"] is not None]
    profit = sum((b["pick_odds"] - 1) if b["correct"] else -1 for b in bets)
    return {"bets": len(bets), "units": round(profit, 2), "roi": round(profit / len(bets) * 100, 1) if bets else None}


def tier_of(p: float) -> str:
    return next(name for th, name in TIERS if p >= th)


def market_reliability(sched: pd.DataFrame) -> list[dict]:
    """Taux de victoire réel du favori des cotes, par palier de probabilité (depuis 2012)."""
    g = sched[(sched.season >= 2012)].dropna(subset=["home_score", "home_moneyline", "away_moneyline"])
    g = g[g.home_score != g.away_score]
    rows = []
    for x in g.itertuples():
        p = no_vig_prob(x.home_moneyline, x.away_moneyline)
        fav = max(p, 1 - p)
        rows.append((tier_of(fav), fav, (p >= 0.5) == (x.home_score > x.away_score)))
    df = pd.DataFrame(rows, columns=["tier", "p", "win"])
    out = []
    for th, name in TIERS:
        d = df[df.tier == name]
        out.append({"tier": name, "min": th, "games": len(d),
                    "predicted": round(d.p.mean() * 100, 1) if len(d) else None,
                    "actual": round(d.win.mean() * 100, 1) if len(d) else None})
    return out


def market_roi(sched: pd.DataFrame) -> dict:
    """Rendement d'une mise fixe sur chaque favori des cotes de clôture nflverse, depuis 2012."""
    g = sched[(sched.season >= 2012)].dropna(subset=["home_score", "home_moneyline", "away_moneyline"])
    g = g[g.home_score != g.away_score]
    pl = []
    for x in g.itertuples():
        home_fav = no_vig_prob(x.home_moneyline, x.away_moneyline) >= 0.5
        price = _dec(x.home_moneyline if home_fav else x.away_moneyline)
        pl.append(price - 1 if home_fav == (x.home_score > x.away_score) else -1)
    return {"bets": len(pl), "roi": round(sum(pl) / len(pl) * 100, 1) if pl else None}


def current_season(now: datetime | None = None) -> int:
    now = now or datetime.now()
    return now.year if now.month >= 8 else now.year - 1


def _fr(x: float) -> str:
    return f"{x:+.1f}".replace("-", "−").replace(".", ",")


def _commentary(fav: str, prob: float, home_is_fav: bool, neutral: bool, model_spread: float,
                vegas: float | None, qb_notes: list[str]) -> str:
    venue = "" if neutral else (", à domicile" if home_is_fav else ", à l’extérieur")
    text = f"Avantage {fav} ({int(prob + 0.5)}\u00a0%){venue}."
    if vegas is not None and (model_spread < 0) != (vegas < 0) and abs(model_spread - vegas) >= 1.5:
        text += " Notre modèle maison voit plutôt l’autre équipe gagner : signal de prudence."
    elif vegas is not None and abs(model_spread - vegas) >= 3:
        text += f" Le modèle maison ({_fr(model_spread)}) s’écarte des bookmakers ({_fr(vegas)})."
    for note in qb_notes:
        text += " " + note
    return text


class Context:
    """Tout ce qui est connu avant une semaine donnée."""

    def __init__(self, pbp, season, week, scorer_model, statuses=None, lineups=None):
        self.season, self.week = season, week
        self.epa = epa_ratings(pbp, season, week)
        self.qbs, self.qb_base, self.qb_repl = qb_table(pbp, season, week)
        self.model = scorer_model
        self.live = lineups is not None      # semaine à venir : composition connue, journal des matchs affiché
        self.lineups = lineups or {}
        self.statuses = statuses if statuses is not None else scorer_model.statuses(season, week)
        # effectif actif de chaque équipe : écarte les joueurs sortis de l'effectif, réintègre ceux qui reviennent
        roster = {t: l["active_ids"] for t, l in self.lineups.items() if l.get("active_ids")} or None
        self.players = scorer_model.players(season, week, statuses=self.statuses, roster=roster)


def predict_game(g, elo: dict, ctx: Context, team_info, odds: dict | None = None) -> dict:
    neutral = g.location == "Neutral"
    elo_m = (elo.get(g.home_team, 1505) + (0 if neutral else HFA) - elo.get(g.away_team, 1505)) / ELO_PER_POINT
    epa_m = epa_margin(ctx.epa, g.home_team, g.away_team, neutral)
    # Composition : si le QB du calendrier est forfait, on prend le suivant dans la hiérarchie
    home_qb_id, home_qb_name, home_qb_new = lineup_mod.starting_qb(
        ctx.lineups.get(g.home_team), g.home_qb_id, g.home_qb_name, ctx.statuses)
    away_qb_id, away_qb_name, away_qb_new = lineup_mod.starting_qb(
        ctx.lineups.get(g.away_team), g.away_qb_id, g.away_qb_name, ctx.statuses)
    qb_h = qb_adjustment(ctx.qbs, ctx.qb_base, ctx.qb_repl, g.home_team, home_qb_id)
    qb_a = qb_adjustment(ctx.qbs, ctx.qb_base, ctx.qb_repl, g.away_team, away_qb_id)
    rest_m = rest_adjustment(g.home_rest, g.away_rest)
    model_spread = -(ELO_WEIGHT * elo_m + (1 - ELO_WEIGHT) * epa_m + qb_h - qb_a + rest_m)
    vegas = None if pd.isna(g.spread_line) else -float(g.spread_line)
    spread = MARKET_WEIGHT * vegas + (1 - MARKET_WEIGHT) * model_spread if vegas is not None else model_spread
    p_ml = no_vig_prob(g.home_moneyline, g.away_moneyline)
    p_home = (p_ml if p_ml is not None else win_prob(spread)) * 100
    source = "cotes nflverse" if p_ml is not None else ("spread" if vegas is not None else "modèle")
    total_line = None if pd.isna(g.total_line) else float(g.total_line)
    if odds:  # consensus de plusieurs bookmakers, prioritaire sur la ligne unique nflverse
        p_home = odds["prob_home"] * 100
        source = f"moyenne de {odds['n_books']} bookmakers"
        if odds["spread"] is not None:
            vegas = float(odds["spread"])
            spread = vegas
        if odds["total"] is not None:
            total_line = float(odds["total"])

    p_home = round(p_home, 1)     # même arrondi partout (cartes, commentaire, pronostics)
    total = DEFAULT_TOTAL if total_line is None else total_line
    home_pts, away_pts = total / 2 - spread / 2, total / 2 + spread / 2
    scorers = []
    for team, pts, margin in ((g.away_team, away_pts, spread), (g.home_team, home_pts, -spread)):
        scorers += likely_scorers(ctx.model, ctx.players, ctx.season, ctx.week, team, pts, margin,
                                  depth=(ctx.lineups.get(team) or {}).get("labels"), with_form=ctx.live)
    home, away = team_info(g.home_team), team_info(g.away_team)
    home_fav = p_home >= 50
    qb_notes = [f"QB titulaire indisponible chez les {t['nick']} : {name} attendu."
                for t, name, new in ((home, home_qb_name, home_qb_new), (away, away_qb_name, away_qb_new)) if new]
    qb_notes += [f"QB annoncé chez les {t['nick']} ({name}) : {_fr(v)} pt par rapport à leur niveau habituel."
                 for t, name, v in ((home, home_qb_name, qb_h), (away, away_qb_name, qb_a)) if abs(v) >= 2]
    return {
        "game_id": g.game_id, "week": int(g.week), "game_type": g.game_type,
        "gameday": g.gameday, "gametime": g.gametime, "neutral_site": neutral,
        "home": home, "away": away,
        "prob_home_win": round(p_home, 1), "prob_away_win": round(100 - p_home, 1),
        "predicted_spread": round(spread, 1), "model_spread": round(model_spread, 1),
        "model_prob_home": round(win_prob(model_spread) * 100, 1),
        "vegas_spread": vegas, "vegas_total": total_line,
        "odds": None if not odds else {
            "n_books": odds["n_books"], "books": odds["books"], "best_fr": odds["best_fr"],
            "fair_home": round(100 / p_home, 2), "fair_away": round(100 / (100 - p_home), 2),
        },
        "projected_score": {"home": round(home_pts), "away": round(away_pts)},
        "confidence_score": confidence_label(p_home),
        "tier": tier_of(max(p_home, 100 - p_home) / 100), "prob_source": source,
        "factors": {
            "elo": round(elo_m, 1), "epa": round(epa_m, 1),
            "qb": {"home": round(qb_h, 1), "away": round(qb_a, 1),
                   "home_name": home_qb_name if isinstance(home_qb_name, str) else None,
                   "away_name": away_qb_name if isinstance(away_qb_name, str) else None},
            "rest": {"pts": round(rest_m, 1),
                     "home_days": None if pd.isna(g.home_rest) else int(g.home_rest),
                     "away_days": None if pd.isna(g.away_rest) else int(g.away_rest)},
            "market_weight": 1.0 if vegas is not None else 0.0,
        },
        "scorers": sorted(scorers, key=lambda x: x["prob"], reverse=True),
        "commentary": _commentary((home if home_fav else away)["nick"], max(p_home, 100 - p_home),
                                  home_fav, neutral, model_spread, vegas, qb_notes),
    }


def compact(p: dict) -> dict:
    """Version archivée d'un pronostic : sans le journal détaillé des buteurs (le plus volumineux)."""
    a = {k: v for k, v in p.items() if k not in ("line_history",)}
    a["scorers"] = [{k: v for k, v in s.items() if k != "form"} for s in p.get("scorers", [])]
    return a


def settle(a: dict, played: pd.DataFrame, td: dict, stats_teams: set) -> None:
    """Ajoute le score final, le résultat du pronostic et les buteurs ayant marqué."""
    if a["game_id"] not in played.index:
        return
    g = played.loc[a["game_id"]]
    a["status"] = "final"
    a["score"] = {"home": int(g.home_score), "away": int(g.away_score)}
    a["pick_correct"] = None if g.home_score == g.away_score else bool((a["prob_home_win"] >= 50) == (g.home_score > g.away_score))
    wk = int(g.week)
    if (wk, a["home"]["abbr"]) in stats_teams and (wk, a["away"]["abbr"]) in stats_teams:
        for s in a.get("scorers", []):
            s["scored"] = bool(td.get((wk, s.get("player_id")), 0) > 0)


def run_pipeline() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    season = current_season()
    sched = load_schedules(list(range(FIRST_SEASON, season + 1)))
    teams = load_teams().set_index("team_abbr")
    # Trois saisons d'historique en plus de la saison en cours : le modèle de buteurs apprend dessus
    hist_seasons = list(range(season - 3, season + 1))
    pbp = load_pbp(hist_seasons)
    stats_all = load_player_stats(hist_seasons)
    stats = stats_all[stats_all["season"] == season]
    snaps, id_map = load_snaps(hist_seasons)
    scorer_model = ScorerModel(player_weeks(stats_all, pbp), snap_table(snaps, id_map), sched,
                               load_injuries_all(hist_seasons))

    cur_sched = sched[sched.season == season]
    now = datetime.now(timezone.utc)
    kickoffs = {g.game_id: kickoff_utc(g.gameday, g.gametime) for g in cur_sched.itertuples()}
    # Semaine en cours = la plus ancienne avec un match sans score, sauf match reporté ou annulé (plus de 36 h)
    pending = [g.week for g in cur_sched[cur_sched.home_score.isna()].itertuples()
               if kickoffs[g.game_id] is None or kickoffs[g.game_id] > now - STALE_GAME]
    week = int(min(pending)) if pending else int(cur_sched.week.max()) + 1

    # --- Elo, avec un instantané avant chaque semaine de la saison en cours
    model = NFLEloModel()
    snapshots, last_season = {}, None
    played = sched.dropna(subset=["home_score", "away_score"])
    for g in played.itertuples():
        if g.season != last_season:
            if last_season is not None:
                model.new_season()
            last_season = g.season
        if g.season == season and g.week not in snapshots:
            snapshots[g.week] = dict(model.ratings)
        model.update(g.home_team, g.away_team, g.home_score, g.away_score, g.location == "Neutral")
    if last_season is not None and last_season < season:
        model.new_season()
    snapshots.setdefault(week, dict(model.ratings))
    elo_now = dict(model.ratings)

    record = {}
    for g in played[played.season == season].itertuples():
        for t, us, them in ((g.home_team, g.home_score, g.away_score), (g.away_team, g.away_score, g.home_score)):
            w, l, d = record.get(t, (0, 0, 0))
            record[t] = (w + (us > them), l + (us < them), d + (us == them))

    def make_team_info(epa: pd.DataFrame):
        def team_info(abbr: str) -> dict:
            row = teams.loc[abbr] if abbr in teams.index else None
            w, l, d = record.get(abbr, (0, 0, 0))
            return {
                "abbr": abbr,
                "name": row["team_name"] if row is not None else abbr,
                "nick": row["team_nick"] if row is not None else abbr,
                "color": row["team_color"] if row is not None else "#444444",
                "color_dark": readable_on_dark(row["team_color"], row["team_color2"]) if row is not None else "#888888",
                "logo": row["team_logo_espn"] if row is not None else None,
                "elo": round(elo_now.get(abbr, 1505), 1),
                "record": f"{w}-{l}" + (f"-{d}" if d else ""),
                "off_rank": int(epa.at[abbr, "off_rank"]) if abbr in epa.index else None,
                "def_rank": int(epa.at[abbr, "def_rank"]) if abbr in epa.index else None,
            }
        return team_info

    # --- Bilan : chaque semaine passée, prédite avec les seules infos disponibles avant
    backtest = []
    for wk in sorted(w for w in cur_sched.week.unique() if w <= week):   # semaine en cours : matchs déjà joués
        ctx = Context(pbp, season, wk, scorer_model)
        info = make_team_info(ctx.epa)
        actual_td = stats[(stats.week == wk)].assign(
            t=lambda d: d["rushing_tds"].fillna(0) + d["receiving_tds"].fillna(0)).set_index("player_id")["t"]
        for g in played[(played.season == season) & (played.week == wk)].itertuples():
            pr = predict_game(g, snapshots[wk], ctx, info)
            home_won = g.home_score > g.away_score
            tie = g.home_score == g.away_score
            for sc in pr["scorers"]:
                sc["scored"] = bool(actual_td.get(sc["player_id"], 0) > 0)
            backtest.append({
                "game_id": pr["game_id"], "week": int(wk), "home": pr["home"]["abbr"], "away": pr["away"]["abbr"],
                "home_nick": pr["home"]["nick"], "away_nick": pr["away"]["nick"],
                "home_logo": pr["home"]["logo"], "away_logo": pr["away"]["logo"],
                "score": {"home": int(g.home_score), "away": int(g.away_score)},
                "pick": pr["home"]["abbr"] if pr["prob_home_win"] >= 50 else pr["away"]["abbr"],
                "pick_prob": max(pr["prob_home_win"], pr["prob_away_win"]),
                "pick_odds": _dec(g.home_moneyline if pr["prob_home_win"] >= 50 else g.away_moneyline),
                "correct": None if tie else (pr["prob_home_win"] >= 50) == home_won,
                "model_correct": None if tie else (pr["model_prob_home"] >= 50) == home_won,
                "market_correct": None if tie or pr["vegas_spread"] in (None, 0) else (pr["vegas_spread"] < 0) == home_won,
                "brier": None if tie else round((pr["prob_home_win"] / 100 - home_won) ** 2, 4),
                "ats_edge": None if pr["vegas_spread"] is None else round(pr["model_spread"] - pr["vegas_spread"], 1),
                "ats_cover": None if pr["vegas_spread"] is None or (g.home_score - g.away_score) + pr["vegas_spread"] == 0
                             else bool((g.home_score - g.away_score) + pr["vegas_spread"] > 0),
                "model_brier": None if tie else round((pr["model_prob_home"] / 100 - home_won) ** 2, 4),
                "scorers": [{"name": s["name"], "team": s["team"], "prob": s["prob"], "scored": s["scored"]}
                            for s in pr["scorers"][:3]],
                "all_scorers": [(s["prob"], s["scored"]) for s in pr["scorers"]],
            })

    decided = [b for b in backtest if b["correct"] is not None]
    mk = [b for b in decided if b["market_correct"] is not None]
    sc_all = [x for b in backtest for x in b["all_scorers"]]
    sc_top = [s for b in backtest for s in b["scorers"]]
    weeks = sorted({b["week"] for b in backtest})
    safe = [b for b in decided if b["pick_prob"] >= 70]
    summary = {
        "safe_picks": {"n": len(safe), "correct": sum(b["correct"] for b in safe)},
        "units_all": _units(decided), "units_safe": _units(safe),
        "games": len(decided),
        "correct": sum(b["correct"] for b in decided),
        "brier": round(sum(b["brier"] for b in decided) / len(decided), 3) if decided else None,
        "model_correct": sum(b["model_correct"] for b in decided),
        "model_brier": round(sum(b["model_brier"] for b in decided) / len(decided), 3) if decided else None,
        "market_games": len(mk), "market_correct": sum(b["market_correct"] for b in mk),
        "scorer_picks": len(sc_top), "scorer_hits": sum(s["scored"] for s in sc_top),
        "scorer_expected": round(sum(s["prob"] for s in sc_top) / 100, 1),
        "scorer_all_n": len(sc_all), "scorer_all_hits": sum(h for _, h in sc_all),
        "scorer_all_expected": round(sum(p for p, _ in sc_all) / 100, 1),
        "scorer_brier": round(sum((p / 100 - h) ** 2 for p, h in sc_all) / len(sc_all), 4) if sc_all else None,
        "weeks": [{"week": w, "games": len([b for b in decided if b["week"] == w]),
                   "correct": sum(b["correct"] for b in decided if b["week"] == w)} for w in weeks],
    }
    # Paris contre l'écart : quand le modèle diffère du marché d'au moins 3 points, a-t-il raison ?
    ats = [b for b in backtest if b["ats_edge"] is not None and abs(b["ats_edge"]) >= 3 and b["ats_cover"] is not None]
    # edge < 0 => le modèle est plus favorable au domicile que le marché => pari sur le domicile
    summary["ats_games"] = len(ats)
    summary["ats_correct"] = sum((b["ats_edge"] < 0) == b["ats_cover"] for b in ats)
    # Fiabilité des buteurs par palier de probabilité
    buckets = [(50, 101, "50 % et plus"), (40, 50, "40 à 50 %"), (30, 40, "30 à 40 %"), (0, 30, "moins de 30 %")]
    summary["scorer_tiers"] = [{
        "label": lab, "min": lo, "n": len(sel := [h for p, h in sc_all if lo <= p < hi]),
        "predicted": round(sum(p for p, _ in sc_all if lo <= p < hi) / len(sel), 1) if sel else None,
        "actual": round(sum(sel) / len(sel) * 100, 1) if sel else None} for lo, hi, lab in buckets]
    for b in backtest:
        b.pop("all_scorers")

    # --- Semaine en cours
    # Un match pas encore commencé est recalculé à chaque passage ; dès le coup d'envoi, sa dernière version publiée
    # est figée (data/archive.json) : cotes en direct ignorées, page de match conservée après la fin de la semaine.
    week_games = cur_sched[cur_sched.week == week]
    fresh_games = [g for g in week_games.itertuples() if pd.isna(g.home_score)
                   and (kickoffs[g.game_id] is None or kickoffs[g.game_id] > now)]
    statuses = load_injury_report(season, week)
    # Composition probable : hiérarchie des postes, effectif actif et rapport de blessures
    lineups = lineup_mod.build(load_depth_chart(season), load_roster_status(season), statuses)
    ctx = Context(pbp, season, week, scorer_model, statuses=statuses, lineups=lineups)
    team_info = make_team_info(ctx.epa)
    events, odds_status = get_odds(DATA_DIR / "odds_cache.json", [kickoffs[g.game_id] for g in fresh_games])
    cons = consensus(events, {row["team_name"]: abbr for abbr, row in teams.iterrows()}, now)
    fresh = [predict_game(g, elo_now, ctx, team_info, odds=find_odds(cons, g.home_team, g.away_team, g.gameday))
             for g in fresh_games]
    n_cons = sum(1 for p in fresh if p["odds"])
    inj = load_injury_details(season, week)
    for p, g in zip(fresh, fresh_games):
        p["injuries"] = {"home": inj.get(p["home"]["abbr"], [])[:10], "away": inj.get(p["away"]["abbr"], [])[:10]}
        p["weather"] = forecast(p["home"]["abbr"], p["neutral_site"], p["gameday"], p["gametime"])
        p["round"] = ROUNDS.get(g.game_type)
        p["lineup"] = {side: (lineups.get(p[side]["abbr"]) or {}).get("players", []) for side in ("home", "away")}
        p["status"] = "upcoming"

    top_scorers = sorted((dict(sc, game_id=pr["game_id"],
                               opponent=pr["home"]["abbr"] if sc["team"] == pr["away"]["abbr"] else pr["away"]["abbr"])
                          for pr in fresh for sc in pr["scorers"]),
                         key=lambda x: x["prob"], reverse=True)[:12]

    reliability = market_reliability(sched)
    rel = {r["tier"]: r for r in reliability}
    sc_rel = summary["scorer_tiers"]
    def sc_tier(p):
        return next((t for t in sc_rel if p >= t["min"]), sc_rel[-1])
    picks_win = []
    for pr in fresh:
        home_fav = pr["prob_home_win"] >= 50
        p = max(pr["prob_home_win"], pr["prob_away_win"])
        fav, opp = (pr["home"], pr["away"]) if home_fav else (pr["away"], pr["home"])
        model_fav_home = pr["model_spread"] < 0
        side = "home" if home_fav else "away"
        best = (pr["odds"] or {}).get("best_fr", {}).get(side) if pr["odds"] else None
        picks_win.append({
            "best_fr": best, "ev": round((best["price"] * p / 100 - 1) * 100, 1) if best else None,
            "source": pr["prob_source"],
            "game_id": pr["game_id"], "gameday": pr["gameday"], "gametime": pr["gametime"],
            "team": fav, "opponent": opp, "home": home_fav, "prob": p, "tier": pr["tier"],
            "fair_odds": round(100 / p, 2), "hist": rel.get(pr["tier"]),
            "model_agrees": model_fav_home == home_fav,
            "model_prob": pr["model_prob_home"] if home_fav else round(100 - pr["model_prob_home"], 1),
        })
    picks_win.sort(key=lambda x: x["prob"], reverse=True)
    picks_scorers = [dict(sc, fair_odds=round(100 / sc["prob"], 2), hist=sc_tier(sc["prob"]))
                     for sc in top_scorers if sc["prob"] >= 40]
    # Cotes françaises au-dessus du juste prix (juste prix = médiane des bookmakers à faible marge)
    value = []
    for pr in fresh:
        if not pr["odds"]:
            continue
        for side, team, opp, p in (("home", pr["home"], pr["away"], pr["prob_home_win"]),
                                   ("away", pr["away"], pr["home"], pr["prob_away_win"])):
            best = pr["odds"]["best_fr"].get(side)
            if best and best["price"] * p / 100 >= 1 + VALUE_MIN_EV:
                value.append({"game_id": pr["game_id"], "gameday": pr["gameday"], "gametime": pr["gametime"],
                              "team": team, "opponent": opp, "prob": p, "price": best["price"], "book": best["book"],
                              "stake_pct": round(quarter_kelly(p / 100, best["price"]) * 100, 2),
                              "fair_odds": round(100 / p, 2), "ev": round((best["price"] * p / 100 - 1) * 100, 1)})
    value.sort(key=lambda x: x["ev"], reverse=True)
    # Badges des cartes de match : occasion, blessés importants, vent
    value_ids = {v["game_id"] for v in value}
    for pr in fresh:
        key_out = sum(1 for side in ("home", "away") for x in (pr.get("injuries") or {}).get(side, [])
                      if x["status"] in ("Out", "Doubtful") and x["position"] in ("QB", "RB", "WR", "TE"))
        pr["flags"] = {"value": pr["game_id"] in value_ids, "key_out": key_out,
                       "windy": bool((pr.get("weather") or {}).get("windy")),
                       "dome": (pr.get("weather") or {}).get("roof") == "dome"}
    picks = {
        "value": value,
        "safest": [x for x in picks_win if x["prob"] >= 70],
        "coin_flips": [x for x in picks_win if x["prob"] < 57],
        "scorers": picks_scorers,
        "reliability": reliability,
        "market_roi": market_roi(sched),
    }

    # Suivi en conditions réelles : vainqueurs, buteurs et cotes signalées, figés au coup d'envoi
    tds = stats.assign(t=stats["rushing_tds"].fillna(0) + stats["receiving_tds"].fillna(0))
    td = tds.groupby(["week", "player_id"])["t"].sum().to_dict()
    td = {(int(w), pid): v for (w, pid), v in td.items()}
    stats_teams = {(int(w), t) for w, t in zip(stats["week"], stats["team"])}
    log = update_log(DATA_DIR / "picks_log.json", fresh, cur_sched, season, value=value, td=td, stats_teams=stats_teams)
    tracking = summarize(log, season)

    # Historique des lignes (une photo par jour, conservée d'une exécution à l'autre)
    hist_path = DATA_DIR / "line_history.json"
    try:
        line_hist = json.loads(hist_path.read_text())
    except (FileNotFoundError, ValueError):
        line_hist = {}
    today = now.date().isoformat()
    line_hist = {k: v for k, v in line_hist.items() if k in set(week_games.game_id)}
    for p in fresh:
        snaps = [x for x in line_hist.get(p["game_id"], []) if x["date"] != today]
        snaps.append({"date": today, "prob_home": p["prob_home_win"], "spread": p["vegas_spread"],
                      "books": (p["odds"] or {}).get("n_books")})
        line_hist[p["game_id"]] = snaps[-14:]
        p["line_history"] = line_hist[p["game_id"]]
    hist_path.write_text(json.dumps(line_hist, ensure_ascii=False, indent=1))

    # Archive : dernière version publiée de chaque match de la saison, figée au coup d'envoi
    arch_path = DATA_DIR / "archive.json"
    try:
        archive = json.loads(arch_path.read_text())
    except (FileNotFoundError, ValueError):
        archive = {}
    archive = {k: v for k, v in archive.items() if k.startswith(f"{season}_")}
    for p in fresh:
        archive[p["game_id"]] = compact(p)
    played_idx = cur_sched.dropna(subset=["home_score"]).set_index("game_id")
    for gid, a in archive.items():
        settle(a, played_idx, td, stats_teams)
        if a.get("status") == "upcoming" and gid not in {p["game_id"] for p in fresh}:
            a["status"] = "live"      # coup d'envoi passé, score pas encore connu
    predictions = []
    fresh_by_id = {p["game_id"]: p for p in fresh}
    for g in week_games.itertuples():
        if g.game_id in fresh_by_id:
            predictions.append(fresh_by_id[g.game_id])
            continue
        if g.game_id in archive:
            a = dict(archive[g.game_id])
        else:   # pas de version publiée (premier passage après le coup d'envoi) : recalcul avec les infos d'avant-match
            a = compact(predict_game(g, snapshots.get(week, elo_now), ctx, team_info))
            a["round"], a["unpublished"] = ROUNDS.get(g.game_type), True
            settle(a, played_idx, td, stats_teams)
        if a.get("status") != "final":
            a["status"] = "live"
        predictions.append(a)
    arch_path.write_text(json.dumps(archive, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    post = cur_sched[cur_sched.game_type.isin(ROUNDS.keys())]
    postseason = [{
        "game_id": g.game_id, "round": ROUNDS[g.game_type], "home": g.home_team, "away": g.away_team,
        "score": None if pd.isna(g.home_score) else {"home": int(g.home_score), "away": int(g.away_score)},
        "prob_home": next((p["prob_home_win"] for p in predictions if p["game_id"] == g.game_id), None),
    } for g in post.itertuples()]

    # Notes de force : modèle maison, puis ajustées sur toutes les lignes des bookmakers de la saison
    model_ratings = {t: ELO_WEIGHT * (elo_now[t] - 1505) / ELO_PER_POINT
                        + (1 - ELO_WEIGHT) * (float(ctx.epa.at[t, "net"]) * 30 if t in ctx.epa.index else 0.0)
                     for t in teams.index if t in elo_now}
    lines = cur_sched[(cur_sched.week <= week) & (cur_sched.game_type == "REG")]
    overrides = {p["game_id"]: -p["vegas_spread"] for p in fresh if p["vegas_spread"] is not None}
    sim_ratings, market_hfa = market_ratings.fit(lines, model_ratings, week, overrides)
    # Course aux playoffs : 10 000 simulations de la fin de saison
    remaining = cur_sched[cur_sched.home_score.isna() & (cur_sched.game_type == "REG")]
    sim = simulate(remaining, played[(played.season == season) & (played.game_type == "REG")], record, sim_ratings, teams,
                   fixed_probs={p["game_id"]: p["prob_home_win"] / 100 for p in predictions if p["status"] != "final"},
                   hfa_pts=market_hfa) if len(remaining) else {}

    pred_by_id = {p["game_id"]: p for p in predictions}

    def team_schedule(t):
        rows = []
        for g in cur_sched[(cur_sched.home_team == t) | (cur_sched.away_team == t)].itertuples():
            home = g.home_team == t
            opp = g.away_team if home else g.home_team
            row = {"week": int(g.week), "game_id": g.game_id, "gameday": g.gameday, "home": home, "opp": opp,
                   "opp_nick": teams.at[opp, "team_nick"] if opp in teams.index else opp,
                   "opp_logo": teams.at[opp, "team_logo_espn"] if opp in teams.index else None}
            if not pd.isna(g.home_score):
                us, them = (g.home_score, g.away_score) if home else (g.away_score, g.home_score)
                row.update(score=f"{int(us)}-{int(them)}", result="V" if us > them else "D" if us < them else "N")
            elif g.game_id in pred_by_id:
                pr = pred_by_id[g.game_id]
                row["prob"] = pr["prob_home_win"] if home else pr["prob_away_win"]
            else:
                m = sim_ratings.get(g.home_team, 0) - sim_ratings.get(g.away_team, 0) + (0 if g.location == "Neutral" else market_hfa)
                ph = win_prob(-m) * 100
                row["prob"] = round(ph if home else 100 - ph, 1)
            rows.append(row)
        return rows

    weeks_hist = sorted(snapshots)
    ranking = []
    for t in teams.index:
        if t not in elo_now:
            continue
        info = team_info(t)
        info["history"] = [round(snapshots[w].get(t, 1505), 1) for w in weeks_hist] + [info["elo"]]
        info["conf"] = teams.at[t, "team_conf"]
        info["division"] = teams.at[t, "team_division"]
        info["sim"] = sim.get(t)
        info["power"] = round(sim_ratings.get(t, 0.0), 1)
        info["schedule"] = team_schedule(t)
        ranking.append(info)
    ranking.sort(key=lambda t: t["power"], reverse=True)   # classement de force (cotes + modèle)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": season, "week": week,
        "week_label": (predictions[0].get("round") if predictions and predictions[0].get("round") else f"Semaine {week}"),
        "tracking": tracking, "postseason": postseason,
        "model": {"elo_weight": ELO_WEIGHT, "market_weight": round(MARKET_WEIGHT, 2), "hfa_elo": HFA},
        "season_record": {"games": summary["games"], "correct": summary["correct"],
                          "accuracy": round(summary["correct"] / summary["games"] * 100, 1) if summary["games"] else None},
        "bilan": {"summary": summary, "games": backtest},
        "predictions": predictions,
        "picks": picks,
        "odds_source": {"type": "consensus" if n_cons else "nflverse", "games": n_cons,
                        "books": max((p["odds"]["n_books"] for p in fresh if p["odds"]), default=0),
                        "status": odds_status.get("status"), "fetched_at": odds_status.get("fetched_at"),
                        "credits": odds_status.get("remaining")},
        "sources": {"injuries": sum(len(v) for v in inj.values()), "lineups": len(lineups),
                    "weather_errors": sum(1 for p in fresh if (p.get("weather") or {}).get("error"))},
        "archive_ids": sorted(archive),
        "top_scorers": top_scorers,
        "scorer_model": {"version": 2, "train_rows": int(scorer_model.train_rows),
                         "train_seasons": [season - 2, season],
                         "coefs": dict(zip(["constante"] + FEATURES,
                                           (round(float(c), 3) for c in scorer_model.coefs(season, week))))},
        "ranking": ranking,
    }

    (DATA_DIR / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    pd.DataFrame(ranking)[["abbr", "name", "elo"]].to_csv(DATA_DIR / "team_elos.csv", index=False)
    cur_sched.to_csv(DATA_DIR / "schedules.csv", index=False)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA_DIR / "predictions.json", WEB_DATA_DIR / "predictions.json")
    shutil.copy(DATA_DIR / "archive.json", WEB_DATA_DIR / "archive.json")
    logger.info("Saison %s, semaine %s : %d prédictions ; bilan %s/%s (modèle seul %s)",
                season, week, len(predictions), summary["correct"], summary["games"], summary["model_correct"])
    return payload
