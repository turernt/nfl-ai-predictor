"""Simulation Monte-Carlo de la fin de saison : playoffs, titre de division, tête de série n°1, Super Bowl.

Chaque simulation tire une erreur sur la force de chaque équipe (incertitude du classement), puis joue
tous les matchs restants et les playoffs (format NFL : 7 qualifiés par conférence, n°1 exempté).
Méthode inspirée de nflseedR et du modèle Next Gen Stats (10 000 simulations).
Départages appliqués : confrontation directe (deux équipes), bilan de division, bilan de conférence, puis tirage.
"""
import math

import numpy as np
import pandas as pd

SIMS = 10000
GAME_SD = 11.2          # écart-type du score final autour du spread ; avec RATING_SD, l'écart total vaut ≈ 11,5 pts
RATING_SD = 2.0         # incertitude sur la force réelle de chaque équipe, en points
HFA_PTS = 1.7


def _p(margin):
    return 0.5 * (1 + np.vectorize(math.erf)(margin / GAME_SD / math.sqrt(2)))


def simulate(remaining: pd.DataFrame, played: pd.DataFrame, record: dict, ratings: dict, teams: pd.DataFrame,
             fixed_probs: dict | None = None, sims: int = SIMS, seed: int = 7, hfa_pts: float = HFA_PTS) -> dict:
    """remaining : matchs restants (home_team, away_team, game_id, location, week).
    ratings : points au-dessus de la moyenne. fixed_probs : {game_id: proba domicile} (cotes du marché)."""
    rng = np.random.default_rng(seed)
    abbrs = [a for a in teams.index if a in ratings]
    idx = {a: i for i, a in enumerate(abbrs)}
    T = len(abbrs)
    base = np.array([ratings[a] for a in abbrs])
    noise = rng.normal(0, RATING_SD, (sims, T))
    strength = base + noise

    wins = np.tile(np.array([record.get(a, (0, 0, 0))[0] + 0.5 * record.get(a, (0, 0, 0))[2] for a in abbrs], float), (sims, 1))
    g = remaining[remaining.home_team.isin(idx) & remaining.away_team.isin(idx)]
    h = g.home_team.map(idx).to_numpy(); a = g.away_team.map(idx).to_numpy()
    hfa = np.where(g.location.to_numpy() == "Neutral", 0.0, hfa_pts)
    margin = strength[:, h] - strength[:, a] + hfa
    prob = _p(margin)
    fixed_probs = fixed_probs or {}
    for j, gid in enumerate(g.game_id):
        if gid in fixed_probs:
            prob[:, j] = fixed_probs[gid]
    home_win = rng.random(prob.shape) < prob
    conf = teams.loc[abbrs, "team_conf"].to_numpy()
    div = teams.loc[abbrs, "team_division"].to_numpy()
    div_w = np.zeros((sims, T)); conf_w = np.zeros((sims, T))
    pair_games = {}   # (i, j) trié -> liste de (indice de match restant ou résultat fixe, équipe à domicile)
    pl = played[played.home_team.isin(idx) & played.away_team.isin(idx)]
    for x in pl.itertuples():
        hi, ai = idx[x.home_team], idx[x.away_team]
        hw = 1.0 if x.home_score > x.away_score else 0.0 if x.home_score < x.away_score else 0.5
        pair_games.setdefault(tuple(sorted((hi, ai))), []).append(("fixed", hi, hw))
        if conf[hi] == conf[ai]:
            conf_w[:, hi] += hw; conf_w[:, ai] += 1 - hw
            if div[hi] == div[ai]:
                div_w[:, hi] += hw; div_w[:, ai] += 1 - hw
    for j in range(len(g)):
        wins[:, h[j]] += home_win[:, j]
        wins[:, a[j]] += ~home_win[:, j]
        pair_games.setdefault(tuple(sorted((h[j], a[j]))), []).append(("sim", h[j], j))
        if conf[h[j]] == conf[a[j]]:
            conf_w[:, h[j]] += home_win[:, j]; conf_w[:, a[j]] += ~home_win[:, j]
            if div[h[j]] == div[a[j]]:
                div_w[:, h[j]] += home_win[:, j]; div_w[:, a[j]] += ~home_win[:, j]
    rand = rng.random((sims, T))

    def h2h(s, i, j):
        """Victoires de i contre j (résultats réels + simulés)."""
        w = 0.0
        for kind, home, v in pair_games.get(tuple(sorted((i, j))), []):
            hw = v if kind == "fixed" else float(home_win[s, v])
            w += hw if home == i else 1 - hw
        return w

    def ranked(s, group):
        """Classe un groupe d'équipes selon les départages NFL simplifiés."""
        group = list(group)
        by_w = {}
        for t in group:
            by_w.setdefault(wins[s, t], []).append(t)
        out = []
        for w in sorted(by_w, reverse=True):
            tied = by_w[w]
            if len(tied) == 1:
                out += tied; continue
            same_div = len({div[t] for t in tied}) == 1
            def key(t):
                hh = h2h(s, t, [u for u in tied if u != t][0]) if len(tied) == 2 else 0.0
                return (hh, div_w[s, t] if same_div else 0.0, conf_w[s, t], rand[s, t])
            out += sorted(tied, key=key, reverse=True)
        return out
    made = np.zeros((sims, T), bool); div_win = np.zeros((sims, T), bool); seed1 = np.zeros((sims, T), bool)
    conf_win = np.zeros((sims, T), bool); sb_win = np.zeros((sims, T), bool)

    def play(i, j, s, home):  # renvoie le gagnant entre i et j (home = équipe à domicile ou None)
        m = strength[s, i] - strength[s, j] + (hfa_pts if home == i else -hfa_pts if home == j else 0)
        return i if rng.random() < 0.5 * (1 + math.erf(m / GAME_SD / math.sqrt(2))) else j

    conf_idx = {c: np.where(conf == c)[0] for c in np.unique(conf)}
    div_idx = {d: np.where(div == d)[0] for d in np.unique(div)}
    for s in range(sims):
        champs = []
        for c, members in conf_idx.items():
            winners = [ranked(s, d_m)[0] for d, d_m in div_idx.items() if conf[d_m[0]] == c]
            winners = ranked(s, winners)
            others = ranked(s, [t for t in members if t not in winners])[:3]
            seeds = winners + others          # seeds[0] = n°1
            made[s, seeds] = True; div_win[s, winners] = True; seed1[s, seeds[0]] = True
            # Wild card : 2-7, 3-6, 4-5 ; le n°1 est exempté
            alive = [seeds[0]] + [play(seeds[k], seeds[7 - k], s, seeds[k]) for k in (1, 2, 3)]
            alive.sort(key=lambda t: seeds.index(t))
            # Divisionnaire : meilleur contre moins bon restant
            r2 = [play(alive[0], alive[3], s, alive[0]), play(alive[1], alive[2], s, alive[1])]
            r2.sort(key=lambda t: seeds.index(t))
            champ = play(r2[0], r2[1], s, r2[0])
            conf_win[s, champ] = True; champs.append(champ)
        if len(champs) == 2:
            sb_win[s, play(champs[0], champs[1], s, None)] = True

    out = {}
    for a_, i in idx.items():
        out[a_] = {"proj_wins": round(float(wins[:, i].mean()), 1),
                   "playoff": round(float(made[:, i].mean()) * 100, 1),
                   "division": round(float(div_win[:, i].mean()) * 100, 1),
                   "seed1": round(float(seed1[:, i].mean()) * 100, 1),
                   "conf": round(float(conf_win[:, i].mean()) * 100, 1),
                   "sb": round(float(sb_win[:, i].mean()) * 100, 1)}
    # « Si victoire / si défaite » cette semaine (comme le modèle Next Gen Stats)
    first_week = g.week.min() if len(g) else None
    for j, row in enumerate(g.itertuples()):
        if row.week != first_week:
            continue
        hw = home_win[:, j]
        for team, won in ((row.home_team, hw), (row.away_team, ~hw)):
            i = idx[team]
            if won.any() and (~won).any():
                out[team]["if_win"] = round(float(made[won, i].mean()) * 100, 1)
                out[team]["if_lose"] = round(float(made[~won, i].mean()) * 100, 1)
    return out
