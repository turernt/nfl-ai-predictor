"""Vérifie la simulation des playoffs sur les saisons passées (format à 7 qualifiés par conférence, depuis 2020).

À plusieurs moments de chaque saison (après les semaines 4, 8, 12 et 16), on simule la fin de saison avec les seules
informations alors disponibles (lignes des bookmakers jusqu'à cette semaine, bilans réels), puis on compare les chances
annoncées aux équipes réellement qualifiées. Résultat écrit dans data/playoff_backtest.json, affiché sur /saison.

Lancement (une fois par an suffit) : python -m studies.playoff_backtest
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import DATA_DIR                                     # noqa: E402
from src.ingestion.loader import load_schedules, load_teams         # noqa: E402
from src.models import market_ratings                               # noqa: E402
from src.models.season_sim import simulate                          # noqa: E402

SEASONS = range(2020, 2026)
WEEKS = (4, 8, 12, 16)
SIMS = 2000
BUCKETS = [(0, 10), (10, 30), (30, 50), (50, 70), (70, 90), (90, 101)]


def season_end_ratings(sched, season, teams):
    reg = sched[(sched.season == season) & (sched.game_type == "REG")]
    r, _ = market_ratings.fit(reg, {t: 0.0 for t in teams}, int(reg.week.max()))
    return r


def main():
    sched = load_schedules(list(range(min(SEASONS) - 1, max(SEASONS) + 1)))
    teams = load_teams().set_index("team_abbr")
    abbrs = list(teams.index)
    rows = []
    for season in SEASONS:
        s = sched[sched.season == season]
        post = s[s.game_type.isin(["WC", "DIV"])]
        qualified = set(post.home_team) | set(post.away_team)
        prior = {t: 0.6 * v for t, v in season_end_ratings(sched, season - 1, abbrs).items()}
        reg = s[s.game_type == "REG"]
        for wk in WEEKS:
            played = reg[reg.week <= wk]
            remaining = reg[reg.week > wk].assign(home_score=np.nan, away_score=np.nan)
            record = {}
            for g in played.itertuples():
                for t, us, them in ((g.home_team, g.home_score, g.away_score), (g.away_team, g.away_score, g.home_score)):
                    w, l, d = record.get(t, (0, 0, 0))
                    record[t] = (w + (us > them), l + (us < them), d + (us == them))
            ratings, hfa = market_ratings.fit(played, prior, wk)
            sim = simulate(remaining, played, record, ratings, teams, sims=SIMS, hfa_pts=hfa)
            for t, v in sim.items():
                rows.append({"season": season, "week": wk, "team": t, "p": v["playoff"], "made": t in qualified})
            print(season, wk, "ok", flush=True)
    p = np.array([r["p"] for r in rows]) / 100
    y = np.array([r["made"] for r in rows], float)
    out = {"seasons": [min(SEASONS), max(SEASONS)], "weeks": list(WEEKS), "n": len(rows),
           "brier": round(float(((p - y) ** 2).mean()), 3),
           "brier_base": round(float(((y.mean() - y) ** 2).mean()), 3),
           "buckets": []}
    for lo, hi in BUCKETS:
        m = (p * 100 >= lo) & (p * 100 < hi)
        if m.any():
            out["buckets"].append({"label": f"{lo} à {min(hi, 100)} %", "n": int(m.sum()),
                                   "predicted": round(float(p[m].mean() * 100), 1),
                                   "actual": round(float(y[m].mean() * 100), 1)})
    out["by_week"] = [{"week": wk, "brier": round(float(((p[w] - y[w]) ** 2).mean()), 3)}
                      for wk in WEEKS for w in [np.array([r["week"] == wk for r in rows])]]
    (DATA_DIR / "playoff_backtest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
