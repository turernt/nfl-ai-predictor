"""Cotes de plusieurs bookmakers via The Odds API (offre gratuite : 500 crédits/mois).

Une requête = marchés (2) × régions (3) = 6 crédits. Les réponses sont gardées en cache (data/odds_cache.json) et l'API
n'est rappelée que si nécessaire : une fois par jour, et toutes les 3 heures quand un match commence dans les 6 heures
(environ 11 appels par semaine, soit près de 290 crédits par mois). Les lancements manuels ne coûtent donc rien.
Les matchs déjà commencés sont ignorés : l'API renvoie aussi les cotes en direct, qui ne sont pas des cotes d'avant-match.
Sans clé (variable d'environnement ODDS_API_KEY), le pipeline revient aux lignes nflverse.
"""
import json
import logging
import os
import statistics
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
REGIONS = "us,eu,fr"
MARKETS = "h2h,spreads"
COST = 6                     # crédits par appel
FR_BOOKS = {"betclic_fr", "winamax_fr", "unibet_fr", "pmu_fr", "parionssport_fr", "netbet_fr"}
REF_MAX_MARGIN = 6.0         # bookmakers retenus pour le juste prix : marge de 6 % au plus
DAILY_REFRESH = timedelta(hours=24)
PREGAME_WINDOW = timedelta(hours=6)
PREGAME_REFRESH = timedelta(hours=3)
MIN_CREDITS = 25             # en dessous, seulement les rafraîchissements d'avant-match


def _now(now=None):
    return now or datetime.now(timezone.utc)


def _load(path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError, AttributeError):
        return {}


def _need_refresh(cache: dict, kickoffs: list, now: datetime) -> tuple[bool, str]:
    if not cache.get("events"):
        return True, "cache vide"
    age = now - datetime.fromisoformat(cache["fetched_at"])
    soon = any(now <= k <= now + PREGAME_WINDOW for k in kickoffs if k)
    remaining = cache.get("remaining")
    low = remaining is not None and int(remaining) < MIN_CREDITS
    if soon and age >= PREGAME_REFRESH:
        return True, "match dans les 6 heures"
    if age >= DAILY_REFRESH and not low:
        return True, "rafraîchissement quotidien"
    return False, f"cache de {int(age.total_seconds() // 3600)} h conservé"


def get_odds(cache_path, kickoffs: list, api_key: str | None = None, now: datetime | None = None) -> tuple[list | None, dict]:
    """Événements (cache ou API) et état de la source : {status, fetched_at, remaining}."""
    api_key = api_key or os.getenv("ODDS_API_KEY")
    now = _now(now)
    cache = _load(cache_path)
    if not api_key:
        logger.info("ODDS_API_KEY absente : cotes nflverse (source unique) utilisées")
        return None, {"status": "nflverse"}
    refresh, why = _need_refresh(cache, kickoffs, now)
    if refresh:
        try:
            r = requests.get(URL, params={"apiKey": api_key, "regions": REGIONS, "markets": MARKETS,
                                          "oddsFormat": "decimal"}, timeout=20)
            r.raise_for_status()
            cache = {"fetched_at": now.isoformat(timespec="seconds"), "remaining": r.headers.get("x-requests-remaining"),
                     "events": r.json()}
            cache_path.write_text(json.dumps(cache, ensure_ascii=False))
            logger.info("The Odds API (%s) : %s événements, crédits restants %s", why, len(cache["events"]), cache["remaining"])
            return cache["events"], {"status": "live", "fetched_at": cache["fetched_at"], "remaining": cache["remaining"]}
        except Exception as e:
            logger.warning("The Odds API indisponible (%s) : cotes en cache utilisées", e)
    else:
        logger.info("The Odds API non appelée : %s", why)
    if not cache.get("events"):
        return None, {"status": "nflverse"}
    return cache["events"], {"status": "cache", "fetched_at": cache.get("fetched_at"), "remaining": cache.get("remaining")}


def _fair_pair(p_home_dec: float, p_away_dec: float) -> float:
    """Probabilité domicile sans la marge du bookmaker (méthode de Shin), à partir de cotes décimales."""
    from src.models.devig import home_prob_from_decimal
    return home_prob_from_decimal(p_home_dec, p_away_dec)


def consensus(events: list | None, name_to_abbr: dict, now: datetime | None = None) -> dict:
    """{(domicile, extérieur, AAAA-MM-JJ): consensus} pour les matchs pas encore commencés.

    Juste prix = médiane des probabilités (marge retirée) des bookmakers dont la marge ne dépasse pas 6 % :
    les bookmakers à forte marge (souvent les français) ne déforment pas la référence, et la médiane résiste
    aux cotes isolées."""
    now = _now(now)
    out = {}
    for ev in events or []:
        home, away = name_to_abbr.get(ev.get("home_team")), name_to_abbr.get(ev.get("away_team"))
        if not home or not away:
            continue
        start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if start <= now:          # match commencé : cotes en direct, à ne pas utiliser
            continue
        probs, ref, spreads, books = [], [], [], []
        best_fr = {"home": None, "away": None}
        for bk in ev.get("bookmakers", []):
            mk = {m["key"]: m for m in bk.get("markets", [])}
            h2h = {o["name"]: o["price"] for o in mk.get("h2h", {}).get("outcomes", [])}
            ph, pa = h2h.get(ev["home_team"]), h2h.get(ev["away_team"])
            if ph and pa and ph > 1 and pa > 1:
                p = _fair_pair(ph, pa)
                margin = round((1 / ph + 1 / pa - 1) * 100, 1)
                probs.append(p)
                if margin <= REF_MAX_MARGIN:
                    ref.append(p)
                books.append({"key": bk["key"], "title": bk.get("title", bk["key"]), "home": ph, "away": pa,
                              "margin": margin, "fr": bk["key"] in FR_BOOKS})
                if bk["key"] in FR_BOOKS:
                    for side, price in (("home", ph), ("away", pa)):
                        if best_fr[side] is None or price > best_fr[side]["price"]:
                            best_fr[side] = {"price": price, "book": bk.get("title", bk["key"])}
            for o in mk.get("spreads", {}).get("outcomes", []):
                if o["name"] == ev["home_team"] and "point" in o:
                    spreads.append(o["point"])
        if not probs:
            continue
        out[(home, away, start.date().isoformat())] = {
            "prob_home": statistics.median(ref or probs),
            "spread": statistics.median(spreads) if spreads else None,   # négatif = domicile favori
            "total": None,                                                # totaux : lignes nflverse
            "n_books": len(probs), "n_ref": len(ref),
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
