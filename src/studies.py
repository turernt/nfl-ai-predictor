"""Études recalculées à chaque passage, pour que les chiffres affichés sur le site ne soient jamais écrits en dur.

- Écart-type du score autour du spread (conversion écart de points → probabilité), lignes de clôture depuis 2016.
- Retrait de la marge : méthode de Shin contre méthode proportionnelle, calibration des outsiders.
- Vent et total de points : vent observé (nflverse, depuis 2012) et vent prévu (archive gratuite des prévisions
  Open-Meteo, depuis 2022, mise en cache dans data/wind_forecasts.json : seuls les nouveaux matchs sont demandés).
- Simulation des playoffs : résultat du test rétrospectif (studies/playoff_backtest.py, data/playoff_backtest.json).
"""
import json
import logging
import math
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from src.config import DATA_DIR
from src.ingestion.weather import STADIUMS, WINDY_KMH, kickoff_utc
from src.models.devig import shin

logger = logging.getLogger(__name__)
HIST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FORECAST_FROM = 2022
FETCH_BUDGET = 75        # secondes par passage : le cache se remplit sur plusieurs passages
MPH_TO_KMH = 1.609


def _imp(o):
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def _ci(p, n):
    """Intervalle de confiance à 95 % d'une proportion, en points de pourcentage."""
    return round(1.96 * math.sqrt(p * (1 - p) / n) * 100, 1) if n else None


def spread_sd(sched: pd.DataFrame) -> dict:
    h = sched[sched.season >= 2016].dropna(subset=["home_score", "spread_line"])
    h = h[h.home_score != h.away_score]
    y = (h.home_score > h.away_score).to_numpy(float)
    s = h.spread_line.to_numpy(float)
    best = None
    for sd in np.arange(10.0, 15.01, 0.25):
        p = 0.5 * (1 + np.vectorize(math.erf)(s / sd / math.sqrt(2)))
        p = p.clip(1e-6, 1 - 1e-6)
        ll = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
        if best is None or ll < best[1]:
            best = (round(float(sd), 2), ll)
    return {"best_sd": best[0], "games": int(len(h))}


def devig(sched: pd.DataFrame) -> dict:
    d = sched[sched.season >= 2012].dropna(subset=["home_score", "home_moneyline", "away_moneyline"])
    d = d[d.home_score != d.away_score]
    ih, ia = d.home_moneyline.map(_imp).to_numpy(), d.away_moneyline.map(_imp).to_numpy()
    y = (d.home_score > d.away_score).to_numpy()
    out = {"games": int(len(d))}
    for name, p in (("shin", np.array([shin([a, b])[0] for a, b in zip(ih, ia)])), ("prop", ih / (ih + ia))):
        dog = np.minimum(p, 1 - p)
        dog_won = np.where(p < 0.5, y, ~y)
        m = dog < 0.25
        out[name] = {"brier": round(float(((p - y) ** 2).mean()), 4),
                     "dogs": int(m.sum()), "dog_pred": round(float(dog[m].mean() * 100), 1),
                     "dog_actual": round(float(dog_won[m].mean() * 100), 1)}
    return out


def _under(df: pd.DataFrame) -> dict:
    df = df[df.total != df.total_line]
    n = len(df)
    u = float((df.total < df.total_line).mean()) if n else 0.0
    return {"n": n, "under": round(u * 100, 1) if n else None, "ci": _ci(u, n)}


def wind_observed(sched: pd.DataFrame) -> dict:
    g = sched[sched.season >= 2012].dropna(subset=["total", "total_line"])
    g = g.assign(total=g.home_score + g.away_score) if "total" not in g else g
    windy = g[g.wind * MPH_TO_KMH >= WINDY_KMH]
    return {"all": _under(windy), "base": _under(g),
            "periods": [dict(_under(windy[(windy.season >= a) & (windy.season <= b)]), label=f"{a}-{b}" if b < 2100 else f"depuis {a}")
                        for a, b in ((2012, 2017), (2018, 2022), (2023, 2100))]}



def _fetch_forecasts(sched: pd.DataFrame) -> dict:
    """Vent prévu au coup d'envoi pour chaque match joué en plein air depuis 2022 (cache incrémental)."""
    path = DATA_DIR / "wind_forecasts.json"
    try:
        cache = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        cache = {}
    g = sched[(sched.season >= FORECAST_FROM) & sched.home_score.notna() & (sched.location != "Neutral")]
    g = g[g.home_team.map(lambda t: STADIUMS.get(t, (0, 0, "dome"))[2] == "open")]
    missing = g[~g.game_id.isin(cache)]
    deadline = time.monotonic() + FETCH_BUDGET
    # une requête par stade et par saison (quelques mois de données horaires), dans la limite du budget de temps
    for (team, _season), grp in missing.groupby(["home_team", "season"]):
        if time.monotonic() > deadline:
            logger.info("Archive des prévisions : budget de temps atteint, la suite au prochain passage")
            break
        lat, lon, _ = STADIUMS[team]
        try:
            r = requests.get(HIST_URL, params={"latitude": lat, "longitude": lon, "timezone": "UTC",
                                               "hourly": "wind_speed_10m", "start_date": grp.gameday.min(),
                                               "end_date": grp.gameday.max()}, timeout=20)
            r.raise_for_status()
            h = r.json()["hourly"]
            idx = {t: i for i, t in enumerate(h["time"])}
            for x in grp.itertuples():
                ko = kickoff_utc(x.gameday, x.gametime)
                i = idx.get(ko.replace(minute=0, second=0).strftime("%Y-%m-%dT%H:00")) if ko else None
                v = h["wind_speed_10m"][i] if i is not None else None
                if v is not None:
                    cache[x.game_id] = round(float(v), 1)
        except Exception as e:
            logger.warning("Archive des prévisions Open-Meteo indisponible pour %s : %s", team, e)
    path.write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True))
    return cache


def wind_forecast(sched: pd.DataFrame) -> dict:
    cache = _fetch_forecasts(sched)
    g = sched[sched.game_id.isin(cache)].dropna(subset=["home_score", "total_line"])
    g = g.assign(total=g.home_score + g.away_score, fwind=g.game_id.map(cache))
    windy = g[g.fwind >= WINDY_KMH]
    res = {"since": FORECAST_FROM, "games": int(len(g)), "windy": _under(windy), "calm": _under(g[g.fwind < WINDY_KMH])}
    w = res["windy"]
    # Signal publié seulement si la borne basse de l'intervalle dépasse 52,4 % (seuil de rentabilité à cote 1,91)
    res["validated"] = bool(w["n"] >= 100 and w["under"] - w["ci"] > 52.4)
    return res


def compute(sched: pd.DataFrame) -> dict:
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for name, fn in (("spread_sd", spread_sd), ("devig", devig), ("wind_observed", wind_observed),
                     ("wind_forecast", wind_forecast)):
        try:
            out[name] = fn(sched)
        except Exception as e:      # une étude en échec ne doit jamais bloquer la publication
            logger.warning("Étude %s impossible : %s", name, e)
    try:
        out["playoff_backtest"] = json.loads((DATA_DIR / "playoff_backtest.json").read_text())
    except (FileNotFoundError, ValueError):
        pass
    return out
