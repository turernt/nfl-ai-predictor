import json
import logging
import shutil
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_DIR, WEB_DATA_DIR, FIRST_SEASON, HFA, ELO_PER_POINT
from src.ingestion.loader import (load_schedules, load_teams, load_player_stats, load_injury_report, load_pbp)
from src.models.elo_engine import NFLEloModel, confidence_label
from src.models.ratings import (epa_ratings, epa_margin, qb_table, qb_adjustment, rest_adjustment, win_prob)
from src.models.scorers import build_player_table, team_td_rates, likely_scorers, red_zone_opps

logger = logging.getLogger(__name__)

DEFAULT_TOTAL = 44.0     # total de points moyen en NFL, utilisé sans ligne des bookmakers
ELO_WEIGHT = 0.5         # modèle maison = 50 % Elo + 50 % EPA, puis QB et repos
# Étude 2023-2026 (899 matchs) : les cotes du marché prédisent mieux que le modèle maison et que
# tout mélange des deux (Brier 0,213 contre 0,215 pour 2/3-1/3). La probabilité affichée est donc
# celle des cotes (marge du bookmaker retirée) ; le modèle maison sert de second avis.
MARKET_WEIGHT = 1.0
TIERS = [(0.8, "Très sûr"), (0.7, "Sûr"), (0.6, "Probable"), (0.5, "Serré")]


def no_vig_prob(home_ml, away_ml) -> float | None:
    """Probabilité de victoire à domicile tirée des cotes américaines, marge retirée."""
    if pd.isna(home_ml) or pd.isna(away_ml):
        return None
    imp = lambda o: 100 / (o + 100) if o > 0 else -o / (-o + 100)
    ph, pa = imp(home_ml), imp(away_ml)
    return ph / (ph + pa)


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


def current_season(now: datetime | None = None) -> int:
    now = now or datetime.now()
    return now.year if now.month >= 8 else now.year - 1


def _fr(x: float) -> str:
    return f"{x:+.1f}".replace("-", "−").replace(".", ",")


def _commentary(fav: str, prob: float, home_is_fav: bool, neutral: bool, model_spread: float,
                vegas: float | None, qb_notes: list[str]) -> str:
    venue = "" if neutral else (", à domicile" if home_is_fav else ", à l’extérieur")
    text = f"Avantage {fav} ({prob:.0f}\u00a0%){venue}."
    if vegas is not None and (model_spread < 0) != (vegas < 0) and abs(model_spread - vegas) >= 1.5:
        text += " Notre modèle maison voit plutôt l’autre équipe gagner : signal de prudence."
    elif vegas is not None and abs(model_spread - vegas) >= 3:
        text += f" Le modèle maison ({_fr(model_spread)}) s’écarte des bookmakers ({_fr(vegas)})."
    for note in qb_notes:
        text += " " + note
    return text


class Context:
    """Tout ce qui est connu avant une semaine donnée."""

    def __init__(self, pbp, stats, sched, season, week, injuries=None):
        self.epa = epa_ratings(pbp, season, week)
        self.qbs, self.qb_base, self.qb_repl = qb_table(pbp, season, week)
        self.players = build_player_table(stats, week, red_zone_opps(pbp, season, week))
        self.rates = team_td_rates(stats, sched, season, week)
        self.injuries = injuries or {}


