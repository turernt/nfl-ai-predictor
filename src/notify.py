"""Alertes Telegram (gratuites) : cotes au-dessus du juste prix, changement de quarterback, mouvement de ligne,
récapitulatif de fin de semaine.

Secrets GitHub : TELEGRAM_BOT_TOKEN (créé avec @BotFather) et TELEGRAM_CHAT_ID.
Chaque alerte n'est envoyée qu'une fois (mémoire dans data/notified.json et data/alert_state.json).
"""
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)
SITE = "https://nfl-ai-predictor.vercel.app"
LINE_MOVE = 2.0          # points d'écart (spread) qui déclenchent une alerte de mouvement de ligne


def _fr(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def _load(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return default


def _send(lines: list[str]) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": "\n".join(lines), "disable_web_page_preview": True}, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Alerte Telegram non envoyée : %s", e)
        return False


def send_value_alerts(payload: dict, data_dir) -> int:
    value = payload.get("picks", {}).get("value", [])
    if not value or not os.getenv("TELEGRAM_BOT_TOKEN"):
        return 0
    path = data_dir / "notified.json"
    seen = set(_load(path, []))
    new = [v for v in value if f'{v["game_id"]}:{v["team"]["abbr"]}:{v["book"]}' not in seen]
    if not new:
        return 0
    lines = ["Arthur Analytics : cote française au-dessus du juste prix", ""]
    for v in new:
        lines.append(f'• {v["team"]["nick"]} (contre {v["opponent"]["nick"]}) à {_fr(v["price"])} chez {v["book"]}'
                     f' : probabilité {round(v["prob"])} %, cote juste {_fr(v["fair_odds"])}, espérance +{_fr(v["ev"], 1)} %')
    lines += ["", f"{SITE}/pronostics", "Jouer comporte des risques. 09 74 75 13 13."]
    if not _send(lines):
        return 0
    seen.update(f'{v["game_id"]}:{v["team"]["abbr"]}:{v["book"]}' for v in new)
    path.write_text(json.dumps(sorted(seen)))
    return len(new)


def _recap(week: int, games: list[dict], tracking: dict) -> list[str]:
    decided = [g for g in games if g.get("pick_correct") is not None]
    ok = sum(g["pick_correct"] for g in decided)
    safe = [g for g in decided if max(g["prob_home_win"], g["prob_away_win"]) >= 70]
    sc = [s for g in games for s in g.get("scorers", []) if s.get("prob", 0) >= 40 and "scored" in s]
    lines = [f"Arthur Analytics : bilan de la semaine {week}", "",
             f"• Vainqueurs : {ok} sur {len(decided)}"]
    if safe:
        lines.append(f"• Favoris à 70 % ou plus : {sum(g['pick_correct'] for g in safe)} sur {len(safe)}")
    if sc:
        lines.append(f"• Buteurs annoncés à 40 % ou plus : {sum(s['scored'] for s in sc)} ont marqué sur {len(sc)}")
    v = (tracking or {}).get("value") or {}
    if v.get("settled"):
        lines.append(f"• Cotes signalées depuis le début : {v['won']} gagnées sur {v['settled']}, "
                     f"valeur de clôture moyenne {_fr(v['clv_avg'] or 0, 1)} %")
    if (tracking or {}).get("settled"):
        lines.append(f"• Suivi réel de la saison : {tracking['correct']} sur {tracking['settled']}")
    lines += ["", f"{SITE}/bilan"]
    return lines


def send_alerts(payload: dict, data_dir) -> int:
    """Changements de quarterback, mouvements de ligne et récapitulatif de fin de semaine."""
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        return 0
    path = data_dir / "alert_state.json"
    first = not path.exists()
    state = _load(path, {"games": {}, "recaps": []})
    msgs = []
    for p in payload.get("predictions", []):
        if p.get("status") != "upcoming":
            continue
        gid, qb = p["game_id"], p.get("factors", {}).get("qb", {})
        st = state["games"].setdefault(gid, {"qb": {"home": qb.get("home_name"), "away": qb.get("away_name")},
                                             "spread": p.get("vegas_spread")})
        for side in ("home", "away"):
            old, cur = st["qb"].get(side), qb.get(f"{side}_name")
            if old and cur and old != cur:
                msgs.append(f'• QB : {cur} remplace {old} chez les {p[side]["nick"]} '
                            f'({p["away"]["nick"]} @ {p["home"]["nick"]}). Probabilité : {p["home"]["nick"]} {round(p["prob_home_win"])} %')
            if cur:
                st["qb"][side] = cur
        s0, s1 = st.get("spread"), p.get("vegas_spread")
        if s0 is not None and s1 is not None and abs(s1 - s0) >= LINE_MOVE:
            fav = p["home"] if s1 < 0 else p["away"]
            msgs.append(f'• Ligne : {p["away"]["nick"]} @ {p["home"]["nick"]} passe de {_fr(abs(s0), 1)} à {_fr(abs(s1), 1)} pts '
                        f'({fav["nick"]} favoris). Probabilité : {p["home"]["nick"]} {round(p["prob_home_win"])} %')
            st["spread"] = s1
        elif s0 is None:
            st["spread"] = s1
    sent = 0
    if msgs and not first:
        sent += _send(["Arthur Analytics : changement avant un match", ""] + msgs + ["", SITE])
    # Récapitulatif : une fois que tous les matchs d'une semaine sont terminés
    archive = _load(data_dir / "archive.json", {})
    by_week = {}
    for g in archive.values():
        by_week.setdefault(g["week"], []).append(g)
    for week, games in sorted(by_week.items()):
        if week in state["recaps"] or not all(g.get("status") == "final" for g in games):
            continue
        if first or week < payload.get("week", 0) - 1:
            state["recaps"].append(week)       # pas de rattrapage des anciennes semaines
            continue
        if _send(_recap(week, games, payload.get("tracking"))):
            state["recaps"].append(week)
            sent += 1
    current = {p["game_id"] for p in payload.get("predictions", [])}
    state["games"] = {k: v for k, v in state["games"].items() if k in current}
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    return sent
