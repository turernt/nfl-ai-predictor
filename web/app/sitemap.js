import data from '../data/predictions.json';

const base = process.env.VERCEL_PROJECT_PRODUCTION_URL
  ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'http://localhost:3000';

export default function sitemap() {
  const now = new Date(data.generated_at);
  return [
    { url: `${base}/`, lastModified: now, changeFrequency: 'daily', priority: 1 },
    { url: `${base}/pronostics`, lastModified: now, changeFrequency: 'daily', priority: 0.9 },
    { url: `${base}/bilan`, lastModified: now, changeFrequency: 'weekly', priority: 0.6 },
    { url: `${base}/saison`, lastModified: now, changeFrequency: 'daily', priority: 0.8 },
    ...data.ranking.map((t) => ({ url: `${base}/equipe/${t.abbr}`, lastModified: now, changeFrequency: 'daily', priority: 0.6 })),
    ...data.predictions.map((g) => ({ url: `${base}/match/${g.game_id}`, lastModified: now, changeFrequency: 'daily', priority: 0.7 })),
  ];
}
