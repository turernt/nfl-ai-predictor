export const num = (n, d = 1) =>
  n.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d });

// Les horaires nflverse sont en heure de New York : on les convertit en heure de Paris.
export function kickoff(day, time) {
  if (!day) return null;
  const [y, m, d] = day.split('-').map(Number);
  const [h, mi] = (time || '13:00').split(':').map(Number);
  const guess = Date.UTC(y, m - 1, d, h, mi);
  const ny = new Date(new Date(guess).toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const utc = new Date(new Date(guess).toLocaleString('en-US', { timeZone: 'UTC' }));
  return new Date(guess + (utc - ny));
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
export const fmtDay = (date) =>
  cap(date.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Paris' }));
export const fmtWeekday = (date) =>
  cap(date.toLocaleDateString('fr-FR', { weekday: 'long', timeZone: 'Europe/Paris' }));
export const fmtHour = (date) =>
  date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' }).replace(':', ' h ');
export const fmtLong = (date) =>
  cap(date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Paris' }));

// Spread côté favori : « BUF −7,3 »
export function spreadLabel(spread, home, away) {
  if (spread == null) return '—';
  if (Math.abs(spread) < 0.05) return 'Pick’em';
  return `${spread < 0 ? home.abbr : away.abbr} −${num(Math.abs(spread))}`;
}

// Points à l’avantage d’une équipe : « +2,1 BUF »
export function edgeLabel(pts, home, away) {
  if (Math.abs(pts) < 0.05) return 'Neutre';
  return `${pts > 0 ? home.abbr : away.abbr} +${num(Math.abs(pts))}`;
}

export const pct = (x) => `${Math.round(x)}\u00a0%`;
export const statusFr = { Questionable: 'Incertain' };
