'use client';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { kickoff, fmtDay, fmtHour, fmtWeekday, spreadLabel, num, pct } from './lib';
import { Logo, Scorer, ProbBar, TierBadge } from './ui';

function TeamRow({ team, prob, score, favored, final }) {
  return (
    <div className={`team-row ${favored ? 'is-fav' : ''}`}>
      <Logo team={team} />
      <div className="team-id">
        <span className="team-name">{team.nick}</span>
        <span className="team-sub">{team.record}</span>
      </div>
      <span className={`score ${final ? 'final' : ''}`}>{score ?? '—'}</span>
      <span className="win">{pct(prob)}</span>
    </div>
  );
}

function GameCard({ g, windSignal }) {
  const date = kickoff(g.gameday, g.gametime);
  const homeFav = g.prob_home_win >= 50;
  const scorers = g.scorers || [];
  const final = g.status === 'final';
  const live = g.status === 'live';
  const score = final ? g.score : g.projected_score || {};
  return (
    <article className={`card ${final ? 'is-final' : ''}`}>
      <header className="card-head">
        <span>
          {final ? 'Terminé' : live ? 'En cours' : date ? `${fmtDay(date)}, ${fmtHour(date)}` : 'Date à confirmer'}
          {final && g.pick_correct != null && (
            <b className={g.pick_correct ? 'res-ok' : 'res-ko'}> · pronostic {g.pick_correct ? 'juste' : 'faux'}</b>
          )}
        </span>
        <TierBadge tier={g.tier} />
      </header>
      {!final && g.flags && (g.flags.value || g.flags.key_out > 0 || g.flags.windy || g.weather?.temp_c != null) && (
        <div className="flags">
          {g.flags.value && <span className="flag v">Cote française au-dessus du juste prix</span>}
          {g.flags.key_out > 0 && <span className="flag i">{g.flags.key_out} titulaire{g.flags.key_out > 1 ? 's' : ''} offensif{g.flags.key_out > 1 ? 's' : ''} absent{g.flags.key_out > 1 ? 's' : ''}</span>}
          {g.flags.windy && (
            <span className="flag w">
              {windSignal && g.vegas_total != null ? `Vent fort : moins de ${num(g.vegas_total)} points plus probable` : `Vent fort, ${g.weather.wind_kmh}\u00a0km/h`}
            </span>
          )}
          {!g.flags.windy && g.weather?.temp_c != null && <span className="flag">{g.weather.temp_c}&nbsp;°C, vent {g.weather.wind_kmh}&nbsp;km/h</span>}
        </div>
      )}
      <div className="matchup">
        <div className="col-labels"><span>{final ? 'Score final' : 'Score projeté'}</span><span>Victoire</span></div>
        <TeamRow team={g.away} prob={g.prob_away_win} score={score.away} favored={!homeFav} final={final} />
        <TeamRow team={g.home} prob={g.prob_home_win} score={score.home} favored={homeFav} final={final} />
      </div>
      <ProbBar g={g} />
      {!final && (
        <dl className="lines">
          <div><dt>Bookmakers{g.odds ? ` (${g.odds.n_books})` : ''}</dt><dd>{spreadLabel(g.vegas_spread, g.home, g.away)}</dd></div>
          <div><dt>Modèle maison</dt><dd>{spreadLabel(g.model_spread, g.home, g.away)}</dd></div>
          <div><dt>Total</dt><dd>{g.vegas_total != null ? num(g.vegas_total) : '—'}</dd></div>
        </dl>
      )}
      {scorers.length > 0 && (
        <details className="scorers" open={!final}>
          <summary>
            <h3>{final ? 'Buteurs annoncés' : 'Buteurs probables'}</h3>
          </summary>
          <ul>{scorers.slice(0, 3).map((s) => <Scorer key={s.player_id || s.name} s={s} />)}</ul>
        </details>
      )}
      {!final && <p className="note">{g.commentary}</p>}
      <Link className="more" href={`/match/${g.game_id}`}>{final ? 'Revoir l’analyse d’avant-match' : 'Voir l’analyse complète'}</Link>
    </article>
  );
}

export default function GamesBoard({ games, windSignal = false }) {
  const enriched = useMemo(() => games.map((g) => {
    const date = kickoff(g.gameday, g.gametime);
    return { g, date, day: date ? fmtWeekday(date) : 'À confirmer', edge: Math.abs(g.prob_home_win - 50) };
  }), [games]);
  const open = enriched.filter((x) => x.g.status !== 'final');
  const done = enriched.filter((x) => x.g.status === 'final');
  const ok = done.filter((x) => x.g.pick_correct).length;
  const decided = done.filter((x) => x.g.pick_correct != null).length;
  const days = [...new Set([...open].sort((a, b) => (a.date || 0) - (b.date || 0)).map((x) => x.day))];
  const [day, setDay] = useState('Tous');
  const [sort, setSort] = useState('time');

  const shown = open
    .filter((x) => day === 'Tous' || x.day === day)
    .sort((a, b) => (sort === 'time' ? (a.date || 0) - (b.date || 0) : b.edge - a.edge));

  return (
    <>
      {open.length > 0 && (
        <>
          <div className="toolbar">
            <div className="tabs" role="group" aria-label="Jour">
              {['Tous', ...days].map((d) => (
                <button key={d} type="button" aria-pressed={day === d} className={day === d ? 'on' : ''} onClick={() => setDay(d)}>
                  {d}
                  <span className="count">{d === 'Tous' ? open.length : open.filter((x) => x.day === d).length}</span>
                </button>
              ))}
            </div>
            <label className="sort">
              Trier par
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="time">horaire</option>
                <option value="edge">probabilité du favori</option>
              </select>
            </label>
          </div>
          <div className="grid">{shown.map(({ g }) => <GameCard key={g.game_id} g={g} windSignal={windSignal} />)}</div>
        </>
      )}
      {done.length > 0 && (
        <section className="done" aria-label="Matchs terminés">
          <h2 className="done-title">
            Matchs terminés
            <span className="team-sub">{` ${ok} pronostic${ok > 1 ? 's' : ''} juste${ok > 1 ? 's' : ''} sur ${decided}`}</span>
          </h2>
          <div className="grid">{done.sort((a, b) => (b.date || 0) - (a.date || 0)).map(({ g }) => <GameCard key={g.game_id} g={g} />)}</div>
        </section>
      )}
    </>
  );
}
