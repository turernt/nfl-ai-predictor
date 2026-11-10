"""Météo prévue au coup d'envoi (Open-Meteo : gratuit, sans clé). Prévisions disponibles à 7 jours."""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)
URL = "https://api.open-meteo.com/v1/forecast"

# Stade de chaque équipe à domicile : latitude, longitude, toit ("dome" = fermé, "retractable", "open")
STADIUMS = {
    "ARI": (33.5276, -112.2626, "retractable"), "ATL": (33.7554, -84.4008, "retractable"),
    "BAL": (39.2780, -76.6227, "open"), "BUF": (42.7738, -78.7870, "open"),
    "CAR": (35.2258, -80.8528, "open"), "CHI": (41.8623, -87.6167, "open"),
    "CIN": (39.0955, -84.5161, "open"), "CLE": (41.5061, -81.6995, "open"),
    "DAL": (32.7473, -97.0945, "retractable"), "DEN": (39.7439, -105.0201, "open"),
    "DET": (42.3400, -83.0456, "dome"), "GB": (44.5013, -88.0622, "open"),
    "HOU": (29.6847, -95.4107, "retractable"), "IND": (39.7601, -86.1639, "retractable"),
    "JAX": (30.3239, -81.6373, "open"), "KC": (39.0489, -94.4839, "open"),
    "LV": (36.0909, -115.1833, "dome"), "LA": (33.9535, -118.3392, "dome"),
    "LAC": (33.9535, -118.3392, "dome"), "MIA": (25.9580, -80.2389, "open"),
    "MIN": (44.9737, -93.2581, "dome"), "NE": (42.0909, -71.2643, "open"),
    "NO": (29.9511, -90.0812, "dome"), "NYG": (40.8128, -74.0742, "open"),
    "NYJ": (40.8128, -74.0742, "open"), "PHI": (39.9008, -75.1675, "open"),
    "PIT": (40.4468, -80.0158, "open"), "SF": (37.4032, -121.9698, "open"),
    "SEA": (47.5952, -122.3316, "open"), "TB": (27.9759, -82.5033, "open"),
    "TEN": (36.1665, -86.7713, "open"), "WAS": (38.9076, -76.8645, "open"),
}
WINDY_KMH = 19   # ~12 mph : au-delà, le total est passé sous la ligne 57,9 % du temps (594 matchs, 2012-2026)


def kickoff_utc(gameday: str, gametime: str) -> datetime | None:
    try:
        local = datetime.fromisoformat(f"{gameday}T{gametime or '13:00'}").replace(tzinfo=ZoneInfo("America/New_York"))
        return local.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def forecast(home: str, neutral: bool, gameday: str, gametime: str, now: datetime | None = None) -> dict | None:
    """{roof, temp_c, wind_kmh, precip_prob, windy} ou None si indisponible."""
    if neutral or home not in STADIUMS:
        return None
    lat, lon, roof = STADIUMS[home]
    if roof == "dome":
        return {"roof": "dome"}
    ko = kickoff_utc(gameday, gametime)
    now = now or datetime.now(timezone.utc)
    if ko is None or not (now - timedelta(hours=3) <= ko <= now + timedelta(days=7)):
        return {"roof": roof, "pending": True}
    try:
        r = requests.get(URL, params={"latitude": lat, "longitude": lon, "timezone": "UTC",
                                      "hourly": "temperature_2m,wind_speed_10m,precipitation_probability",
                                      "start_date": ko.date().isoformat(), "end_date": ko.date().isoformat()},
                         timeout=15)
        r.raise_for_status()
        h = r.json()["hourly"]
        hour = ko.replace(minute=0, second=0).strftime("%Y-%m-%dT%H:00")
        i = h["time"].index(hour) if hour in h["time"] else min(ko.hour, len(h["time"]) - 1)
        wind = h["wind_speed_10m"][i]
        return {"roof": roof, "temp_c": round(h["temperature_2m"][i]), "wind_kmh": round(wind),
                "precip_prob": h["precipitation_probability"][i],
                "windy": roof == "open" and wind is not None and wind >= WINDY_KMH}
    except Exception as e:
        logger.warning("Météo indisponible pour %s : %s", home, e)
        return {"roof": roof, "error": True}
