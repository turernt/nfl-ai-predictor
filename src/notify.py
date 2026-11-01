"""Alerte Telegram (gratuite) quand une cote française dépasse le juste prix.

Secrets GitHub : TELEGRAM_BOT_TOKEN (créé avec @BotFather) et TELEGRAM_CHAT_ID.
Chaque occasion n'est envoyée qu'une fois (mémoire dans data/notified.json).
"""
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)


def _fr(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def send_value_alerts(payload: dict, data_dir, site_url: str = "https://nfl-ai-predictor.vercel.app") -> int:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    value = payload.get("picks", {}).get("value", [])
    if not token or not chat or not value:
        return 0
    path = data_dir / "notified.json"
    try:
        seen = set(json.loads(path.read_text()))
    except (FileNotFoundError, ValueError):
        seen = set()
    new = [v for v in value if f'{v["game_id"]}:{v["team"]["abbr"]}:{v["book"]}' not in seen]
    if not new:
        return 0
    lines = ["Arthur Analytics : cote française au-dessus du juste prix", ""]
    for v in new:
        lines.append(f'• {v["team"]["nick"]} (contre {v["opponent"]["nick"]}) à {_fr(v["price"])} chez {v["book"]}'
                     f' : probabilité {round(v["prob"])} %, cote juste {_fr(v["fair_odds"])}, espérance +{_fr(v["ev"], 1)} %')
    lines += ["", f"{site_url}/pronostics", "Jouer comporte des risques. 09 74 75 13 13."]
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": "\n".join(lines), "disable_web_page_preview": True}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning("Alerte Telegram non envoyée : %s", e)
        return 0
    seen.update(f'{v["game_id"]}:{v["team"]["abbr"]}:{v["book"]}' for v in new)
    path.write_text(json.dumps(sorted(seen)))
    return len(new)
