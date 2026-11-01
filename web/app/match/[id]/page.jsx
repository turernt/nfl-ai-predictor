import Link from 'next/link';
import { notFound } from 'next/navigation';
import data from '../../../data/predictions.json';
import { Topbar, Footer, Logo, Scorer, ProbBar } from '../../ui';
import { kickoff, fmtLong, fmtHour, spreadLabel, edgeLabel, num, pct } from '../../lib';

export function generateStaticParams() {
  return data.predictions.map((g) => ({ id: g.game_id }));
}

export function generateMetadata({ params }) {
  const g = data.predictions.find((x) => x.game_id === params.id);
  if (!g) return {};
  return {
    title: `${g.away.nick} @ ${g.home.nick}, semaine ${g.week}`,
    description: g.commentary,
  };
}

function FactorRow({ label, pts, g, scale, strong }) {
  const w = Math.min(50, (Math.abs(pts) / scale) * 50);
  return (
    <div className={`factor ${strong ? 'strong' : ''}`}>
      <span className="factor-label">{label}</span>
      <div className="factor-bar" aria-hidden="true">
        <span className="axis" />
        {pts < 0 && <span className="fill" style={{ right: '50%', width: `${w}%`, background: g.away.color }} />}
        {pts > 0 && <span className="fill" style={{ left: '50%', width: `${w}%`, background: g.home.color }} />}
      </div>
      <span className="factor-val">{edgeLabel(pts, g.home, g.away)}</span>
    </div>
  );
}

function EloChart({ home, away, weeks }) {
  const W = 560, H = 180, P = 28;
  const all = [...home.history, ...away.history];
  const min = Math.min(...all) - 10, max = Math.max(...all) + 10;
  const x = (i, n) => P + (i / (n - 1)) * (W - 2 * P);
  const y = (v) => H - P - ((v - min) / (max - min)) * (H - 2 * P);
  const line = (vals) => vals.map((v, i) => `${x(i, vals.length)},${y(v)}`).join(' ');
  return (
    <svg className="elo-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Évolution de l’Elo des deux équipes">
      <line x1={P} x2={W - P} y1={y(1505)} y2={y(1505)} className="ref" />
      <text x={P} y={y(1505) - 6} className="ref-label">Moyenne 1 505</text>
      {[away, home].map((t) => (
        <g key={t.abbr}>
          <polyline points={line(t.history)} fill="none" stroke={t.color} strokeWidth="2.5" strokeLinejoin="round" />
          <circle cx={x(t.history.length - 1, t.history.length)} cy={y(t.history.at(-1))} r="4" fill={t.color} />
          <text x={x(t.history.length - 1, t.history.length) - 8} y={y(t.history.at(-1)) - 8} textAnchor="end" className="pt-label">
            {t.abbr} {Math.round(t.history.at(-1))}
          </text>
        </g>
      ))}
      {weeks.map((wk, i) => (
        <text key={i} x={x(i, weeks.length)} y={H - 6} textAnchor="middle" className="axis-label">{wk}</text>
      ))}
    </svg>
  );
}

