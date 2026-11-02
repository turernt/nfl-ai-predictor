# Arthur Analytics

Prédictions NFL hebdomadaires (probabilités de victoire, scores projetés, buteurs probables), 100 % gratuit.

## Modèle

- **Classement de force** : notes en points ajustées par moindres carrés sur toutes les lignes des bookmakers de la saison, rappelées vers le modèle maison ; elles servent aux matchs des semaines suivantes et à la simulation des playoffs (écart moyen de 2,6 pts avec les futures lignes, contre 2,8 pour le modèle seul).
- **Modèle maison** = 50 % Elo (marge de victoire, régression inter-saisons) + 50 % efficacité par jeu (EPA, play-by-play),
  ajusté du quarterback annoncé (valeur EPA par dropback vs niveau habituel de l’équipe) et du repos.
- **Probabilité retenue** = cotes des bookmakers, marge retirée (testées plus fiables que le modèle et que tout mélange, 899 matchs 2023-2026) ; le modèle maison sert de second avis.
- **Pronostics** (`/pronostics`) : favoris à 70 % ou plus, buteurs à 40 % ou plus, matchs à éviter, avec la fiabilité historique de chaque palier (depuis 2012).
- **Buteurs** : part des TD de l’équipe lissée vers la part d’opportunités (70 % zone rouge), TD attendus de l’équipe
  selon le score projeté, loi de Poisson, puis recalibration logistique ajustée sur 2024-2025 (5 760 prédictions) et vérifiée sur 2026.
- **Bilan** : chaque semaine passée est re-prédite avec les seules données disponibles avant, puis comparée aux résultats.

## Fonctionnement

1. **GitHub Actions** (deux fois par jour, 13 h 17 et 21 h 47 UTC, pour suivre cotes, blessures et QB annoncés) lance `python main.py --update`.
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

Une mise à jour consomme 6 crédits (2 marchés × 3 régions) ; avec deux mises à jour par jour, environ 370 crédits par mois.

## Alertes Telegram (facultatif, gratuit)

1. Dans Telegram, écrire à @BotFather, commande `/newbot` : il fournit un jeton.
2. Écrire un message au bot, puis ouvrir `https://api.telegram.org/bot<JETON>/getUpdates` pour lire le `chat.id`.
3. GitHub → *Settings → Secrets and variables → Actions* : `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`.

Une alerte part quand une cote française dépasse le juste prix d’au moins 2 % (une seule fois par occasion).

## Fiabilité et contrôles

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
