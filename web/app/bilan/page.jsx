import data from '../../data/predictions.json';
import { Topbar, Footer } from '../ui';
import { num, pct } from '../lib';

export const metadata = { title: 'Bilan des pronostics' };

const rate = (a, b) => (b ? `${num((a / b) * 100)}\u00a0%` : '—');
const signed = (x, d = 1, unit = '') => (x == null ? '—' : `${x >= 0 ? '+' : '−'}${num(Math.abs(x), d)}${unit}`);

function RealTracking({ tr }) {
  const sc = tr.scorers || {};
  const v = tr.value || {};
  const since = new Date(tr.since).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).replace(/^1 /, '1er ');
  return (
    <section className="panel">
      <h2>Pronostics publiés, en conditions réelles</h2>
      <p className="lede">
        Depuis le {since}, chaque pronostic est enregistré tel qu’il apparaît sur le site, figé au coup d’envoi puis
        comparé au résultat : aucun recalcul après coup. C’est le seul bilan qui compte.
      </p>
      <div className="stats">
        <div className="stat main"><span className="stat-label">Bons vainqueurs</span>
          <span className="stat-big">{rate(tr.correct, tr.settled)}</span>
          <span className="stat-sub">{tr.correct} sur {tr.settled} matchs joués ({tr.published} publiés)</span></div>
        <div className="stat"><span className="stat-label">Favoris à 70 % ou plus</span>
          <span className="stat-big">{rate(tr.safe.correct, tr.safe.n)}</span>
          <span className="stat-sub">{tr.safe.correct} sur {tr.safe.n}</span></div>
        <div className="stat"><span className="stat-label">Score de Brier</span>
          <span className="stat-big">{tr.brier != null ? num(tr.brier, 3) : '—'}</span>
          <span className="stat-sub">plus bas = probabilités plus justes (pile ou face : 0,250)</span></div>
        <div className="stat"><span className="stat-label">Buteurs affichés</span>
          <span className="stat-big">{sc.n ? `${sc.hits}` : '—'}</span>
          <span className="stat-sub">{sc.n ? `ont marqué sur ${sc.n}, pour ${num(sc.expected, 0)} attendus` : 'en attente des premiers matchs'}</span></div>
      </div>

      {sc.n > 0 && (
        <table className="compare rel">
          <thead><tr><th>Buteurs (suivi réel)</th><th>Cas</th><th>Annoncé</th><th>Réel</th></tr></thead>
          <tbody>
            {sc.tiers.filter((t) => t.n).map((t) => (
              <tr key={t.label}><th scope="row">{t.label}</th><td>{t.n}</td><td>{num(t.predicted)}&nbsp;%</td><td><b>{num(t.actual)}&nbsp;%</b></td></tr>
            ))}
            {sc.top_n > 0 && (
              <tr><th scope="row">Buteur n°1 de chaque match</th><td>{sc.top_n}</td><td>—</td><td><b>{rate(sc.top_hits, sc.top_n)}</b></td></tr>
            )}
          </tbody>
        </table>
      )}

      {tr.wind_totals?.n > 0 && (
        <p className="fine">
          Matchs venteux (19 km/h ou plus prévus au coup d’envoi) : le total est passé sous la ligne dans {tr.wind_totals.under} cas
          sur {tr.wind_totals.n} ({num((tr.wind_totals.under / tr.wind_totals.n) * 100)}&nbsp;%).
        </p>
      )}

      <h3 className="col-title sub-title">Cotes françaises signalées au-dessus du juste prix</h3>
      {v.n ? (
        <>
          <div className="stats">
            <div className="stat"><span className="stat-label">Valeur de clôture moyenne</span>
              <span className={`stat-big ${v.clv_avg >= 0 ? 'pos' : 'neg'}`}>{signed(v.clv_avg, 1, '\u00a0%')}</span>
              <span className="stat-sub">{v.clv_n ? `${v.clv_pos} sur ${v.clv_n} au-dessus de la clôture` : 'en attente des premiers matchs'}</span></div>
            <div className="stat"><span className="stat-label">Résultat à 1 € par cote</span>
              <span className={`stat-big ${v.units >= 0 ? 'pos' : 'neg'}`}>{signed(v.units, 2, '\u00a0€')}</span>
              <span className="stat-sub">{v.won} gagnées sur {v.settled} ({v.n} signalées)</span></div>
          </div>
          <p className="fine">
            La valeur de clôture compare la cote signalée au juste prix juste avant le match (ligne de clôture nflverse,
            marge retirée). Positive en moyenne sur plusieurs dizaines de cotes, elle indique un vrai avantage ; le résultat
            en euros, lui, reste dominé par le hasard sur un petit nombre de paris.
          </p>
        </>
      ) : <p className="lede">Aucune cote signalée pour l’instant.</p>}

      {tr.recent?.length > 0 && (
        <ul className="results">
          {tr.recent.map((e) => (
            <li key={`${e.week}${e.home}`} className={e.result === 'V' ? 'ok' : e.result === 'D' ? 'ko' : ''}>
              <span className="res-mark">{e.result === 'V' ? '✓' : e.result === 'D' ? '✗' : '='}</span>
              <span className="res-game"><span className="res-line">{e.away} {e.score?.split('-')[0]}, {e.home} {e.score?.split('-')[1]}</span>
                <span className="res-sub">Semaine {e.week}, pronostic {e.pick} à {pct(e.close_prob)} au coup d’envoi{e.close_mkt != null ? ` (clôture du marché ${pct(e.close_mkt)})` : ''}</span></span>
              <span className="res-scorers">
                {(e.scorers || []).filter((s) => 'scored' in s).sort((a, b) => b.prob - a.prob).slice(0, 4).map((s) => (
                  <span key={s.name} className={s.scored ? 'hit' : ''}>{s.name} {pct(s.prob)}{s.scored ? ' ✓' : ''}</span>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Bilan() {
  const { season, bilan, tracking: tr, picks } = data;
  const s = bilan.summary;
  const roi = picks?.market_roi;
  const weeks = [...new Set(bilan.games.map((b) => b.week))].sort((a, b) => b - a);
  const maxGames = Math.max(...s.weeks.map((w) => w.games), 1);

  return (
    <>
      <Topbar current="Bilan" />
      <main className="wrap narrow">
        <header className="hero">
          <div>
            <h1>Bilan de la saison {season}</h1>
            <p>
              D’abord les pronostics réellement publiés, puis une simulation rétrospective de toute la saison, utile pour
              comparer les méthodes mais plus flatteuse que la réalité.
            </p>
          </div>
        </header>

        {tr && <RealTracking tr={tr} />}

        <section className="panel">
          <h2>Et si vous aviez parié ?</h2>
          <p className="lede">Mise de 1 € sur chaque favori, aux vraies cotes des bookmakers (marge comprise).</p>
          <div className="stats">
            {roi?.bets > 0 && (
              <div className="stat main">
                <span className="stat-label">Tous les favoris depuis 2012</span>
                <span className={`stat-big ${roi.roi >= 0 ? 'pos' : 'neg'}`}>{signed(roi.roi, 1, '\u00a0%')}</span>
                <span className="stat-sub">rendement sur {roi.bets.toLocaleString('fr-FR')} paris</span>
              </div>
            )}
            {[['Favoris de la saison (simulation)', s.units_all], ['Favoris à 70 % ou plus (simulation)', s.units_safe]].map(([label, u]) => u?.bets > 0 && (
              <div key={label} className="stat">
                <span className="stat-label">{label}</span>
                <span className={`stat-big ${u.units >= 0 ? 'pos' : 'neg'}`}>{signed(u.units, 2, '\u00a0€')}</span>
                <span className="stat-sub">{u.bets} paris, rendement {signed(u.roi, 1, '\u00a0%')}</span>
              </div>
            ))}
          </div>
          <p className="fine">
            Sur la durée, parier chaque favori fait perdre à peu près la marge du bookmaker. Sur une seule saison, le rendement
            varie d’une douzaine de points dans un sens ou dans l’autre : il ne dit rien de la qualité d’une méthode.
          </p>
        </section>

        <section className="panel">
          <h2>Simulation rétrospective</h2>
          <p className="lede">
            Chaque match joué est re-prédit avec les données disponibles avant sa semaine, mais avec la ligne de clôture,
            le quarterback qui a réellement joué et la version actuelle du modèle de buteurs. Elle sert à comparer les
            méthodes, pas à mesurer ce que le site a réellement publié.
          </p>
          <div className="stats">
            <div className="stat"><span className="stat-label">Bon vainqueur (cotes)</span>
              <span className="stat-big">{rate(s.correct, s.games)}</span>
              <span className="stat-sub">{s.correct} sur {s.games}, Brier {s.brier != null ? num(s.brier, 3) : '—'}</span></div>
            <div className="stat"><span className="stat-label">Modèle maison seul</span>
              <span className="stat-big">{rate(s.model_correct, s.games)}</span>
              <span className="stat-sub">{s.model_correct} sur {s.games}, Brier {s.model_brier != null ? num(s.model_brier, 3) : '—'}</span></div>
            <div className="stat"><span className="stat-label">Modèle contre l’écart</span>
              <span className="stat-big">{rate(s.ats_correct, s.ats_games)}</span>
              <span className="stat-sub">{s.ats_correct} sur {s.ats_games} (52,4 % requis)</span></div>
            <div className="stat"><span className="stat-label">Buteurs mis en avant</span>
              <span className="stat-big">{rate(s.scorer_hits, s.scorer_picks)}</span>
              <span className="stat-sub">{s.scorer_hits} ont marqué, {num(s.scorer_expected, 0)} attendus</span></div>
          </div>
          <div className="weekbars">
            {s.weeks.map((w) => (
              <div key={w.week} className="wb">
                <div className="wb-col" style={{ height: `${(w.games / maxGames) * 100}%` }}>
                  <span className="wb-fill" style={{ height: `${(w.correct / w.games) * 100}%` }} />
                </div>
                <span className="wb-val">{w.correct}/{w.games}</span>
                <span className="wb-week">S{w.week}</span>
              </div>
            ))}
          </div>
        </section>

        {weeks.map((wk) => (
          <details key={wk} className="panel week-detail">
            <summary><h2>Semaine {wk}</h2></summary>
            <ul className="results">
              {bilan.games.filter((b) => b.week === wk).map((b) => (
                <li key={b.game_id} className={b.correct ? 'ok' : b.correct === false ? 'ko' : ''}>
                  <span className="res-mark" aria-label={b.correct ? 'Juste' : b.correct === false ? 'Faux' : 'Nul'}>
                    {b.correct ? '✓' : b.correct === false ? '✗' : '='}
                  </span>
                  <span className="res-game">
                    <span className="res-line">{b.away_nick} {b.score.away}, {b.home_nick} {b.score.home}</span>
                    <span className="res-sub">Pronostic : {b.pick} à {pct(b.pick_prob)}</span>
                  </span>
                  <span className="res-scorers">
                    {b.scorers.map((sc) => (
                      <span key={sc.name} className={sc.scored ? 'hit' : ''}>{sc.name} {pct(sc.prob)}{sc.scored ? ' ✓' : ''}</span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </main>
      <Footer />
    </>
  );
}
