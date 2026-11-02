"""Cotes en direct de plusieurs bookmakers via The Odds API (offre gratuite : 500 crédits/mois).

Une requête = marchés (2) × régions (3) = 6 crédits ; deux mises à jour par jour ≈ 370 crédits/mois.
Les totaux de points viennent de nflverse (le marché « totals » coûterait 3 crédits de plus par requête).
Sans clé (variable d'environnement ODDS_API_KEY), le pipeline revient aux lignes nflverse.
"""
import logging
import os
import statistics
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
REGIONS = "us,eu,fr"
MARKETS = "h2h,spreads"
FR_BOOKS = {"betclic_fr", "winamax_fr", "unibet_fr", "pmu_fr", "parionssport_fr", "netbet_fr"}
SHARP_BOOKS = {"pinnacle", "betfair_ex_eu", "betfair_ex_uk"}   # marchés les plus efficaces : poids double


def fetch_odds(api_key: str | None = None) -> list | None:
    api_key = api_key or os.getenv("ODDS_API_KEY")
    if not api_key:
        logger.info("ODDS_API_KEY absente : cotes nflverse (source unique) utilisées")
        return None
    try:
        r = requests.get(URL, params={"apiKey": api_key, "regions": REGIONS, "markets": MARKETS,
                                      "oddsFormat": "decimal"}, timeout=20)
        r.raise_for_status()
        logger.info("The Odds API : %s événements, crédits restants %s", len(r.json()),
                    r.headers.get("x-requests-remaining"))
        return r.json()
    except Exception as e:
        logger.warning("The Odds API indisponible (%s) : repli sur nflverse", e)
        return None


def _fair_pair(p_home_dec: float, p_away_dec: float) -> float:
    """Probabilité domicile sans la marge du bookmaker (méthode de Shin), à partir de cotes décimales."""
    from src.models.devig import home_prob_from_decimal
    return home_prob_from_decimal(p_home_dec, p_away_dec)


def consensus(events: list | None, name_to_abbr: dict) -> dict:
    """{(domicile, extérieur, AAAA-MM-JJ): consensus} à partir de tous les bookmakers disponibles."""
    out = {}
    for ev in events or []:
        home, away = name_to_abbr.get(ev.get("home_team")), name_to_abbr.get(ev.get("away_team"))
        if not home or not away:
            continue
        probs, weights, spreads, totals, books = [], [], [], [], []
        best_fr = {"home": None, "away": None}
        for bk in ev.get("bookmakers", []):
            mk = {m["key"]: m for m in bk.get("markets", [])}
            h2h = {o["name"]: o["price"] for o in mk.get("h2h", {}).get("outcomes", [])}
            ph, pa = h2h.get(ev["home_team"]), h2h.get(ev["away_team"])
            if ph and pa and ph > 1 and pa > 1:
                w = 2.0 if bk["key"] in SHARP_BOOKS else 1.0
                probs.append(_fair_pair(ph, pa)); weights.append(w)
                books.append({"key": bk["key"], "title": bk.get("title", bk["key"]), "home": ph, "away": pa,
                              "margin": round((1 / ph + 1 / pa - 1) * 100, 1), "fr": bk["key"] in FR_BOOKS})
                if bk["key"] in FR_BOOKS:
                    for side, price in (("home", ph), ("away", pa)):
                        if best_fr[side] is None or price > best_fr[side]["price"]:
                            best_fr[side] = {"price": price, "book": bk.get("title", bk["key"])}
            for o in mk.get("spreads", {}).get("outcomes", []):
                if o["name"] == ev["home_team"] and "point" in o:
                    spreads.append(o["point"])
            for o in mk.get("totals", {}).get("outcomes", []):
                if o["name"] == "Over" and "point" in o:
                    totals.append(o["point"])
        if not probs:
            continue
        p = sum(pr * w for pr, w in zip(probs, weights)) / sum(weights)
        day = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
        out[(home, away, day.date().isoformat())] = {
            "prob_home": p,
            "spread": statistics.median(spreads) if spreads else None,   # négatif = domicile favori
            "total": statistics.median(totals) if totals else None,
            "n_books": len(probs),
            "books": sorted(books, key=lambda b: (not b["fr"], b["title"])),
            "best_fr": best_fr,
        }
    return out


def find(cons: dict, home: str, away: str, gameday: str):
    """Retrouve un match (la date UTC peut différer d'un jour de la date américaine)."""
    if not cons or not isinstance(gameday, str):
        return None
    d = datetime.fromisoformat(gameday).date()
    for delta in (0, 1, -1):
        key = (home, away, (d.fromordinal(d.toordinal() + delta)).isoformat())
        if key in cons:
            return cons[key]
    return None
