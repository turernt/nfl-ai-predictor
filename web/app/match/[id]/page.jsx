import Link from 'next/link';
import { notFound } from 'next/navigation';
import data from '../../../data/predictions.json';
import archive from '../../../data/archive.json';
import { Topbar, Footer, Logo, Scorer, Lineup, ProbBar, tc } from '../../ui';
import { kickoff, fmtLong, fmtHour, spreadLabel, edgeLabel, num, pct, fr1, windNote } from '../../lib';

// Matchs de la semaine (version complète) puis tous les matchs archivés de la saison (figés au coup d’envoi)
const findGame = (id) => data.predictions.find((x) => x.game_id === id) || archive[id];

export function generateStaticParams() {
  const ids = new Set([...data.predictions.map((g) => g.game_id), ...Object.keys(archive)]);
  return [...ids].map((id) => ({ id }));
}

export function generateMetadata({ params }) {
  const g = findGame(params.id);
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
        {pts < 0 && <span className="fill tc" style={{ right: '50%', width: `${w}%`, ...tc(g.away) }} />}
        {pts > 0 && <span className="fill tc" style={{ left: '50%', width: `${w}%`, ...tc(g.home) }} />}
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
        <g key={t.abbr} className="tcs" style={tc(t)}>
          <polyline points={line(t.history)} fill="none" strokeWidth="2.5" strokeLinejoin="round" />
          <circle cx={x(t.history.length - 1, t.history.length)} cy={y(t.history.at(-1))} r="4" />
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
  const g = findGame(params.id);
  if (!g) notFound();
  const isFinal = g.status === 'final';
  const frozen = g.status === 'final' || g.status === 'live';
  const noInjuryReport = !g.injuries || (!g.injuries.home?.length && !g.injuries.away?.length);
  const date = kickoff(g.gameday, g.gametime);
  const f = g.factors;
  const ew = data.model.elo_weight;
  const rows = [
    ['Force Elo', f.elo * ew],
    ['Efficacité par jeu (EPA)', f.epa * (1 - ew)],
    ['Quarterbacks attendus', f.qb.home - f.qb.away],
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
  const proj = (isFinal ? g.score : g.projected_score) || {};
  const byTeam = (abbr) => g.scorers.filter((s) => s.team === abbr);

  const compare = [
    ['Bilan', g.away.record, g.home.record],
    ['Elo', Math.round(g.away.elo), Math.round(g.home.elo)],
    ['Attaque (rang EPA)', g.away.off_rank ? `${g.away.off_rank}e` : '—', g.home.off_rank ? `${g.home.off_rank}e` : '—'],
    ['Défense (rang EPA)', g.away.def_rank ? `${g.away.def_rank}e` : '—', g.home.def_rank ? `${g.home.def_rank}e` : '—'],
    ['QB attendu', f.qb.away_name || '—', f.qb.home_name || '—'],
    ['Jours de repos', f.rest.away_days ?? '—', f.rest.home_days ?? '—'],
  ];

  return (
    <>
      <Topbar />
      <main className="wrap narrow">
        <Link className="back" href="/">Tous les matchs</Link>

        <header className="scoreboard">
          <p className="sb-date">Semaine {g.week}, {date ? `${fmtLong(date)}, ${fmtHour(date)}` : 'date à confirmer'}</p>
          {frozen && (
            <p className="notice">
              {isFinal ? 'Match terminé, score final ci-dessous. ' : 'Match en cours. '}
              Analyse figée telle qu’elle était publiée avant le coup d’envoi
              {g.unpublished ? ' (recalculée après coup : aucune version n’avait été publiée)' : ''}.
              {isFinal && g.pick_correct != null && <b className={g.pick_correct ? 'res-ok' : 'res-ko'}> Pronostic {g.pick_correct ? 'juste' : 'faux'}.</b>}
            </p>
          )}
          <div className="sb-teams">
            {[[g.away, g.prob_away_win, proj.away], [g.home, g.prob_home_win, proj.home]].map(([t, p, sc], i) => (
              <div key={t.abbr} className={`sb-team ${i ? 'home' : ''} ${p >= 50 ? 'is-fav' : ''}`}>
                <Logo team={t} size={64} />
                <Link className="sb-name" href={`/equipe/${t.abbr}`}>{t.name}</Link>
                <span className="team-sub">{t.record}{i ? ', à domicile' : ''}</span>
                <span className="sb-score">{sc ?? '—'}</span>
                <span className="sb-win">{pct(p)}</span>
              </div>
            ))}
          </div>
          <ProbBar g={g} />
          <p className="sb-note">{g.commentary}</p>
          {g.line_history?.length > 1 && (() => {
            const h = g.line_history, a = h[0], z = h[h.length - 1];
            const d = (x) => new Date(x).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
            const diff = z.prob_home - a.prob_home;
            return (
              <p className="move">
                Mouvement du marché depuis le {d(a.date)} : {g.home.nick} {pct(a.prob_home)} → {pct(z.prob_home)}
                {Math.abs(diff) >= 0.5 ? ` (${diff > 0 ? '+' : '−'}${num(Math.abs(diff))} pt)` : ' (stable)'}
                {a.spread != null && z.spread != null && a.spread !== z.spread ? `, écart ${spreadLabel(a.spread, g.home, g.away)} → ${spreadLabel(z.spread, g.home, g.away)}` : ''}
              </p>
            );
          })()}
        </header>

        <section className="panel">
          <h2>Ce que dit notre modèle</h2>
          <p className="lede">Chaque facteur est exprimé en points d’avance au score pour l’une des deux équipes.</p>
          <div className="factors">
            <div className="factor-head"><span /><span className="fh-teams"><span>{g.away.abbr}</span><span>{g.home.abbr}</span></span><span /></div>
            {rows.map(([l, v]) => <FactorRow key={l} label={l} pts={v} g={g} scale={scale} />)}
            <FactorRow label="Modèle maison" pts={model} g={g} scale={scale} strong />
            {market != null
              ? <FactorRow label="Bookmakers (pronostic retenu)" pts={market} g={g} scale={scale} strong />
              : <FactorRow label="Pronostic retenu" pts={final} g={g} scale={scale} strong />}
          </div>
          <p className="fine">
            La probabilité affichée vient des cotes des bookmakers, marge retirée : bien calibrées sur 3 950 matchs depuis 2012,
            et jamais battues par notre modèle ni par un mélange des deux. Notre modèle sert de second avis :
            quand il contredit les cotes, c’est un signal de prudence. Spread retenu : {spreadLabel(g.predicted_spread, g.home, g.away)},
            total : {g.vegas_total != null ? num(g.vegas_total) : '—'}.
          </p>
        </section>

        {(g.weather || g.injuries) && (
          <section className="panel">
            <h2>Avant le match</h2>
            {g.weather && (
              <p className="wx">
                {g.weather.roof === 'dome' ? 'Stade couvert : la météo ne joue pas.'
                  : g.weather.error ? 'Météo momentanément indisponible.'
                  : g.weather.pending ? 'Prévisions météo disponibles 7 jours avant le match.'
                  : <>Météo prévue au coup d’envoi : <b>{g.weather.temp_c}&nbsp;°C</b>, vent <b>{g.weather.wind_kmh}&nbsp;km/h</b>
                      {g.weather.precip_prob != null ? <>, risque de pluie {g.weather.precip_prob}&nbsp;%</> : null}
                      {g.weather.roof === 'retractable' ? ' (toit rétractable, souvent fermé)' : ''}.</>}
                {g.weather.windy && (() => {
                  const wn = windNote(data.studies);
                  return wn && (
                    <span className="warn">
                      {' '}Vent fort : depuis 2012, le total est passé sous la ligne dans {fr1(wn.observed.under)}&nbsp;% de ces matchs ({wn.observed.n} matchs).
                      {wn.validated ? ` Signal retenu : moins de ${g.vegas_total != null ? num(g.vegas_total) : '—'} points.` : ' Effet suivi, pas encore assez net pour un pronostic.'}
                    </span>
                  );
                })()}
              </p>
            )}
            {g.injuries && noInjuryReport && (
              <p className="team-sub">Rapport de blessures pas encore publié pour cette semaine (il paraît du mercredi au vendredi).</p>
            )}
            {g.injuries && !noInjuryReport && (
              <div className="two-col">
                {[g.away, g.home].map((t) => {
                  const list = (t.abbr === g.home.abbr ? g.injuries.home : g.injuries.away) || [];
                  return (
                    <div key={t.abbr}>
                      <h3 className="col-title"><Logo team={t} size={22} />Blessés {t.nick}</h3>
                      {list.length ? (
                        <ul className="inj">
                          {list.map((x) => (
                            <li key={x.name}>
                              <span className={`st st-${x.status}`}>{{ Out: 'Forfait', Doubtful: 'Douteux', Questionable: 'Incertain' }[x.status]}</span>
                              <span>{x.name} <span className="team-sub">{x.position}{x.injury ? `, ${x.injury}` : ''}</span></span>
                            </li>
                          ))}
                        </ul>
                      ) : <p className="team-sub">Aucun joueur signalé.</p>}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {g.odds && (
          <section className="panel">
            <h2>Cotes des bookmakers</h2>
            <p className="lede">
              {g.odds.n_books} bookmakers. Cote juste (sans marge) : {g.away.nick} {num(g.odds.fair_away, 2)}, {g.home.nick} {num(g.odds.fair_home, 2)}.
              En vert, les cotes supérieures au juste prix.
            </p>
            <div className="table-scroll">
              <table className="compare odds">
                <thead><tr><th>Bookmaker</th><th>{g.away.abbr}</th><th>{g.home.abbr}</th><th>Marge</th></tr></thead>
                <tbody>
                  {g.odds.books.map((b) => (
                    <tr key={b.key}>
                      <th scope="row">{b.title}</th>
                      <td className={b.away > g.odds.fair_away ? 'val' : ''}>{num(b.away, 2)}</td>
                      <td className={b.home > g.odds.fair_home ? 'val' : ''}>{num(b.home, 2)}</td>
                      <td>{num(b.margin)}&nbsp;%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <section className="panel">
          <h2>Face à face</h2>
          <table className="compare">
            <thead><tr><th /><th>{g.away.nick}</th><th>{g.home.nick}</th></tr></thead>
            <tbody>{compare.map(([l, a, h]) => <tr key={l}><th scope="row">{l}</th><td>{a}</td><td>{h}</td></tr>)}</tbody>
          </table>
          {hHome && hAway && <EloChart home={hHome} away={hAway} weeks={weekLabels} />}
        </section>

        {g.lineup && (g.lineup.home?.length > 0 || g.lineup.away?.length > 0) && (
          <section className="panel">
            <h2>Composition probable</h2>
            <p className="lede">
              Titulaires attendus en attaque, d’après la hiérarchie des postes, l’effectif actif et le rapport de blessures.
              Un joueur forfait est remplacé par le suivant dans la hiérarchie.
            </p>
            <div className="two-col">
              {[g.away, g.home].map((t) => (
                <div key={t.abbr}>
                  <h3 className="col-title"><Logo team={t} size={22} />{t.nick}</h3>
                  <Lineup players={t.abbr === g.home.abbr ? g.lineup.home : g.lineup.away} />
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="panel">
          <h2>Buteurs probables</h2>
          <p className="lede">
            Probabilité de marquer au moins un touchdown à la course ou à la réception, calculée sur les matchs précédents
            de chaque joueur (ballons reçus près de l’en-but, temps de jeu, touchdowns), la composition du jour et le score
            attendu. Les points verts indiquent les matchs où le joueur a marqué.
          </p>
          <div className="two-col">
            {[g.away, g.home].map((t) => (
              <div key={t.abbr}>
                <h3 className="col-title"><Logo team={t} size={22} />{t.nick}</h3>
                <ul className="plain">{byTeam(t.abbr).map((s) => <Scorer key={s.player_id || s.name} s={s} showTeam={false} detail />)}</ul>
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
