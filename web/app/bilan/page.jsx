import data from '../../data/predictions.json';
import { Topbar, Footer } from '../ui';
import { num, pct } from '../lib';

export const metadata = { title: 'Bilan des pronostics' };

const rate = (a, b) => (b ? `${num((a / b) * 100)}\u00a0%` : '—');

export default function Bilan() {
  const { season, bilan } = data;
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
