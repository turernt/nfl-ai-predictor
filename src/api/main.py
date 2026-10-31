"""API FastAPI : sert les prédictions générées par le pipeline.

Les données sont lues depuis data/predictions.json, ou depuis DATA_URL
(ex. l'URL raw GitHub du fichier) pour rester à jour sans redéployer le Space.
"""
import json
import os
import time

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import PredictionRequest, PredictionResponse
from src.config import DATA_DIR, HFA, ELO_PER_POINT
from src.models.elo_engine import confidence_label

DATA_URL = os.getenv("DATA_URL")
CACHE_TTL = 3600
_cache = {"data": None, "ts": 0.0}

app = FastAPI(title="NFL AI Predictor API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def get_data() -> dict:
    if _cache["data"] and time.time() - _cache["ts"] < CACHE_TTL:
        return _cache["data"]
    try:
        if DATA_URL:
            r = requests.get(DATA_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
        else:
            data = json.loads((DATA_DIR / "predictions.json").read_text())
    except Exception as e:
        if _cache["data"]:
            return _cache["data"]
        raise HTTPException(503, f"Données indisponibles : lancez `python main.py --update` ({e})")
    _cache.update(data=data, ts=time.time())
    return data


@app.get("/")
def health():
    d = get_data()
    return {"status": "online", "season": d["season"], "week": d["week"], "generated_at": d["generated_at"]}


@app.get("/api/v1/predictions")
def predictions():
    d = get_data()
    return {k: d[k] for k in ("season", "week", "generated_at", "season_record", "predictions")}


@app.get("/api/v1/elos")
def elos():
    return get_data()["ranking"]


@app.post("/api/v1/predict", response_model=PredictionResponse)
def predict(req: PredictionRequest):
    elo = {t["abbr"]: t["elo"] for t in get_data()["ranking"]}
    home, away = req.home_team.upper(), req.away_team.upper()
    for t in (home, away):
        if t not in elo:
            raise HTTPException(404, f"Équipe inconnue : {t}. Valeurs possibles : {sorted(elo)}")
    if home == away:
        raise HTTPException(422, "Une équipe ne peut pas jouer contre elle-même.")
    diff = elo[home] + (0 if req.neutral_site else HFA) - elo[away]
    p = 1 / (1 + 10 ** (-diff / 400)) * 100
    return PredictionResponse(
        home_team=home, away_team=away, home_elo=elo[home], away_elo=elo[away],
        prob_home_win=round(p, 1), prob_away_win=round(100 - p, 1),
        predicted_spread=round(-diff / ELO_PER_POINT, 1),
        confidence_score=confidence_label(p),
        commentary=f"Écart Elo de {diff:+.0f} points, avantage du terrain inclus." if not req.neutral_site
        else f"Écart Elo de {diff:+.0f} points, terrain neutre.",
    )
