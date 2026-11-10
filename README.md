# Arthur Analytics

Projet personnel, sans usage commercial. Le site n’est pas proposé aux moteurs de recherche (noindex).

Prédictions NFL hebdomadaires (probabilités de victoire, scores projetés, buteurs probables), 100 % gratuit.

## Modèle

- **Classement de force** : notes en points ajustées par moindres carrés sur toutes les lignes des bookmakers de la saison, rappelées vers le modèle maison ; elles servent aux matchs des semaines suivantes et à la simulation des playoffs (écart moyen de 2,6 pts avec les futures lignes, contre 2,8 pour le modèle seul).
- **Modèle maison** = 50 % Elo (marge de victoire, régression inter-saisons) + 50 % efficacité par jeu (EPA, play-by-play),
  ajusté du quarterback annoncé (valeur EPA par dropback vs niveau habituel de l’équipe) et du repos.
- **Probabilité retenue** = cotes des bookmakers, marge retirée (médiane des bookmakers dont la marge ne dépasse pas 6 %) ; aucun mélange avec le modèle maison n’a fait mieux sur 899 matchs (2023-2026). Le modèle maison sert de second avis. Conversion écart de points → probabilité : écart-type de 11,5 points (calé sur 2016-2026).
- **Gel au coup d’envoi** : un match commencé n’est plus recalculé ; sa dernière version publiée est conservée dans `data/archive.json` (page de match accessible toute la saison, matchs terminés visibles sur l’accueil).
- **Pronostics** (`/pronostics`) : favoris à 70 % ou plus, buteurs à 40 % ou plus, matchs à éviter, avec la fiabilité historique de chaque palier (depuis 2012).
- **Buteurs** : le modèle suit chaque joueur match par match (TD attendus selon la position de ses courses et de ses cibles,
  temps de jeu, statut médical), répartit les TD attendus de l’équipe selon la composition du jour, puis applique une
  régression logistique réajustée à chaque mise à jour sur les prédictions passées. Hors échantillon (2025-2026), son buteur
  n°1 de chaque match a marqué 48,0 % du temps contre 42,9 % avec l’ancien calcul.
- **Composition probable** : hiérarchie des postes, effectif actif et rapport de blessures (QB, coureurs, receveurs, tight end).
- **Bilan** : d’abord le suivi réel (vainqueurs, buteurs et cotes signalées, figés au coup d’envoi, valeur de clôture contre la ligne nflverse), puis une simulation rétrospective de la saison.

## Fonctionnement

1. **GitHub Actions** (quatre passages par jour et des passages en plus avant les matchs du jeudi, du dimanche et du lundi ; GitHub les démarre souvent avec retard) lance `python main.py --update`. En cas d’échec, rien n’est publié et une alerte Telegram part si les secrets sont renseignés.
2. Le pipeline charge tous les calendriers depuis 2010 via `nflreadpy`, recalcule les Elo
   (marge de victoire, retour à la moyenne entre saisons, terrain neutre géré) et écrit
   `data/predictions.json`, `data/team_elos.csv`, `data/schedules.csv` (+ copie dans `web/data/`).
3. Le workflow commit les données puis déclenche un redéploiement **Vercel** (Deploy Hook).
4. Le site Next.js (`web/`) est généré statiquement à partir du JSON : aucune dépendance à l’API, aucun temps de réveil.
5. Pages : accueil (cartes filtrables), `/pronostics`, `/saison` (course aux playoffs, 10 000 simulations), `/equipe/[abbr]` (calendrier et chances par équipe), `/match/[id]` (analyse, cotes, mouvement du marché), `/bilan` (historique et rendement en euros).
6. L’**API FastAPI** (optionnelle, Hugging Face Spaces) expose les mêmes données et un endpoint de simulation de match.

## Cotes de plusieurs bookmakers (facultatif, gratuit)

Par défaut, les probabilités viennent des lignes nflverse (une seule source). Pour utiliser la moyenne
de tous les bookmakers (américains, européens dont Pinnacle, et français : Betclic, Winamax, Unibet, PMU,
Parions Sport, NetBet) et repérer les cotes françaises au-dessus du juste prix :

1. Créer une clé gratuite sur https://the-odds-api.com (offre Starter, 500 crédits/mois, sans carte bancaire).
2. GitHub → *Settings → Secrets and variables → Actions → New repository secret* : nom `ODDS_API_KEY`.

