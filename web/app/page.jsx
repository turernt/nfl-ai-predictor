import Link from 'next/link';
import data from '../data/predictions.json';
import GamesBoard from './GamesBoard';
import { Topbar, Footer, Sparkline } from './ui';
import { num, pct } from './lib';

export default function Home() {
  const { season, week, predictions, ranking, season_record: rec, generated_at, top_scorers = [], bilan } = data;
  const updated = new Date(generated_at).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Paris',
  });
  const weeks = bilan?.summary?.weeks || [];
  const last = weeks[weeks.length - 1];
  const lastGames = last ? bilan.games.filter((b) => b.week === last.week) : [];

  return (
    <>
      <Topbar current="Matchs" />
      <main className="wrap">
        <header className="hero">
          <div>
            <h1>Prédictions NFL, {(data.week_label || `semaine ${week}`).toLowerCase().replace(/^super bowl$/, 'Super Bowl')}</h1>
            <p>
              Saison {season}. Probabilités de victoire tirées des cotes (les plus fiables sur 3 900 matchs),
              second avis de notre modèle (Elo, efficacité par jeu, quarterback, repos), scores projetés et buteurs probables.
              {' '}<Link href="/pronostics">Voir les pronostics les plus sûrs</Link>.
            </p>
          </div>
          {last && (
            <Link className="recap" href="/bilan">
              <span className="recap-label">Semaine {last.week}</span>
              <span className="recap-big">{last.correct}<small>/{last.games}</small></span>
              <span className="recap-dots" aria-hidden="true">
                {lastGames.map((b) => <i key={b.game_id} className={b.correct ? 'ok' : b.correct === false ? 'ko' : ''} />)}
              </span>
              <span className="recap-sub">
                Saison : {rec.correct} sur {rec.games} ({num(rec.accuracy)}&nbsp;%). Voir le bilan
              </span>
            </Link>
          )}
        </header>

        <section id="matchs" aria-label="Matchs de la semaine">
          {predictions.length === 0
            ? <div className="empty">Aucun match à venir pour l’instant. Les prédictions reviennent dès la publication du prochain calendrier.</div>
            : <GamesBoard games={predictions} />}
        </section>

        {top_scorers.length > 0 && (
          <section id="buteurs" className="block">
            <h2>Meilleures chances de touchdown</h2>
            <p className="lede">Probabilité de marquer au moins un touchdown à la course ou à la réception cette semaine.</p>
            <ol className="board">
              {top_scorers.map((s, i) => (
                <li key={s.player_id || s.name}>
                  <span className="rk">{i + 1}</span>
                  {s.headshot ? <img className="face" src={s.headshot} alt="" width="32" height="32" loading="lazy" /> : <span className="face" />}
                  <div className="scorer-id">
                    <span className="scorer-name">{s.name}</span>
                    <span className="scorer-sub">{s.team} contre {s.opponent}, {s.position}</span>
                  </div>
                  <b className="big-prob">{pct(s.prob)}</b>
                </li>
              ))}
            </ol>
          </section>
        )}

        <section id="classement" className="block">
          <h2>Classement de force</h2>
          <p className="lede">
            Points d’avance attendus face à une équipe moyenne sur terrain neutre, calculés à partir de toutes les cotes
            de la saison et de notre modèle. La courbe montre l’évolution de l’Elo depuis la semaine 1.
          </p>
          <ol className="elo">
            {ranking.map((t, i) => (
              <li key={t.abbr}>
                <span className="rk">{i + 1}</span>
                {t.logo ? <img className="mini-logo" src={t.logo} alt="" width="22" height="22" loading="lazy" /> : <span className="mini-logo" />}
                <span className="elo-name"><Link href={`/equipe/${t.abbr}`}>{t.nick}</Link><span className="team-sub"> {t.record}</span></span>
                <Sparkline values={t.history} color={t.history?.at(-1) >= t.history?.[0] ? 'var(--accent)' : 'var(--down)'} />
                <b>{t.power != null ? `${t.power >= 0 ? '+' : '−'}${num(Math.abs(t.power))}` : Math.round(t.elo)}</b>
              </li>
            ))}
          </ol>
        </section>
      </main>
      <Footer updated={updated} />
    </>
  );
}