def predict_game(g, elo: dict, ctx: Context, team_info, with_injuries: bool) -> dict:
    neutral = g.location == "Neutral"
    elo_m = (elo.get(g.home_team, 1505) + (0 if neutral else HFA) - elo.get(g.away_team, 1505)) / ELO_PER_POINT
    epa_m = epa_margin(ctx.epa, g.home_team, g.away_team, neutral)
    qb_h = qb_adjustment(ctx.qbs, ctx.qb_base, ctx.qb_repl, g.home_team, g.home_qb_id)
    qb_a = qb_adjustment(ctx.qbs, ctx.qb_base, ctx.qb_repl, g.away_team, g.away_qb_id)
    rest_m = rest_adjustment(g.home_rest, g.away_rest)
    model_spread = -(ELO_WEIGHT * elo_m + (1 - ELO_WEIGHT) * epa_m + qb_h - qb_a + rest_m)
    vegas = None if pd.isna(g.spread_line) else -float(g.spread_line)
    spread = MARKET_WEIGHT * vegas + (1 - MARKET_WEIGHT) * model_spread if vegas is not None else model_spread
    p_ml = no_vig_prob(g.home_moneyline, g.away_moneyline)
    p_home = (p_ml if p_ml is not None else win_prob(spread)) * 100
    source = "cotes" if p_ml is not None else ("spread" if vegas is not None else "modèle")

    total = DEFAULT_TOTAL if pd.isna(g.total_line) else float(g.total_line)
    home_pts, away_pts = total / 2 - spread / 2, total / 2 + spread / 2
    inj = ctx.injuries if with_injuries else {}
    scorers = (likely_scorers(ctx.players, ctx.rates, g.away_team, away_pts, inj)
               + likely_scorers(ctx.players, ctx.rates, g.home_team, home_pts, inj))
    home, away = team_info(g.home_team), team_info(g.away_team)
    home_fav = p_home >= 50
    qb_notes = [f"QB annoncé chez les {t['nick']} ({name}) : {_fr(v)} pt par rapport à leur niveau habituel."
                for t, name, v in ((home, g.home_qb_name, qb_h), (away, g.away_qb_name, qb_a)) if abs(v) >= 2]
    return {
        "game_id": g.game_id, "week": int(g.week), "game_type": g.game_type,
        "gameday": g.gameday, "gametime": g.gametime, "neutral_site": neutral,
        "home": home, "away": away,
        "prob_home_win": round(p_home, 1), "prob_away_win": round(100 - p_home, 1),
        "predicted_spread": round(spread, 1), "model_spread": round(model_spread, 1),
        "model_prob_home": round(win_prob(model_spread) * 100, 1),
        "vegas_spread": vegas, "vegas_total": None if pd.isna(g.total_line) else float(g.total_line),
        "projected_score": {"home": round(home_pts), "away": round(away_pts)},
        "confidence_score": confidence_label(p_home),
        "tier": tier_of(max(p_home, 100 - p_home) / 100), "prob_source": source,
        "factors": {
            "elo": round(elo_m, 1), "epa": round(epa_m, 1),
            "qb": {"home": round(qb_h, 1), "away": round(qb_a, 1),
                   "home_name": g.home_qb_name if isinstance(g.home_qb_name, str) else None,
                   "away_name": g.away_qb_name if isinstance(g.away_qb_name, str) else None},
            "rest": {"pts": round(rest_m, 1),
                     "home_days": None if pd.isna(g.home_rest) else int(g.home_rest),
                     "away_days": None if pd.isna(g.away_rest) else int(g.away_rest)},
            "market_weight": 1.0 if vegas is not None else 0.0,
        },
        "scorers": sorted(scorers, key=lambda x: x["prob"], reverse=True),
        "commentary": _commentary((home if home_fav else away)["nick"], max(p_home, 100 - p_home),
                                  home_fav, neutral, model_spread, vegas, qb_notes),
    }


