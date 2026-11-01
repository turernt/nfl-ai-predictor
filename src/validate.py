"""Contrôles avant publication : le workflow s'arrête (sans rien publier) si les données sont incohérentes."""
import json
import sys

from src.config import DATA_DIR


def main() -> int:
    d = json.loads((DATA_DIR / "predictions.json").read_text())
    errors = []
    for key in ("season", "week", "predictions", "ranking", "bilan", "picks", "generated_at"):
        if key not in d:
            errors.append(f"clé manquante : {key}")
    if len(d.get("ranking", [])) != 32:
        errors.append(f"classement : {len(d.get('ranking', []))} équipes au lieu de 32")
    for p in d.get("predictions", []):
        if not (0 < p["prob_home_win"] < 100) or abs(p["prob_home_win"] + p["prob_away_win"] - 100) > 0.2:
            errors.append(f"probabilités incohérentes : {p['game_id']}")
        for s in p.get("scorers", []):
            if not (0 <= s["prob"] < 100):
                errors.append(f"buteur incohérent : {s['name']}")
    sims = [t["sim"] for t in d.get("ranking", []) if t.get("sim")]
    if sims and abs(sum(s["sb"] for s in sims) - 100) > 1:
        errors.append("simulation : la somme des chances de Super Bowl n'est pas 100 %")
    for e in errors:
        print("ERREUR", e)
    print("Données valides" if not errors else f"{len(errors)} erreur(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
