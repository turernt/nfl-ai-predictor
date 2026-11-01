'use client';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { kickoff, fmtDay, fmtHour, fmtWeekday, spreadLabel, num, pct } from './lib';
import { Logo, Scorer, ProbBar } from './ui';

function TeamRow({ team, prob, score, favored }) {
  return (
    <div className={`team-row ${favored ? 'is-fav' : ''}`}>
      <Logo team={team} />
      <div className="team-id">
        <span className="team-name">{team.nick}</span>
        <span className="team-sub">{team.record}</span>
      </div>
      <span className="score">{score ?? '—'}</span>
      <span className="win">{pct(prob)}</span>
    </div>
  );
}

function GameCard({ g }) {
  const date = kickoff(g.gameday, g.gametime);
  const homeFav = g.prob_home_win >= 50;
  const scorers = g.scorers || [];
  const proj = g.projected_score || {};
  return (
    <article className="card">
      <header className="card-head">
        <span>{date ? `${fmtDay(date)}, ${fmtHour(date)}` : 'Date à confirmer'}</span>
        <span className={`conf conf-${g.confidence_score}`}>Confiance {g.confidence_score.toLowerCase()}</span>
      </header>
      {g.flags && (g.flags.value || g.flags.key_out > 0 || g.flags.windy || g.weather?.temp_c != null) && (
        <div className="flags">
          {g.flags.value && <span className="flag v">Cote française au-dessus du juste prix</span>}
          {g.flags.key_out > 0 && <span className="flag i">{g.flags.key_out} titulaire{g.flags.key_out > 1 ? 's' : ''} offensif{g.flags.key_out > 1 ? 's' : ''} absent{g.flags.key_out > 1 ? 's' : ''}</span>}
          {g.flags.windy && <span className="flag w">Vent fort</span>}
          {!g.flags.windy && g.weather?.temp_c != null && <span className="flag">{g.weather.temp_c}&nbsp;°C, vent {g.weather.wind_kmh}&nbsp;km/h</span>}
        </div>
      )}
      <div className="matchup">
        <div className="col-labels"><span>Score</span><span>Victoire</span></div>
        <TeamRow team={g.away} prob={g.prob_away_win} score={proj.away} favored={!homeFav} />
        <TeamRow team={g.home} prob={g.prob_home_win} score={proj.home} favored={homeFav} />
      </div>
      <ProbBar g={g} />
      <dl className="lines">
        <div><dt>Bookmakers{g.odds ? ` (${g.odds.n_books})` : ''}</dt><dd>{spreadLabel(g.vegas_spread, g.home, g.away)}</dd></div>
        <div><dt>Modèle maison</dt><dd>{spreadLabel(g.model_spread, g.home, g.away)}</dd></div>
        <div><dt>Total</dt><dd>{g.vegas_total != null ? num(g.vegas_total) : '—'}</dd></div>
      </dl>
      {scorers.length > 0 && (
        <section className="scorers">
          <h3>Buteurs probables</h3>
          <ul>{scorers.slice(0, 3).map((s) => <Scorer key={s.player_id || s.name} s={s} />)}</ul>
        </section>
      )}
      <p className="note">{g.commentary}</p>
      <Link className="more" href={`/match/${g.game_id}`}>Voir l’analyse complète</Link>
    </article>
  );
}

export default function GamesBoard({ games }) {
  const enriched = useMemo(() => games.map((g) => {
    const date = kickoff(g.gameday, g.gametime);
    return { g, date, day: date ? fmtWeekday(date) : 'À confirmer', edge: Math.abs(g.prob_home_win - 50) };
  }), [games]);
  const days = [...new Set([...enriched].sort((a, b) => (a.date || 0) - (b.date || 0)).map((x) => x.day))];
  const [day, setDay] = useState('Tous');
  const [sort, setSort] = useState('time');

  const shown = enriched
    .filter((x) => day === 'Tous' || x.day === day)
    .sort((a, b) => (sort === 'time' ? (a.date || 0) - (b.date || 0) : b.edge - a.edge));

  return (
    <>
      <div className="toolbar">
        <div className="tabs" role="tablist" aria-label="Jour">
          {['Tous', ...days].map((d) => (
            <button key={d} role="tab" aria-selected={day === d} className={day === d ? 'on' : ''} onClick={() => setDay(d)}>
              {d}
              <span className="count">{d === 'Tous' ? enriched.length : enriched.filter((x) => x.day === d).length}</span>
            </button>
          ))}
        </div>
        <label className="sort">
          Trier par
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="time">horaire</option>
            <option value="edge">confiance</option>
          </select>
        </label>
      </div>
      <div className="grid">{shown.map(({ g }) => <GameCard key={g.game_id} g={g} />)}</div>
    </>
  );
}
