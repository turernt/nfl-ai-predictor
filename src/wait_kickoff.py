"""Attente avant le coup d'envoi : GitHub démarre les tâches programmées avec plusieurs heures de retard.

Lancé au début d'un passage programmé : si un match commence dans moins de 5 h 30, le passage attend jusqu'à
75 minutes avant le coup d'envoi (compositions et blessures de dernière minute connues), puis continue.
Sans match proche, ou pour un lancement manuel, il continue tout de suite. Gratuit : les minutes d'exécution
GitHub Actions sont illimitées pour un dépôt public.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.config import DATA_DIR
from src.ingestion.weather import kickoff_utc

BEFORE = timedelta(minutes=75)
MAX_WAIT = timedelta(hours=5, minutes=30)


def next_wait(now: datetime) -> timedelta:
    try:
        s = pd.read_csv(DATA_DIR / "schedules.csv")
    except FileNotFoundError:
        return timedelta(0)
    kicks = [k for g in s[s.home_score.isna()].itertuples()
             if (k := kickoff_utc(g.gameday, g.gametime if isinstance(g.gametime, str) else None)) and k > now]
    if not kicks:
        return timedelta(0)
    wait = min(kicks) - BEFORE - now
    return wait if timedelta(0) < wait <= MAX_WAIT else timedelta(0)


if __name__ == "__main__":
    if os.getenv("GITHUB_EVENT_NAME") != "schedule":
        sys.exit(0)
    w = next_wait(datetime.now(timezone.utc))
    print(f"Attente avant le prochain coup d'envoi : {int(w.total_seconds() // 60)} min", flush=True)
    time.sleep(w.total_seconds())
