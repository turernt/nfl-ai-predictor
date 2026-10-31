import math
from src.config import BASE_ELO, K_FACTOR, HFA, REGRESSION, ELO_PER_POINT


class NFLEloModel:
    """Elo façon FiveThirtyEight : marge de victoire + retour à la moyenne inter-saisons."""

    def __init__(self):
        self.ratings: dict[str, float] = {}

    def get(self, team: str) -> float:
        return self.ratings.setdefault(team, BASE_ELO)

    def new_season(self):
        for t, e in self.ratings.items():
            self.ratings[t] = e * (1 - REGRESSION) + BASE_ELO * REGRESSION

    def elo_diff(self, home: str, away: str, neutral: bool = False) -> float:
        return self.get(home) + (0 if neutral else HFA) - self.get(away)

    def update(self, home: str, away: str, home_score: float, away_score: float, neutral: bool = False):
        diff = self.elo_diff(home, away, neutral)
        exp_home = 1 / (1 + 10 ** (-diff / 400))
        margin = home_score - away_score
        actual = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        winner_diff = diff if margin > 0 else -diff
        mov = math.log(abs(margin) + 1) * 2.2 / (winner_diff * 0.001 + 2.2) if margin else 1.0
        shift = K_FACTOR * mov * (actual - exp_home)
        self.ratings[home] = self.get(home) + shift
        self.ratings[away] = self.get(away) - shift

    def predict(self, home: str, away: str, neutral: bool = False) -> dict:
        diff = self.elo_diff(home, away, neutral)
        p_home = 1 / (1 + 10 ** (-diff / 400))
        # Convention paris : spread négatif = l'équipe à domicile est favorite
        return {
            "prob_home_win": round(p_home * 100, 1),
            "prob_away_win": round((1 - p_home) * 100, 1),
            "predicted_spread": round(-diff / ELO_PER_POINT, 1),
        }


def confidence_label(prob_home: float) -> str:
    gap = abs(2 * prob_home - 100)
    return "Élevée" if gap > 40 else "Modérée" if gap > 20 else "Faible"  # >70 %, >60 %
