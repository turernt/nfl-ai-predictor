# NFL AI Predictor

Prédictions NFL hebdomadaires (probabilités, spread, confiance) calculées par un modèle Elo, 100 % gratuit.

## Fonctionnement

1. **GitHub Actions** (chaque mardi 9 h UTC) lance `python main.py --update`.
2. Le pipeline charge tous les calendriers depuis 2010 via `nflreadpy`, recalcule les Elo
   (marge de victoire, retour à la moyenne entre saisons, terrain neutre géré) et écrit
   `data/predictions.json`, `data/team_elos.csv`, `data/schedules.csv` (+ copie dans `web/data/`).
3. Le workflow commit les données puis déclenche un redéploiement **Vercel** (Deploy Hook).
4. Le site Next.js (`web/`) est généré statiquement à partir du JSON : aucune dépendance à l’API, aucun temps de réveil.
5. L’**API FastAPI** (optionnelle, Hugging Face Spaces) expose les mêmes données et un endpoint de simulation de match.

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
