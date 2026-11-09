"""Composition probable d'une équipe pour le match à venir.

Trois sources croisées : la hiérarchie des postes (depth chart), l'effectif actif (les joueurs en réserve des
blessés ou en équipe d'entraînement sont écartés) et le rapport de blessures de la semaine.
"""
import pandas as pd

SLOTS = [("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1)]   # nombre de joueurs disponibles affichés par poste
ON_ROSTER = {"ACT", "INA"}                              # dans les 53 (INA = inactif au match précédent)
UNAVAILABLE = {"Out", "Doubtful"}


def build(depth: pd.DataFrame | None, roster: pd.DataFrame | None, statuses: dict) -> dict:
    """{équipe: {"players": [...], "active_ids": {...}, "qb": {...} ou None, "labels": {player_id: "RB1"}}}"""
    if depth is None or depth.empty:
        return {}
    active = None
    if roster is not None and not roster.empty:
        active = {t: set(g.loc[g["status"].isin(ON_ROSTER), "gsis_id"]) for t, g in roster.groupby("team")}
    out = {}
    for team, grp in depth.groupby("team"):
        ids = active.get(team) if active else None
        players, labels, qb = [], {}, None
        for pos, wanted in SLOTS:
            rows = grp[grp["pos_abb"] == pos].drop_duplicates("gsis_id").sort_values("pos_rank")
            if ids is not None:
                rows = rows[rows["gsis_id"].isin(ids)]
            available = 0
            for i, r in enumerate(rows.itertuples(), start=1):
                labels[r.gsis_id] = f"{pos}{i}"
                if available >= wanted:
                    continue
                status = statuses.get(r.gsis_id)
                ok = status not in UNAVAILABLE
                players.append({"player_id": r.gsis_id, "name": r.player_name, "pos": pos, "rank": i,
                                "status": status if isinstance(status, str) else None, "available": ok})
                if ok:
                    available += 1
                    if pos == "QB" and qb is None:
                        qb = {"player_id": r.gsis_id, "name": r.player_name}
        out[team] = {"players": players, "active_ids": ids, "qb": qb, "labels": labels}
    return out


def starting_qb(lineup: dict | None, qb_id, qb_name, statuses: dict) -> tuple[object, object, bool]:
    """QB retenu pour le match : celui du calendrier, sauf s'il est forfait ou hors de l'effectif actif.

    Renvoie (identifiant, nom, changé ?)."""
    if not lineup or not lineup.get("qb"):
        return qb_id, qb_name, False
    ids = lineup.get("active_ids")
    announced_ok = (isinstance(qb_id, str) and statuses.get(qb_id) not in UNAVAILABLE
                    and (ids is None or qb_id in ids))
    if announced_ok or lineup["qb"]["player_id"] == qb_id:
        return qb_id, qb_name, False
    return lineup["qb"]["player_id"], lineup["qb"]["name"], True
