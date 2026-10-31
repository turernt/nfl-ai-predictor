import json
import logging
import shutil
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_DIR, WEB_DATA_DIR, FIRST_SEASON, HFA
from src.ingestion.loader import load_schedules, load_teams, load_player_stats, load_injury_report
from src.models.elo_engine import NFLEloModel, confidence_label
from src.models.scorers import build_player_table, team_td_rates, likely_scorers

DEFAULT_TOTAL = 44.0  # total de points moyen en NFL, utilisé sans ligne des bookmakers

logger = logging.getLogger(__name__)


def current_season(now: datetime | None = None) -> int:
    now = now or datetime.now()
    return now.year if now.month >= 8 else now.year - 1


def _fr(x: float) -> str:
    return f"{x:+.1f}".replace("-", "−").replace(".", ",")


def _commentary(fav: str, dog: str, prob: float, model_spread: float, vegas_spread: float | None,
                vegas_fav: str | None, home_is_fav: bool, neutral: bool) -> str:
    venue = "" if neutral else (", à domicile" if home_is_fav else ", à l’extérieur")
    text = f"Avantage {fav} ({prob:.0f}\u00a0%){venue}."
    if vegas_spread is not None and vegas_spread != 0 and (vegas_spread < 0) != (model_spread < 0):
        text += f" Les bookmakers voient plutôt {vegas_fav} gagner : lecture opposée à surveiller."
    elif vegas_spread is not None and abs(model_spread - vegas_spread) >= 3:
        side = "plus large" if abs(model_spread) > abs(vegas_spread) else "plus serré"
        text += f" Le modèle annonce un écart {side} que les bookmakers ({_fr(vegas_spread)})."
    elif prob < 58:
        text += f" Match très ouvert face à {dog}."
    return text


def run_pipeline() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    season = current_season()
    seasons = list(range(FIRST_SEASON, season + 1))
    sched = load_schedules(seasons)
    teams = load_teams().set_index("team_abbr")

    model = NFLEloModel()
    hits, games_scored = 0, 0
    last_season = None

    played = sched.dropna(subset=["home_score", "away_score"])
    for g in played.itertuples():
        if g.season != last_season:
            if last_season is not None:
                model.new_season()
            last_season = g.season
        neutral = g.location == "Neutral"
        if g.season == season and g.home_score != g.away_score:
            p = model.predict(g.home_team, g.away_team, neutral)["prob_home_win"]
            games_scored += 1
            hits += (p >= 50) == (g.home_score > g.away_score)
        model.update(g.home_team, g.away_team, g.home_score, g.away_score, neutral)

    if last_season is not None and last_season < season:
        model.new_season()  # intersaison : on applique la régression avant la semaine 1

    cur = played[played.season == season]
    record = {}
    for g in cur.itertuples():
        for t, us, them in ((g.home_team, g.home_score, g.away_score), (g.away_team, g.away_score, g.home_score)):
            w, l, d = record.get(t, (0, 0, 0))
            record[t] = (w + (us > them), l + (us < them), d + (us == them))

    def team_info(abbr: str) -> dict:
        row = teams.loc[abbr] if abbr in teams.index else None
        return {
            "abbr": abbr,
            "name": row["team_name"] if row is not None else abbr,
            "nick": row["team_nick"] if row is not None else abbr,
            "color": row["team_color"] if row is not None else "#444444",
            "logo": row["team_logo_espn"] if row is not None else None,
            "elo": round(model.get(abbr), 1),
            "record": "-".join(str(x) for x in record.get(abbr, (0, 0, 0))[:2])
                      + (f"-{record[abbr][2]}" if record.get(abbr, (0, 0, 0))[2] else ""),
        }

    upcoming = sched[(sched.season == season) & sched.home_score.isna()]
    week = int(upcoming.week.min()) if not upcoming.empty else None
    predictions = []
    if week is not None:
        try:
            stats = load_player_stats(season)
            players = build_player_table(stats, week)
            rates = team_td_rates(stats, sched, season, week)
            injuries = load_injury_report(season, week)
        except Exception as e:
            logger.warning("Buteurs probables indisponibles : %s", e)
            players, rates, injuries = pd.DataFrame(), pd.DataFrame(), {}
        for g in upcoming[upcoming.week == week].itertuples():
            neutral = g.location == "Neutral"
            pred = model.predict(g.home_team, g.away_team, neutral)
            vegas = None if pd.isna(g.spread_line) else -float(g.spread_line)
            home, away = team_info(g.home_team), team_info(g.away_team)
            home_fav = pred["prob_home_win"] >= 50
            fav, dog = (home, away) if home_fav else (away, home)
            total = DEFAULT_TOTAL if pd.isna(g.total_line) else float(g.total_line)
            home_pts = total / 2 - pred["predicted_spread"] / 2
            away_pts = total - home_pts
            scorers = (likely_scorers(players, rates, g.away_team, away_pts, injuries)
                       + likely_scorers(players, rates, g.home_team, home_pts, injuries))
            predictions.append({
                "game_id": g.game_id,
                "week": week,
                "game_type": g.game_type,
                "gameday": g.gameday,
                "gametime": g.gametime,
                "neutral_site": neutral,
                "home": home,
                "away": away,
                **pred,
                "vegas_spread": vegas,
                "vegas_total": None if pd.isna(g.total_line) else float(g.total_line),
                "projected_score": {"home": round(home_pts), "away": round(away_pts)},
                "scorers": sorted(scorers, key=lambda x: x["prob"], reverse=True),
                "confidence_score": confidence_label(pred["prob_home_win"]),
                "commentary": _commentary(fav["nick"], dog["nick"], max(pred["prob_home_win"], pred["prob_away_win"]),
                                          pred["predicted_spread"], vegas,
                                          None if vegas is None else (home["nick"] if vegas < 0 else away["nick"]),
                                          home_fav, neutral),
            })

    ranking = sorted((team_info(t) for t in teams.index if t in model.ratings),
                     key=lambda t: t["elo"], reverse=True)

    top_scorers = sorted((dict(sc, game_id=pr["game_id"],
                               opponent=pr["home"]["abbr"] if sc["team"] == pr["away"]["abbr"] else pr["away"]["abbr"])
                          for pr in predictions for sc in pr["scorers"]),
                         key=lambda x: x["prob"], reverse=True)[:12]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": season,
        "week": week,
        "model": {"name": "Elo (marge de victoire, régression inter-saisons)", "hfa_elo": HFA},
        "season_record": {"games": games_scored, "correct": hits,
                          "accuracy": round(hits / games_scored * 100, 1) if games_scored else None},
        "predictions": predictions,
        "top_scorers": top_scorers,
        "ranking": ranking,
    }

    (DATA_DIR / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    pd.DataFrame(ranking)[["abbr", "name", "elo"]].to_csv(DATA_DIR / "team_elos.csv", index=False)
    sched[sched.season == season].to_csv(DATA_DIR / "schedules.csv", index=False)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA_DIR / "predictions.json", WEB_DATA_DIR / "predictions.json")
    logger.info("Saison %s, semaine %s : %d prédictions, modèle %s/%s cette saison",
                season, week, len(predictions), hits, games_scored)
    return payload
