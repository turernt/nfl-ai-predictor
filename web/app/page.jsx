import data from '../data/predictions.json';

const num = (n, d = 1) => n.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d });

// Les horaires nflverse sont en heure de New York : on les convertit en heure de Paris.
function kickoff(day, time) {
  if (!day) return null;
  const [y, m, d] = day.split('-').map(Number);
  const [h, mi] = (time || '13:00').split(':').map(Number);
  const guess = Date.UTC(y, m - 1, d, h, mi);
  const ny = new Date(new Date(guess).toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const utc = new Date(new Date(guess).toLocaleString('en-US', { timeZone: 'UTC' }));
  return new Date(guess + (utc - ny));
}
const fmtDay = (date) =>
  date.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Paris' });
const fmtHour = (date) =>
  date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' }).replace(':', ' h ');

function spreadLabel(spread, home, away) {
  if (spread == null) return '—';
  if (spread === 0) return 'Pick’em';
  return `${spread < 0 ? home.abbr : away.abbr} −${num(Math.abs(spread))}`;
}

const statusFr = { Questionable: 'Incertain' };

function TeamRow({ team, prob, score, favored }) {
  return (
    <div className={`team-row ${favored ? 'is-fav' : ''}`}>
      {team.logo ? <img className="logo" src={team.logo} alt="" width="36" height="36" loading="lazy" /> : <span className="logo" />}
      <div className="team-id">
        <span className="team-name">{team.nick}</span>
        <span className="team-sub">{team.record}</span>
      </div>
      <span className="score">{score}</span>
      <span className="win">{Math.round(prob)}&nbsp;%</span>
    </div>
  );
}

function Scorer({ s }) {
  return (
    <li className="scorer">
      {s.headshot ? <img className="face" src={s.headshot} alt="" width="32" height="32" loading="lazy" /> : <span className="face" />}
      <div className="scorer-id">
        <span className="scorer-name">{s.name}</span>
        <span className="scorer-sub">
          {s.team}, {s.position}, {s.season_tds} TD cette saison
          {s.status && <em className="tag">{statusFr[s.status] || s.status}</em>}
        </span>
      </div>
      <div className="scorer-prob">
        <b>{Math.round(s.prob)}&nbsp;%</b>
        <span className="meter"><span style={{ width: `${s.prob}%` }} /></span>
      </div>
    </li>
  );
}

function GameCard({ g }) {
  const date = kickoff(g.gameday, g.gametime);
  const homeFav = g.prob_home_win >= 50;
  const scorers = g.scorers || [];
  const top = scorers.slice(0, 3);
  const rest = scorers.slice(3);
  const proj = g.projected_score || {};
  return (
    <article className="card" id={g.game_id}>
      <header className="card-head">
        <span>{date ? `${fmtDay(date)}, ${fmtHour(date)}` : 'Date à confirmer'}</span>
        <span className={`conf conf-${g.confidence_score}`}>Confiance {g.confidence_score.toLowerCase()}</span>
      </header>

      <div className="matchup">
        <div className="col-labels"><span>Score</span><span>Victoire</span></div>
        <TeamRow team={g.away} prob={g.prob_away_win} score={proj.away ?? '—'} favored={!homeFav} />
        <TeamRow team={g.home} prob={g.prob_home_win} score={proj.home ?? '—'} favored={homeFav} />
      </div>

      <div className="field" role="img" aria-label={`${g.away.nick} ${g.prob_away_win} %, ${g.home.nick} ${g.prob_home_win} %`}>
        <span style={{ width: `${g.prob_away_win}%`, background: g.away.color }} />
        <span style={{ width: `${g.prob_home_win}%`, background: g.home.color }} />
      </div>

      <dl className="lines">
        <div><dt>Spread modèle</dt><dd>{spreadLabel(g.predicted_spread, g.home, g.away)}</dd></div>
        <div><dt>Bookmakers</dt><dd>{spreadLabel(g.vegas_spread, g.home, g.away)}</dd></div>
        <div><dt>Total</dt><dd>{g.vegas_total != null ? num(g.vegas_total) : '—'}</dd></div>
      </dl>

      {top.length > 0 && (
        <section className="scorers">
          <h3>Buteurs probables</h3>
          <ul>{top.map((s) => <Scorer key={s.name + s.team} s={s} />)}</ul>
          {rest.length > 0 && (
            <details>
              <summary>Voir {rest.length} autres joueurs</summary>
              <ul>{rest.map((s) => <Scorer key={s.name + s.team} s={s} />)}</ul>
            </details>
          )}
        </section>
      )}

      <p className="note">{g.commentary}</p>
    </article>
  );
}

export default function Home() {
  const { season, week, predictions, ranking, season_record: rec, generated_at, top_scorers = [] } = data;
  const updated = new Date(generated_at).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Paris',
  });
  const games = [...predictions].sort(
    (a, b) => (kickoff(a.gameday, a.gametime) || 0) - (kickoff(b.gameday, b.gametime) || 0),
  );

  return (
    <>
      <nav className="topbar">
        <div className="topbar-in">
          <a className="brand" href="#">Gridiron Analytics</a>
          <div className="links">
            <a href="#matchs">Matchs</a>
            <a href="#buteurs">Buteurs</a>
            <a href="#classement">Classement</a>
          </div>
        </div>
      </nav>

      <main className="wrap">
        <header className="hero">
          <h1>Prédictions NFL, semaine {week ?? '—'}</h1>
          <p>
            Saison {season}. Probabilités de victoire, scores projetés et buteurs probables, recalculés chaque mardi.
            {rec?.accuracy != null && (
              <> Bon vainqueur désigné <strong>{rec.correct} fois sur {rec.games}</strong> cette saison ({num(rec.accuracy)}&nbsp;%).</>
            )}
          </p>
        </header>

        <section id="matchs" aria-label="Matchs de la semaine">
          {games.length === 0 ? (
            <div className="empty">Aucun match à venir pour l’instant. Les prédictions reviennent dès la publication du prochain calendrier.</div>
          ) : (
            <div className="grid">{games.map((g) => <GameCard key={g.game_id} g={g} />)}</div>
          )}
        </section>

        {top_scorers.length > 0 && (
          <section id="buteurs" className="block">
            <h2>Meilleures chances de touchdown</h2>
            <p className="lede">Probabilité de marquer au moins un touchdown à la course ou à la réception cette semaine.</p>
            <ol className="board">
              {top_scorers.map((s, i) => (
                <li key={s.name + s.team}>
                  <span className="rk">{i + 1}</span>
                  {s.headshot ? <img className="face" src={s.headshot} alt="" width="32" height="32" loading="lazy" /> : <span className="face" />}
                  <div className="scorer-id">
                    <span className="scorer-name">{s.name}</span>
                    <span className="scorer-sub">{s.team} contre {s.opponent}, {s.position}</span>
                  </div>
                  <b className="big-prob">{Math.round(s.prob)}&nbsp;%</b>
                </li>
              ))}
            </ol>
          </section>
        )}

        <section id="classement" className="block">
          <h2>Classement Elo</h2>
          <p className="lede">1 505 correspond à une équipe moyenne. 25 points d’écart valent environ un point au score.</p>
          <ol className="elo">
            {ranking.map((t, i) => (
              <li key={t.abbr}>
                <span className="rk">{i + 1}</span>
                {t.logo ? <img className="mini-logo" src={t.logo} alt="" width="22" height="22" loading="lazy" /> : <span className="mini-logo" />}
                <span>{t.name}</span>
                <span className="team-sub">{t.record}</span>
                <b>{Math.round(t.elo)}</b>
              </li>
            ))}
          </ol>
        </section>

        <footer>
          Données nflverse, mises à jour le {updated}. Prédictions statistiques à titre informatif, pas des conseils de pari.
        </footer>
      </main>
    </>
  );
}