export default function MatchPage({ params }) {
  const g = data.predictions.find((x) => x.game_id === params.id);
  if (!g) notFound();
  const date = kickoff(g.gameday, g.gametime);
  const f = g.factors;
  const ew = data.model.elo_weight;
  const rows = [
    ['Force Elo', f.elo * ew],
    ['Efficacité par jeu (EPA)', f.epa * (1 - ew)],
    ['Quarterbacks annoncés', f.qb.home - f.qb.away],
    ['Repos', f.rest.pts],
  ];
  const model = -g.model_spread;
  const market = g.vegas_spread != null ? -g.vegas_spread : null;
  const final = -g.predicted_spread;
  const scale = Math.max(7, ...[...rows.map((r) => r[1]), model, market ?? 0, final].map(Math.abs));
  const hist = Object.fromEntries(data.ranking.map((t) => [t.abbr, t]));
  const hHome = hist[g.home.abbr], hAway = hist[g.away.abbr];
  const nWeeks = hHome?.history?.length || 0;
  const weekLabels = Array.from({ length: nWeeks }, (_, i) => (i === nWeeks - 1 ? 'Auj.' : `S${i + 1}`));
  const proj = g.projected_score || {};
  const byTeam = (abbr) => g.scorers.filter((s) => s.team === abbr);

  const compare = [
    ['Bilan', g.away.record, g.home.record],
    ['Elo', Math.round(g.away.elo), Math.round(g.home.elo)],
    ['Attaque (rang EPA)', g.away.off_rank ? `${g.away.off_rank}e` : '—', g.home.off_rank ? `${g.home.off_rank}e` : '—'],
    ['Défense (rang EPA)', g.away.def_rank ? `${g.away.def_rank}e` : '—', g.home.def_rank ? `${g.home.def_rank}e` : '—'],
    ['QB annoncé', f.qb.away_name || '—', f.qb.home_name || '—'],
    ['Jours de repos', f.rest.away_days ?? '—', f.rest.home_days ?? '—'],
  ];

  return (
    <>
      <Topbar />
      <main className="wrap narrow">
        <Link className="back" href="/">Tous les matchs</Link>

        <header className="scoreboard">
          <p className="sb-date">Semaine {g.week}, {date ? `${fmtLong(date)}, ${fmtHour(date)}` : 'date à confirmer'}</p>
          <div className="sb-teams">
            {[[g.away, g.prob_away_win, proj.away], [g.home, g.prob_home_win, proj.home]].map(([t, p, sc], i) => (
              <div key={t.abbr} className={`sb-team ${i ? 'home' : ''} ${p >= 50 ? 'is-fav' : ''}`}>
                <Logo team={t} size={64} />
                <span className="sb-name">{t.name}</span>
                <span className="team-sub">{t.record}{i ? ', à domicile' : ''}</span>
                <span className="sb-score">{sc ?? '—'}</span>
                <span className="sb-win">{pct(p)}</span>
              </div>
            ))}
          </div>
          <ProbBar g={g} />
          <p className="sb-note">{g.commentary}</p>
        </header>

        <section className="panel">
          <h2>Comment on arrive à ce pronostic</h2>
          <p className="lede">Chaque facteur est exprimé en points d’avance au score pour l’une des deux équipes.</p>
          <div className="factors">
            <div className="factor-head"><span /><span className="fh-teams"><span>{g.away.abbr}</span><span>{g.home.abbr}</span></span><span /></div>
            {rows.map(([l, v]) => <FactorRow key={l} label={l} pts={v} g={g} scale={scale} />)}
            <FactorRow label="Modèle maison" pts={model} g={g} scale={scale} strong />
            {market != null && <FactorRow label="Bookmakers" pts={market} g={g} scale={scale} strong />}
            <FactorRow label={market != null ? 'Pronostic final' : 'Pronostic final (sans ligne)'} pts={final} g={g} scale={scale} strong />
          </div>
          <p className="fine">
            Le pronostic final combine les bookmakers (deux tiers), qui intègrent des informations de dernière minute,
            et notre modèle (un tiers), qui apporte une lecture indépendante. Spread final : {spreadLabel(g.predicted_spread, g.home, g.away)},
            total : {g.vegas_total != null ? num(g.vegas_total) : '—'}.
          </p>
        </section>

        <section className="panel">
          <h2>Face à face</h2>
          <table className="compare">
            <thead><tr><th /><th>{g.away.nick}</th><th>{g.home.nick}</th></tr></thead>
            <tbody>{compare.map(([l, a, h]) => <tr key={l}><th scope="row">{l}</th><td>{a}</td><td>{h}</td></tr>)}</tbody>
          </table>
          {hHome && hAway && <EloChart home={hHome} away={hAway} weeks={weekLabels} />}
        </section>

        <section className="panel">
          <h2>Buteurs probables</h2>
          <p className="lede">Probabilité de marquer au moins un touchdown à la course ou à la réception.</p>
          <div className="two-col">
            {[g.away, g.home].map((t) => (
              <div key={t.abbr}>
                <h3 className="col-title"><Logo team={t} size={22} />{t.nick}</h3>
                <ul className="plain">{byTeam(t.abbr).map((s) => <Scorer key={s.player_id || s.name} s={s} showTeam={false} />)}</ul>
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
