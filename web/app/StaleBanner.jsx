'use client';
import { useEffect, useState } from 'react';

// Affiche un avertissement si les données ont plus de 48 h (mise à jour automatique en échec).
export default function StaleBanner({ at }) {
  const [stale, setStale] = useState(false);
  useEffect(() => { setStale(Date.now() - new Date(at).getTime() > 48 * 3600 * 1000); }, [at]);
  if (!stale) return null;
  const d = new Date(at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', timeZone: 'Europe/Paris' });
  return (
    <div className="stale" role="status">
      Données du {d} : la mise à jour automatique a pris du retard. Les cotes et les blessures ont pu changer depuis.
    </div>
  );
}
