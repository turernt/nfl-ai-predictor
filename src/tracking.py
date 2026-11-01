"""Suivi des pronostics réellement publiés (pas recalculés après coup) et de la valeur de clôture (CLV).

À chaque exécution, chaque match à venir est enregistré : la première probabilité publiée est figée,
la dernière avant le coup d'envoi sert de « clôture ». Une fois le match joué, le résultat est ajouté.
CLV = probabilité de clôture − probabilité publiée, du côté du pronostic : positif = le marché a ensuite
donné raison au pronostic.
"""
import json
from datetime import datetime, timezone

import pandas as pd


def update_log(path, predictions: list, sched: pd.DataFrame, season: int) -> dict:
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
    played = sched.dropna(subset=["home_score"]).set_index("game_id")
    for gid, e in games.items():
        if "result" not in e and gid in played.index:
            g = played.loc[gid]
            if g.home_score == g.away_score:
                e["result"] = "N"
            else:
                e["result"] = "V" if (g.home_score > g.away_score) == e["pick_home"] else "D"
            e["score"] = f"{int(g.away_score)}-{int(g.home_score)}"
    path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    return log


def summarize(log: dict, season: int) -> dict:
    g = [e for e in log["games"].values() if e["season"] == season]
    done = [e for e in g if e.get("result") in ("V", "D")]
    safe = [e for e in done if e["open_prob"] >= 70]
    clv = [e["close_prob"] - e["open_prob"] for e in g if "close_prob" in e]
    fr = [e for e in done if e.get("open_fr")]
    units = sum((e["open_fr"]["price"] - 1) if e["result"] == "V" else -1 for e in fr)
    return {
        "since": log.get("since"), "published": len(g), "settled": len(done),
        "correct": sum(e["result"] == "V" for e in done),
        "safe": {"n": len(safe), "correct": sum(e["result"] == "V" for e in safe)},
        "clv_avg": round(sum(clv) / len(clv), 2) if clv else None,
        "clv_pos": sum(c > 0 for c in clv), "clv_n": len(clv),
        "fr_bets": len(fr), "fr_units": round(units, 2),
        "recent": sorted(done, key=lambda e: e.get("closed_at", ""), reverse=True)[:16],
    }
