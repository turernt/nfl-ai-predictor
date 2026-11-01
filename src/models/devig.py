"""Retrait de la marge du bookmaker par la méthode de Shin (1993).

La méthode proportionnelle répartit la marge à parts égales ; or les bookmakers la placent surtout sur les
outsiders (biais favori-outsider). Testé sur 3 930 matchs NFL (2012-2026) : outsiders sous 25 %,
annoncés 19,2 % / réels 18,3 % en proportionnel, contre 18,9 % / 18,9 % avec Shin.
"""
import math


def shin(implied: list[float]) -> list[float]:
    """Probabilités réelles à partir des probabilités implicites (1 / cote décimale)."""
    b = sum(implied)
    if b <= 1:                       # pas de marge (ou cotes incohérentes) : normalisation simple
        return [p / b for p in implied]

    def probs(z):
        return [(math.sqrt(z * z + 4 * (1 - z) * p * p / b) - z) / (2 * (1 - z)) for p in implied]

    lo, hi = 0.0, 0.4
    for _ in range(60):              # z = part des parieurs « initiés » ; on cherche Σp = 1
        z = (lo + hi) / 2
        if sum(probs(z)) > 1:
            lo = z
        else:
            hi = z
    p = probs((lo + hi) / 2)
    s = sum(p)
    return [x / s for x in p]


def home_prob_from_decimal(home: float, away: float) -> float:
    return shin([1 / home, 1 / away])[0]


def quarter_kelly(prob: float, price: float, cap: float = 0.02) -> float:
    """Mise conseillée en fraction de la bankroll : un quart du critère de Kelly, plafonné à 2 %."""
    b = price - 1
    if b <= 0:
        return 0.0
    f = (b * prob - (1 - prob)) / b
    return max(0.0, min(cap, f / 4))
