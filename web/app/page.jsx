import data from '../data/predictions.json';

const fmtNum = (n) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

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
const dayLabel = (date) =>
  date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Paris' });
const hourLabel = (date) =>
  date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' }).replace(':', ' h ');

// Spread affiché côté favori : « BUF −7,3 »
function spreadLabel(spread, home, away) {
  if (spread == null) return '—';
  if (spread === 0) return 'Pick’em';
  const fav = spread < 0 ? home.abbr : away.abbr;
  return `${fav} −${fmtNum(Math.abs(spread))}`;
}

function Game({ g }) {
  const homeWins = g.prob_home_win >= 50;
  const date = kickoff(g.gameday, g.gametime);
  return (
    <article className="game">
      <div className="teams">
        <div className={`team ${homeWins ? 'lose' : ''}`}>
          <span className="name">{g.away.name}</span>
          <span className="pct">{Math.round(g.prob_away_win)} %</span>
        </div>
        <span className="at">{g.neutral_site ? 'vs' : '@'}</span>
        <div className={`team home ${homeWins ? '' : 'lose'}`}>
          <span className="pct">{Math.round(g.prob_home_win)} %</span>
          <span className="name">{g.home.name}</span>
        </div>
      </div>

      <div
        className="field"
        role="img"
        aria-label={`${g.away.name} ${g.prob_away_win} %, ${g.home.name} ${g.prob_home_win} %`}
      >
        <span style={{ width: `${g.prob_away_win}%`, background: g.away.color }} />
        <span style={{ width: `${g.prob_home_win}%`, background: g.home.color }} />
        <i className="mid" />
      </div>

      <div className="meta">
        {date && <span>{hourLabel(date)}</span>}
        <span>Spread du modèle <b>{spreadLabel(g.predicted_spread, g.home, g.away)}</b></span>
        <span>Bookmakers <b>{spreadLabel(g.vegas_spread, g.home, g.away)}</b></span>
        <span>
          Confiance <b className={`conf-${g.confidence_score}`}>{g.confidence_score.toLowerCase()}</b>
        </span>
      </div>
      <p className="note">{g.commentary}</p>
    </article>
  );
}

export default function Home() {
  const { season, week, predictions, ranking, season_record: rec, generated_at } = data;

  const days = [];
  for (const g of predictions) {
    const date = kickoff(g.gameday, g.gametime);
    const label = date ? dayLabel(date) : 'Date à confirmer';
    const last = days[days.length - 1];
    if (last && last.label === label) last.games.push(g);
    else days.push({ label, games: [g] });
  }

  const updated = new Date(generated_at).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Paris',
  });

  return (
    <main className="wrap">
      <header className="masthead">
        <h1>Gridiron<br />Analytics</h1>
        <div className="week">
          Saison {season}{week ? `, semaine ${week}` : ''}
        </div>
      </header>

      <p className="intro">
        Chaque mardi, un modèle Elo recalcule la force des 32 équipes à partir de tous les résultats depuis 2010,
        puis estime qui gagne les matchs de la semaine.
        {rec?.accuracy != null && (
          <> Cette saison, il a désigné le bon vainqueur <strong>{rec.correct} fois sur {rec.games}</strong> ({fmtNum(rec.accuracy)} %).</>
        )}
      </p>

      {days.length === 0 ? (
        <div className="empty">
          Aucun match à venir pour l’instant. Les prédictions reviennent dès la publication du prochain calendrier.
        </div>
      ) : (
        days.map((d) => (
          <section className="day" key={d.label}>
            <h2>{d.label.charAt(0).toUpperCase() + d.label.slice(1)}</h2>
            {d.games.map((g) => <Game key={g.game_id} g={g} />)}
          </section>
        ))
      )}

      <section className="ranking">
        <h2>Classement Elo</h2>
        <p>1 505 correspond à une équipe moyenne. 25 points d’écart valent environ un point au score.</p>
        <ol>
          {ranking.map((t, i) => (
            <li key={t.abbr}>
              <span className="rk">{i + 1}</span>
              <span className="sw" style={{ background: t.color }} />
              <span>{t.name}</span>
              <span className="elo">{Math.round(t.elo)}</span>
            </li>
          ))}
        </ol>
      </section>

      <footer>
        Données nflverse, mises à jour le {updated}. Prédictions statistiques à titre informatif, pas des conseils de pari.
      </footer>
    </main>
  );
}
