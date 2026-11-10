"""Contrôles avant publication : le workflow s'arrête (sans rien publier) si les données sont incohérentes.

Les erreurs bloquent la publication ; les avertissements sont seulement affichés dans le journal du workflow.
"""
import json
import sys
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_DIR

STATUSES = {"upcoming", "live", "final"}


def _check_pred(p: dict, errors: list) -> None:
    gid = p.get("game_id", "?")
    if not (0 < p["prob_home_win"] < 100) or abs(p["prob_home_win"] + p["prob_away_win"] - 100) > 0.2:
        errors.append(f"probabilités incohérentes : {gid}")
    if p.get("status") not in STATUSES:
        errors.append(f"statut inconnu : {gid} ({p.get('status')})")
    if p.get("status") == "final" and not p.get("score"):
        errors.append(f"match terminé sans score : {gid}")
    for s in p.get("scorers", []):
        if not (0 <= s["prob"] < 100):
            errors.append(f"buteur incohérent : {s['name']}")
        if not isinstance(s.get("form", []), list):
            errors.append(f"journal des matchs incohérent : {s['name']}")


def main() -> int:
    d = json.loads((DATA_DIR / "predictions.json").read_text())
    errors, warnings = [], []
    for key in ("season", "week", "predictions", "ranking", "bilan", "picks", "generated_at"):
        if key not in d:
            errors.append(f"clé manquante : {key}")
    if len(d.get("ranking", [])) != 32:
        errors.append(f"classement : {len(d.get('ranking', []))} équipes au lieu de 32")

    # Tous les matchs de la semaine doivent être présents, ni plus ni moins
    sched = pd.read_csv(DATA_DIR / "schedules.csv")
    expected = set(sched.loc[sched.week == d.get("week"), "game_id"])
    got = [p["game_id"] for p in d.get("predictions", [])]
    if set(got) != expected or len(got) != len(set(got)):
        errors.append(f"semaine {d.get('week')} : {len(got)} matchs publiés pour {len(expected)} au calendrier")

    for p in d.get("predictions", []):
        _check_pred(p, errors)
        for side in ("home", "away"):
            starters = [x for x in (p.get("lineup") or {}).get(side, []) if x.get("available")]
            if len({x["player_id"] for x in starters}) != len(starters):
                errors.append(f"composition en double : {p['game_id']} ({side})")
    try:
        archive = json.loads((DATA_DIR / "archive.json").read_text())
    except FileNotFoundError:
        archive = {}
    for p in archive.values():
        _check_pred(p, errors)

    coefs = (d.get("scorer_model") or {}).get("coefs", {})
    if coefs and not all(isinstance(v, (int, float)) and abs(v) < 20 for v in coefs.values()):
        errors.append("modèle de buteurs : coefficients aberrants")
    sims = [t["sim"] for t in d.get("ranking", []) if t.get("sim")]
    if sims and abs(sum(s["sb"] for s in sims) - 100) > 1:
        errors.append("simulation : la somme des chances de Super Bowl n'est pas 100 %")

    # Avertissements : sources manquantes ou anciennes
    src = d.get("odds_source") or {}
    if src.get("fetched_at"):
        age = datetime.now(timezone.utc) - datetime.fromisoformat(src["fetched_at"])
        if age.total_seconds() > 36 * 3600:
            warnings.append(f"cotes en cache depuis {int(age.total_seconds() // 3600)} h")
    if src.get("credits") is not None and int(float(src["credits"])) < 50:
        warnings.append(f"The Odds API : {src['credits']} crédits restants")
    upcoming = [p for p in d.get("predictions", []) if p.get("status") == "upcoming"]
    if upcoming and not (d.get("sources") or {}).get("injuries"):
        warnings.append("rapport de blessures vide pour la semaine (normal avant le mercredi)")
    if (d.get("sources") or {}).get("weather_errors"):
        warnings.append(f"météo indisponible pour {d['sources']['weather_errors']} match(s)")

    for w in warnings:
        print("AVERTISSEMENT", w)
    for e in errors:
        print("ERREUR", e)
    print("Données valides" if not errors else f"{len(errors)} erreur(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