def run_pipeline() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    season = current_season()
    sched = load_schedules(list(range(FIRST_SEASON, season + 1)))
    teams = load_teams().set_index("team_abbr")
    pbp = load_pbp([season - 1, season])
    stats = load_player_stats(season)

    cur_sched = sched[sched.season == season]
    upcoming = cur_sched[cur_sched.home_score.isna()]
    week = int(upcoming.week.min()) if not upcoming.empty else int(cur_sched.week.max()) + 1

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
                "logo": row["team_logo_espn"] if row is not None else None,
                "elo": round(elo_now.get(abbr, 1505), 1),
                "record": f"{w}-{l}" + (f"-{d}" if d else ""),
                "off_rank": int(epa.at[abbr, "off_rank"]) if abbr in epa.index else None,
                "def_rank": int(epa.at[abbr, "def_rank"]) if abbr in epa.index else None,
            }
        return team_info

    # --- Bilan : chaque semaine passée, prédite avec les seules infos disponibles avant
    backtest = []
    for wk in sorted(w for w in cur_sched.week.unique() if w < week):
        ctx = Context(pbp, stats, sched, season, wk)
        info = make_team_info(ctx.epa)
        actual_td = stats[(stats.week == wk)].assign(
            t=lambda d: d["rushing_tds"].fillna(0) + d["receiving_tds"].fillna(0)).set_index("player_id")["t"]
        for g in played[(played.season == season) & (played.week == wk)].itertuples():
            pr = predict_game(g, snapshots[wk], ctx, info, with_injuries=False)
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
    summary = {
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

    # --- Semaine à venir
    ctx = Context(pbp, stats, sched, season, week, load_injury_report(season, week))
    team_info = make_team_info(ctx.epa)
    predictions = [predict_game(g, elo_now, ctx, team_info, with_injuries=True)
                   for g in upcoming[upcoming.week == week].itertuples()]

    top_scorers = sorted((dict(sc, game_id=pr["game_id"],
                               opponent=pr["home"]["abbr"] if sc["team"] == pr["away"]["abbr"] else pr["away"]["abbr"])
                          for pr in predictions for sc in pr["scorers"]),
                         key=lambda x: x["prob"], reverse=True)[:12]

    reliability = market_reliability(sched)
    rel = {r["tier"]: r for r in reliability}
    sc_rel = summary["scorer_tiers"]
    def sc_tier(p):
        return next((t for t in sc_rel if p >= t["min"]), sc_rel[-1])
    picks_win = []
    for pr in predictions:
        home_fav = pr["prob_home_win"] >= 50
        p = max(pr["prob_home_win"], pr["prob_away_win"])
        fav, opp = (pr["home"], pr["away"]) if home_fav else (pr["away"], pr["home"])
        model_fav_home = pr["model_spread"] < 0
        picks_win.append({
            "game_id": pr["game_id"], "gameday": pr["gameday"], "gametime": pr["gametime"],
            "team": fav, "opponent": opp, "home": home_fav, "prob": p, "tier": pr["tier"],
            "fair_odds": round(100 / p, 2), "hist": rel.get(pr["tier"]),
            "model_agrees": model_fav_home == home_fav,
            "model_prob": pr["model_prob_home"] if home_fav else round(100 - pr["model_prob_home"], 1),
        })
    picks_win.sort(key=lambda x: x["prob"], reverse=True)
    picks_scorers = [dict(sc, fair_odds=round(100 / sc["prob"], 2), hist=sc_tier(sc["prob"]))
                     for sc in top_scorers if sc["prob"] >= 40]
    picks = {
        "safest": [x for x in picks_win if x["prob"] >= 70],
        "coin_flips": [x for x in picks_win if x["prob"] < 57],
        "scorers": picks_scorers,
        "reliability": reliability,
    }

    weeks_hist = sorted(snapshots)
    ranking = []
    for t in teams.index:
        if t not in elo_now:
            continue
        info = team_info(t)
        info["history"] = [round(snapshots[w].get(t, 1505), 1) for w in weeks_hist] + [info["elo"]]
        ranking.append(info)
    ranking.sort(key=lambda t: t["elo"], reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": season, "week": week,
        "model": {"elo_weight": ELO_WEIGHT, "market_weight": round(MARKET_WEIGHT, 2), "hfa_elo": HFA},
        "season_record": {"games": summary["games"], "correct": summary["correct"],
                          "accuracy": round(summary["correct"] / summary["games"] * 100, 1) if summary["games"] else None},
        "bilan": {"summary": summary, "games": backtest},
        "predictions": predictions,
        "picks": picks,
        "top_scorers": top_scorers,
        "ranking": ranking,
    }

    (DATA_DIR / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    pd.DataFrame(ranking)[["abbr", "name", "elo"]].to_csv(DATA_DIR / "team_elos.csv", index=False)
    cur_sched.to_csv(DATA_DIR / "schedules.csv", index=False)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA_DIR / "predictions.json", WEB_DATA_DIR / "predictions.json")
    logger.info("Saison %s, semaine %s : %d prédictions ; bilan %s/%s (modèle seul %s)",
                season, week, len(predictions), summary["correct"], summary["games"], summary["model_correct"])
    return payload
