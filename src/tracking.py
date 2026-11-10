"""Suivi des pronostics réellement publiés (jamais recalculés après coup).

Pour chaque match, tant qu'il n'a pas commencé, le journal garde :
- le pronostic de vainqueur (première probabilité publiée et dernière avant le coup d'envoi) ;
- les buteurs affichés juste avant le coup d'envoi ;
- les cotes françaises signalées au-dessus du juste prix (première apparition : cote, bookmaker, espérance).
Après le match : résultat, buteurs ayant marqué, et valeur de clôture des cotes signalées, mesurée contre la ligne de
clôture nflverse (marge retirée). Une cote signalée qui bat régulièrement la clôture est le seul signal d'un vrai avantage.
"""
import json
from datetime import datetime, timezone

import pandas as pd

from src.models.devig import shin


def _ml_prob(home_ml, away_ml):
    if pd.isna(home_ml) or pd.isna(away_ml):
        return None
    imp = lambda o: 100 / (o + 100) if o > 0 else -o / (-o + 100)
    return shin([imp(home_ml), imp(away_ml)])[0]


def update_log(path, predictions: list, sched: pd.DataFrame, season: int, value: list | None = None,
               td: dict | None = None, stats_teams: set | None = None) -> dict:
    """predictions : matchs pas encore commencés. td : {(semaine, joueur): TD}. stats_teams : {(semaine, équipe)}."""
    try:
        log = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        log = {"since": datetime.now(timezone.utc).date().isoformat(), "games": {}}
    games = log["games"]
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    for p in predictions:
        e = games.get(p["game_id"])
        best = (p.get("odds") or {}).get("best_fr") or {}
        if e is None:
            pick_home = p["prob_home_win"] >= 50
            e = games[p["game_id"]] = {
                "season": season, "week": p["week"], "home": p["home"]["abbr"], "away": p["away"]["abbr"],
                "published_at": now, "pick": p["home"]["abbr"] if pick_home else p["away"]["abbr"],
                "pick_home": pick_home, "open_prob": max(p["prob_home_win"], p["prob_away_win"]),
                "open_fr": (best.get("home") if pick_home else best.get("away")),
            }
        e["close_prob"] = p["prob_home_win"] if e["pick_home"] else p["prob_away_win"]
        e["closed_at"] = now
        e["scorers"] = [{"id": s.get("player_id"), "name": s["name"], "team": s["team"], "prob": s["prob"]}
                        for s in p.get("scorers", [])]
    for v in value or []:
        e = games.get(v["game_id"])
        if e is None:
            continue
        flagged = e.setdefault("value", [])
        if not any(x["team"] == v["team"]["abbr"] and x["book"] == v["book"] for x in flagged):
            flagged.append({"team": v["team"]["abbr"], "home": v["team"]["abbr"] == e["home"], "book": v["book"],
                            "price": v["price"], "prob": v["prob"], "ev": v["ev"], "at": now})

    played = sched.dropna(subset=["home_score"]).set_index("game_id")
    td, stats_teams = td or {}, stats_teams or set()
    for gid, e in games.items():
        if gid not in played.index:
            continue
        g = played.loc[gid]
        if "result" not in e:
            if g.home_score == g.away_score:
                e["result"] = "N"
            else:
                e["result"] = "V" if (g.home_score > g.away_score) == e["pick_home"] else "D"
            e["score"] = f"{int(g.away_score)}-{int(g.home_score)}"
        if "close_mkt" not in e:
            p = _ml_prob(g.home_moneyline, g.away_moneyline)
            if p is not None:
                e["close_mkt"] = round((p if e["pick_home"] else 1 - p) * 100, 1)
                for x in e.get("value", []):
                    side = p if x["home"] else 1 - p
                    x["clv"] = round((x["price"] * side - 1) * 100, 1)
        for x in e.get("value", []):
            if "won" not in x and g.home_score != g.away_score:
                x["won"] = (g.home_score > g.away_score) == x["home"]
        sc = e.get("scorers") or []
        if sc and "scored" not in sc[0] and (int(g.week), e["home"]) in stats_teams and (int(g.week), e["away"]) in stats_teams:
            for s in sc:
                s["scored"] = td.get((int(g.week), s["id"]), 0) > 0
    path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    return log


SCORER_TIERS = [(50, 101, "50 % et plus"), (40, 50, "40 à 50 %"), (30, 40, "30 à 40 %"), (0, 30, "moins de 30 %")]


def summarize(log: dict, season: int) -> dict:
    g = [e for e in log["games"].values() if e["season"] == season]
    done = [e for e in g if e.get("result") in ("V", "D")]
    safe = [e for e in done if e["close_prob"] >= 70]
    brier = [(e["close_prob"] / 100 - (e["result"] == "V")) ** 2 for e in done]
    sc = [s for e in g for s in e.get("scorers", []) if "scored" in s]
    top = [max(e["scorers"], key=lambda s: s["prob"]) for e in g if e.get("scorers") and "scored" in e["scorers"][0]]
    val = [x for e in g for x in e.get("value", [])]
    vdone = [x for x in val if "won" in x]
    vclv = [x["clv"] for x in val if "clv" in x]
    units = sum((x["price"] - 1) if x["won"] else -1 for x in vdone)
    return {
        "since": log.get("since"), "published": len(g), "settled": len(done),
        "correct": sum(e["result"] == "V" for e in done),
        "brier": round(sum(brier) / len(brier), 3) if brier else None,
        "safe": {"n": len(safe), "correct": sum(e["result"] == "V" for e in safe)},
        "scorers": {"n": len(sc), "hits": sum(s["scored"] for s in sc),
                    "expected": round(sum(s["prob"] for s in sc) / 100, 1),
                    "top_n": len(top), "top_hits": sum(s["scored"] for s in top),
                    "tiers": [{"label": lab, "n": len(t := [s for s in sc if lo <= s["prob"] < hi]),
                               "predicted": round(sum(s["prob"] for s in t) / len(t), 1) if t else None,
                               "actual": round(sum(s["scored"] for s in t) / len(t) * 100, 1) if t else None}
                              for lo, hi, lab in SCORER_TIERS]},
        "value": {"n": len(val), "settled": len(vdone), "won": sum(x["won"] for x in vdone),
                  "units": round(units, 2), "roi": round(units / len(vdone) * 100, 1) if vdone else None,
                  "clv_n": len(vclv), "clv_avg": round(sum(vclv) / len(vclv), 1) if vclv else None,
                  "clv_pos": sum(c > 0 for c in vclv)},
        "recent": sorted(done, key=lambda e: e.get("closed_at", ""), reverse=True)[:16],
    }
