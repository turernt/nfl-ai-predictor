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
  const links = [['/', 'Matchs'], ['/pronostics', 'Pronostics'], ['/saison', 'Playoffs'], ['/bilan', 'Bilan']];
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
      <span>
        Prédictions statistiques à titre informatif, pas des conseils de pari. Jouer comporte des risques : 09 74 75 13 13.
        {' '}<Link href="/mentions-legales">Mentions légales</Link>
      </span>
    </footer>
  );
}

export function Logo({ team, size = 36 }) {
  return team.logo
    ? <img className="logo" src={team.logo} alt="" width={size} height={size} loading="lazy" />
    : <span className="logo" style={{ width: size, height: size }} />;
}

// Derniers matchs d’un joueur : un point par match, plein s’il a marqué
export function FormDots({ form }) {
  if (!form?.length) return null;
  const hits = form.filter((f) => f.td > 0).length;
  return (
    <span className="form" title={`A marqué dans ${hits} de ses ${form.length} derniers matchs`}>
      {form.map((f) => <i key={f.week} className={f.td > 0 ? 'td' : ''} />)}
      <span>{hits}/{form.length}</span>
    </span>
  );
}

export function Scorer({ s, showTeam = true, detail = false }) {
  const form = s.form || [];
  return (
    <li className="scorer">
      {s.headshot ? <img className="face" src={s.headshot} alt="" width="32" height="32" loading="lazy" /> : <span className="face" />}
      <div className="scorer-id">
        <span className="scorer-name">{s.name}</span>
        <span className="scorer-sub">
          {showTeam ? `${s.team}, ` : ''}{s.depth || s.position}, {s.season_tds} TD cette saison
          {s.status && <em className="tag">{statusFr[s.status] || s.status}</em>}
        </span>
        {!detail && <FormDots form={form} />}
      </div>
      <div className="scorer-prob">
        <b>{pct(s.prob)}</b>
        <span className="meter"><span style={{ width: `${s.prob}%` }} /></span>
      </div>
      {detail && form.length > 0 && (
        <details className="scorer-more">
          <summary>
            <FormDots form={form} /> derniers matchs{s.snap != null ? `, ${s.snap}\u00a0% des actions jouées` : ''}
          </summary>
          <table className="log">
            <thead><tr><th>Match</th><th>Courses</th><th>Cibles</th><th>Yards</th><th>TD</th><th>Temps de jeu</th></tr></thead>
            <tbody>
              {form.map((f) => (
                <tr key={f.week} className={f.td > 0 ? 'hit' : ''}>
                  <td>S{f.week} {f.opp}</td><td>{f.car}</td><td>{f.tgt}</td><td>{f.yds}</td><td>{f.td}</td>
                  <td>{f.snap != null ? `${f.snap}\u00a0%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </li>
  );
}

// Composition probable : hiérarchie des postes croisée avec l’effectif actif et le rapport de blessures
const POS_FR = { QB: 'Quarterback', RB: 'Coureurs', WR: 'Receveurs', TE: 'Tight end' };
export function Lineup({ players }) {
  if (!players?.length) return <p className="team-sub">Composition indisponible.</p>;
  return (
    <ul className="lineup">
      {players.map((x) => (
        <li key={x.player_id} className={x.available ? '' : 'off'}>
          <span className="pos" title={POS_FR[x.pos]}>{x.pos}{x.rank}</span>
          <span className="lu-name">{x.name}</span>
          {x.status && <span className={`st st-${x.status}`}>{{ Out: 'Forfait', Doubtful: 'Douteux', Questionable: 'Incertain' }[x.status]}</span>}
        </li>
      ))}
    </ul>
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

// Couleurs d’équipe : la variante claire est utilisée en mode sombre (voir .tc dans globals.css)
export const tc = (t) => ({ '--team': t.color, '--team-dark': t.color_dark || t.color });

export function ProbBar({ g }) {
  return (
    <div className="field" role="img" aria-label={`${g.away.nick} ${Math.round(g.prob_away_win)} %, ${g.home.nick} ${Math.round(g.prob_home_win)} %`}>
      <span className="tc" style={{ width: `${g.prob_away_win}%`, ...tc(g.away) }} />
      <span className="tc" style={{ width: `${g.prob_home_win}%`, ...tc(g.home) }} />
    </div>
  );
}
