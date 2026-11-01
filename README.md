# Arthur Analytics

Prédictions NFL hebdomadaires (probabilités de victoire, scores projetés, buteurs probables), 100 % gratuit.

## Modèle

- **Modèle maison** = 50 % Elo (marge de victoire, régression inter-saisons) + 50 % efficacité par jeu (EPA, play-by-play),
  ajusté du quarterback annoncé (valeur EPA par dropback vs niveau habituel de l’équipe) et du repos.
- **Pronostic final** = 2/3 ligne des bookmakers + 1/3 modèle maison ; probabilité = loi normale (écart-type 13,5 pts).
- **Buteurs** : part des TD de l’équipe lissée vers la part d’opportunités (70 % zone rouge), TD attendus de l’équipe
  selon le score projeté, loi de Poisson ; calibration calée sur le bilan de la saison.
- **Bilan** : chaque semaine passée est re-prédite avec les seules données disponibles avant, puis comparée aux résultats.

## Fonctionnement

1. **GitHub Actions** (chaque mardi 9 h UTC) lance `python main.py --update`.
2. Le pipeline charge tous les calendriers depuis 2010 via `nflreadpy`, recalcule les Elo
   (marge de victoire, retour à la moyenne entre saisons, terrain neutre géré) et écrit
   `data/predictions.json`, `data/team_elos.csv`, `data/schedules.csv` (+ copie dans `web/data/`).
3. Le workflow commit les données puis déclenche un redéploiement **Vercel** (Deploy Hook).
4. Le site Next.js (`web/`) est généré statiquement à partir du JSON : aucune dépendance à l’API, aucun temps de réveil.
5. Pages : accueil (cartes filtrables), `/match/[id]` (analyse détaillée), `/bilan` (historique des pronostics).
6. L’**API FastAPI** (optionnelle, Hugging Face Spaces) expose les mêmes données et un endpoint de simulation de match.

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