Un appel consomme 6 crédits (2 marchés × 3 régions). Les cotes sont gardées en cache (`data/odds_cache.json`) : l’API n’est rappelée qu’une fois par jour, et toutes les 3 heures quand un match commence dans les 6 heures, soit environ 290 crédits par mois quel que soit le nombre de passages. Les matchs déjà commencés sont ignorés (cotes en direct).

## Alertes Telegram (facultatif, gratuit)

1. Dans Telegram, écrire à @BotFather, commande `/newbot` : il fournit un jeton.
2. Écrire un message au bot, puis ouvrir `https://api.telegram.org/bot<JETON>/getUpdates` pour lire le `chat.id`.
3. GitHub → *Settings → Secrets and variables → Actions* : `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`.

Une alerte part quand une cote française dépasse le juste prix d’au moins 3 % (une seule fois par occasion).

## Études et vérifications

- `src/studies.py` recalcule à chaque passage les chiffres affichés sur le site : écart-type points → probabilité, méthode de Shin contre méthode simple, effet du vent observé (nflverse, depuis 2012) et du vent prévu (archive gratuite Open-Meteo depuis 2022, mise en cache dans `data/wind_forecasts.json`). Le signal « moins de points » sur les matchs venteux n'apparaît que si la borne basse de l'intervalle de confiance dépasse 52,4 %.
- `studies/playoff_backtest.py` rejoue la simulation des playoffs sur 2020-2025 (`data/playoff_backtest.json`, affiché sur /saison). À relancer une fois par an : `python -m studies.playoff_backtest`.
- `data/sim_history.json` et `data/seasons.json` gardent l'évolution des chances de playoffs et le bilan de chaque saison (page /archives).

## Alertes Telegram

Avec les secrets `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` : cote française au-dessus du juste prix, changement de quarterback, ligne qui bouge de 2 points ou plus, et bilan de la semaine une fois tous ses matchs terminés. Un échec du workflow est aussi signalé.

## Fiabilité et contrôles

- Un passage programmé qui démarre moins de 5 h 30 avant un match attend jusqu'à 75 minutes avant le coup d'envoi (`src/wait_kickoff.py`), pour compenser les retards de GitHub.

- Chaque exécution valide les données (`python -m src.validate`) et construit le site avant de publier : en cas d’erreur, rien n’est mis en ligne.
- Les pronostics publiés sont enregistrés dans `data/picks_log.json` (probabilité à la publication, à la clôture, résultat) : c’est le bilan en conditions réelles et la valeur de clôture (CLV) de la page Bilan.
- Blessures (rapport officiel), météo prévue (Open-Meteo, sans clé) et mouvements de cotes (`data/line_history.json`) sont affichés sur chaque page de match.
- Simulation des playoffs : départages par confrontation directe, bilan de division puis de conférence.

## Installation locale

```bash
pip install -r requirements.txt
python main.py --update              # génère les données
uvicorn src.api.main:app --reload    # API sur http://localhost:8000/docs
cd web && npm install && npm run dev # site sur http://localhost:3000
```

## Déploiement

**GitHub** : pousser le dépôt. Lancer une première fois le workflow via *Actions → Update NFL Data & Elo → Run workflow*.

**Vercel** : importer le dépôt, *Root Directory* = `web`. Puis *Settings → Git → Deploy Hooks* : créer un hook,
et l’enregistrer dans GitHub (*Settings → Secrets → Actions*) sous le nom `VERCEL_DEPLOY_HOOK`.

**Hugging Face Spaces (optionnel)** : créer un Space SDK *Docker*, y pousser le dépôt (le `Dockerfile` écoute sur 7860).
Ajouter la variable `DATA_URL` = `https://raw.githubusercontent.com/<user>/<repo>/main/data/predictions.json`
pour que l’API reste à jour sans redéploiement.

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/` | État + saison/semaine |
| GET | `/api/v1/predictions` | Matchs de la semaine à venir |
| GET | `/api/v1/elos` | Classement Elo |
| POST | `/api/v1/predict` | `{"home_team":"KC","away_team":"BUF","neutral_site":false}` |

## Réglages du modèle

Dans `src/config.py` : `FIRST_SEASON`, `K_FACTOR`, `HFA`, `REGRESSION`, `ELO_PER_POINT`.
Convention de spread : négatif = l’équipe à domicile est favorite (comme les bookmakers).
