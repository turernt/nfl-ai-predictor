import Link from 'next/link';
import { pct, statusFr } from './lib';

export function Mark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#12805c" />
      <path d="M28 50 L41 14 L54 50 M33.5 37 H48.5" stroke="#fff" strokeOpacity="0.5" strokeWidth="6" fill="none" strokeLinejoin="round" strokeLinecap="round" />
      <path d="M10 50 L23 14 L36 50 M15.5 37 H30.5" stroke="#fff" strokeWidth="6" fill="none" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Topbar({ current }) {
  const links = [['/', 'Matchs'], ['/#buteurs', 'Buteurs'], ['/bilan', 'Bilan'], ['/#classement', 'Classement']];
  return (
    <nav className="topbar">
      <div className="topbar-in">
        <Link className="brand" href="/"><Mark /><span>Arthur Analytics</span></Link>
        <div className="links">
          {links.map(([href, label]) => (
            <Link key={href} href={href} aria-current={current === label ? 'page' : undefined}>{label}</Link>
          ))}
        </div>
      </div>
    </nav>
  );
}

export function Footer({ updated }) {
  return (
    <footer className="footer">
      <span>Arthur Analytics. Données nflverse{updated ? `, mises à jour le ${updated}` : ''}.</span>
      <span>Prédictions statistiques à titre informatif, pas des conseils de pari.</span>
    </footer>
  );
}

export function Logo({ team, size = 36 }) {
  return team.logo
    ? <img className="logo" src={team.logo} alt="" width={size} height={size} loading="lazy" />
    : <span className="logo" style={{ width: size, height: size }} />;
}

export function Scorer({ s, showTeam = true }) {
  return (
    <li className="scorer">
      {s.headshot ? <img className="face" src={s.headshot} alt="" width="32" height="32" loading="lazy" /> : <span className="face" />}
      <div className="scorer-id">
        <span className="scorer-name">{s.name}</span>
        <span className="scorer-sub">
          {showTeam ? `${s.team}, ` : ''}{s.position}, {s.season_tds} TD cette saison
          {s.status && <em className="tag">{statusFr[s.status] || s.status}</em>}
        </span>
      </div>
      <div className="scorer-prob">
        <b>{pct(s.prob)}</b>
        <span className="meter"><span style={{ width: `${s.prob}%` }} /></span>
      </div>
    </li>
  );
}

export function Sparkline({ values, color = 'currentColor', width = 72, height = 22 }) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) =>
    `${(i / (values.length - 1)) * (width - 4) + 2},${height - 2 - ((v - min) / span) * (height - 4)}`).join(' ');
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function ProbBar({ g }) {
  return (
    <div className="field" role="img" aria-label={`${g.away.nick} ${Math.round(g.prob_away_win)} %, ${g.home.nick} ${Math.round(g.prob_home_win)} %`}>
      <span style={{ width: `${g.prob_away_win}%`, background: g.away.color }} />
      <span style={{ width: `${g.prob_home_win}%`, background: g.home.color }} />
    </div>
  );
}
