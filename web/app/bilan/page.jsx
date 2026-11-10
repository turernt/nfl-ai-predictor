import data from '../../data/predictions.json';
import { Topbar, Footer } from '../ui';
import { num, pct } from '../lib';

export const metadata = { title: 'Bilan des pronostics' };

const rate = (a, b) => (b ? `${num((a / b) * 100)}\u00a0%` : '—');

export default function Bilan() {
  const { season, bilan, tracking: tr } = data;
  const s = bilan.summary;
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
              Chaque match passé a été prédit avec les seules informations disponibles avant la semaine concernée,
              exactement comme les pronostics de cette semaine.
            </p>
          </div>
        </header>

        <section className="stats">
          <div className="stat main">
            <span className="stat-label">Bon vainqueur</span>
            <span className="stat-big">{rate(s.correct, s.games)}</span>
            <span className="stat-sub">{s.correct} sur {s.games} matchs</span>
          </div>
          <div className="stat">
            <span className="stat-label">Notre modèle seul</span>
            <span className="stat-big">{rate(s.model_correct, s.games)}</span>
            <span className="stat-sub">{s.model_correct} sur {s.games}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Modèle contre l’écart</span>
            <span className="stat-big">{rate(s.ats_correct, s.ats_games)}</span>
            <span className="stat-sub">{s.ats_correct} sur {s.ats_games} (52,4 % requis)</span>
          </div>
          <div className="stat">
            <span className="stat-label">Buteurs mis en avant</span>
            <span className="stat-big">{rate(s.scorer_hits, s.scorer_picks)}</span>
            <span className="stat-sub">{s.scorer_hits} ont marqué, {num(s.scorer_expected, 0)} attendus</span>
          </div>
        </section>
        {tr && (
          <section className="panel">
            <h2>Pronostics publiés, en conditions réelles</h2>
            <p className="lede">
              Depuis le {new Date(tr.since).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).replace(/^1 /, '1er ')}, chaque
              pronostic est enregistré au moment où il apparaît sur le site, puis comparé au résultat : aucun recalcul après coup.
            </p>
            <div className="stats">
              <div className="stat main"><span className="stat-label">Bons vainqueurs</span>
                <span className="stat-big">{tr.settled ? rate(tr.correct, tr.settled) : '—'}</span>
                <span className="stat-sub">{tr.correct} sur {tr.settled} matchs joués ({tr.published} publiés)</span></div>
              <div className="stat"><span className="stat-label">Favoris à 70 % ou plus</span>
                <span className="stat-big">{tr.safe.n ? rate(tr.safe.correct, tr.safe.n) : '—'}</span>
                <span className="stat-sub">{tr.safe.correct} sur {tr.safe.n}</span></div>
              <div className="stat"><span className="stat-label">Valeur de clôture (CLV)</span>
                <span className="stat-big">{tr.clv_avg != null && (tr.settled || tr.clv_avg !== 0) ? `${tr.clv_avg >= 0 ? '+' : '−'}${num(Math.abs(tr.clv_avg), 2)}` : '—'}</span>
                <span className="stat-sub">{tr.settled || tr.clv_avg !== 0 ? `point de probabilité en moyenne (${tr.clv_pos} sur ${tr.clv_n} en hausse)` : 'en attente des premiers matchs'}</span></div>
            </div>
            <p className="fine">
              La valeur de clôture compare la probabilité au moment de la publication et juste avant le match. Positive,
              elle signifie que le marché a ensuite évolué dans le sens du pronostic : c’est le meilleur indicateur de
              qualité à long terme, bien plus fiable que quelques semaines de résultats.
            </p>
            {tr.recent?.length > 0 && (
              <ul className="results">
                {tr.recent.map((e) => (
                  <li key={`${e.week}${e.home}`} className={e.result === 'V' ? 'ok' : e.result === 'D' ? 'ko' : ''}>
                    <span className="res-mark">{e.result === 'V' ? '✓' : e.result === 'D' ? '✗' : '='}</span>
                    <span className="res-game"><span className="res-line">{e.away} {e.score?.split('-')[0]}, {e.home} {e.score?.split('-')[1]}</span>
                      <span className="res-sub">Semaine {e.week}, pronostic {e.pick} à {pct(e.open_prob)} (clôture {pct(e.close_prob)})</span></span>
                    <span />
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {s.units_all?.bets > 0 && (
          <section className="panel">
            <h2>Et si vous aviez parié ?</h2>
            <p className="lede">Mise de 1 € sur chaque pronostic, aux vraies cotes des bookmakers (marge comprise).</p>
            <div className="stats">
              {[['Tous les favoris', s.units_all], ['Favoris à 70 % ou plus', s.units_safe]].map(([label, u]) => (
                <div key={label} className="stat">
                  <span className="stat-label">{label}</span>
                  <span className={`stat-big ${u.units >= 0 ? 'pos' : 'neg'}`}>{u.units >= 0 ? '+' : '−'}{num(Math.abs(u.units), 2)}&nbsp;€</span>
                  <span className="stat-sub">{u.bets} paris, rendement {u.roi >= 0 ? '+' : '−'}{num(Math.abs(u.roi))}&nbsp;%</span>
                </div>
              ))}
            </div>
            <p className="fine">
              Trouver le bon vainqueur ne suffit pas : les favoris paient peu et la marge du bookmaker fait perdre de l’argent
              sur la durée. Seules les cotes supérieures au juste prix (onglet Pronostics) peuvent être rentables. Ces résultats portent sur un petit nombre de paris : ils sont trop peu nombreux pour en tirer une conclusion et ne garantissent aucun gain futur.
            </p>
          </section>
        )}

        <p className="fine">
          Le pronostic retenu suit les cotes des bookmakers. Score de Brier (plus bas = probabilités plus justes) : {s.brier != null ? num(s.brier, 3) : '—'} pour le pronostic,
          {' '}{s.model_brier != null ? num(s.model_brier, 3) : '—'} pour le modèle seul. Un pronostic à pile ou face donnerait 0,250.
        </p>

        <section className="panel">
          <h2>Semaine par semaine</h2>
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
          <section key={wk} className="panel">
            <h2>Semaine {wk}</h2>
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
          </section>
        ))}
      </main>
      <Footer />
    </>
  );
}
