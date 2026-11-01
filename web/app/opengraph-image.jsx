import { ImageResponse } from 'next/og';
import data from '../data/predictions.json';

export const alt = 'Arthur Analytics, prédictions NFL';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function Image() {
  const rec = data.season_record || {};
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        padding: 72, background: '#0f1b2d', color: '#fff', fontFamily: 'sans-serif' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ width: 88, height: 88, borderRadius: 20, background: '#12805c', display: 'flex',
            alignItems: 'center', justifyContent: 'center', fontSize: 48, fontWeight: 700 }}>AA</div>
          <div style={{ fontSize: 44, fontWeight: 700 }}>Arthur Analytics</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ fontSize: 84, fontWeight: 700, lineHeight: 1 }}>{`Prédictions NFL, semaine ${data.week}`}</div>
          <div style={{ fontSize: 34, color: '#9fb0c4' }}>Probabilités de victoire, scores projetés et buteurs probables</div>
        </div>
        <div style={{ fontSize: 30, color: '#4fd1a1' }}>
          {rec.games ? `${rec.correct} bons pronostics sur ${rec.games} cette saison` : `Saison ${data.season}`}
        </div>
      </div>
    ),
    size,
  );
}
