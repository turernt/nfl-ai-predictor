import Link from 'next/link';
import { notFound } from 'next/navigation';
import data from '../../../data/predictions.json';
import { Topbar, Footer, Logo, Sparkline } from '../../ui';
import { num, pct } from '../../lib';

export function generateStaticParams() {
  return data.ranking.map((t) => ({ abbr: t.abbr }));
}

export function generateMetadata({ params }) {
  const t = data.ranking.find((x) => x.abbr === params.abbr);
  if (!t) return {};
  return {
    title: `${t.name} : chances de playoffs et calendrier`,
    description: `${t.name} (${t.record}) : probabilités de victoire match par match, chances de playoffs et de Super Bowl.`,
  };
}

const p = (x) => (x == null ? '—' : x >= 99.95 ? '>99\u00a0%' : x > 0 && x < 0.5 ? '<1\u00a0%' : `${Math.round(x)}\u00a0%`);

export default function TeamPage({ params }) {
  const rank = data.ranking.findIndex((x) => x.abbr === params.abbr);
  if (rank < 0) notFound();
  const t = data.ranking[rank];
  const s = t.sim || {};
  const current = new Set(data.predictions.map((g) => g.game_id));
  const scorers = data.predictions.flatMap((g) => g.scorers || []).filter((x) => x.team === t.abbr);

  return (
    <>
      <Topbar />
      <main className="wrap narrow">
        <Link className="back" href="/saison">Course aux playoffs</Link>
        <header className="team-head">
          <Logo team={t} size={72} />
          <div>
            <h1>{t.name}</h1>
            <p className="team-sub">
              {t.record}, {t.division}. Elo {Math.round(t.elo)} ({rank + 1}e). Attaque {t.off_rank ? `${t.off_rank}e` : '—'}, défense {t.def_rank ? `${t.def_rank}e` : '—'} (EPA).
            </p>
          </div>
          <Sparkline values={t.history} width={120} height={36} color="var(--accent)" />
        </header>

        {t.sim && (
          <section className="stats">
            <div className="stat main"><span className="stat-label">Playoffs</span><span className="stat-big">{p(s.playoff)}</span><span className="stat-sub">{num(s.proj_wins)} victoires projetées</span></div>
            <div className="stat"><span className="stat-label">Titre de division</span><span className="stat-big">{p(s.division)}</span><span className="stat-sub">Tête de série n°1 : {p(s.seed1)}</span></div>
            <div className="stat"><span className="stat-label">Finale de conférence gagnée</span><span className="stat-big">{p(s.conf)}</span><span className="stat-sub">{t.conf}</span></div>
            <div className="stat"><span className="stat-label">Super Bowl</span><span className="stat-big">{p(s.sb)}</span><span className="stat-sub">cote juste {s.sb > 0 ? num(100 / s.sb, 1) : '—'}</span></div>
          </section>
        )}

        <section className="panel">
          <h2>Calendrier</h2>
          <p className="lede">Résultats et probabilité de victoire pour chaque match restant.</p>
          <ul className="sched">
            {(t.schedule || []).flatMap((g, i, arr) => {
              const prev = i ? arr[i - 1].week : 0;
              const byes = [];
              for (let w = prev + 1; w < g.week; w++) byes.push({ bye: true, week: w });
              return [...byes, g];
            }).map((g) => g.bye ? (
              <li key={`bye${g.week}`} className="bye"><span className="wk">S{g.week}</span><span className="team-sub">Semaine de repos</span><span /></li>
            ) : (
              <li key={g.game_id} className={g.result === 'V' ? 'w' : g.result === 'D' ? 'l' : ''}>
                <span className="wk">S{g.week}</span>
                <span className="opp">
                  <span className="team-sub">{g.home ? 'contre' : 'à'}</span>
                  {g.opp_logo ? <img className="logo" src={g.opp_logo} alt="" width="22" height="22" loading="lazy" /> : null}
                  <Link href={`/equipe/${g.opp}`}>{g.opp_nick}</Link>
                </span>
                {g.result
                  ? <span className="res"><b>{g.result === 'V' ? 'Victoire' : g.result === 'D' ? 'Défaite' : 'Nul'}</b> {g.score}</span>
                  : (
                    <span className="res">
                      <span className="meter wide"><span style={{ width: `${g.prob}%` }} /></span>
                      <b>{pct(g.prob)}</b>
                      {current.has(g.game_id) && <Link href={`/match/${g.game_id}`} className="pk-link">Analyse</Link>}
                    </span>
                  )}
              </li>
            ))}
          </ul>
        </section>

        {scorers.length > 0 && (
          <section className="panel">
            <h2>Buteurs probables cette semaine</h2>
            <ul className="flips">
              {scorers.map((x) => (
                <li key={x.player_id || x.name}>
                  {x.headshot ? <img className="face" src={x.headshot} alt="" width="32" height="32" loading="lazy" /> : <span className="face" />}
                  {x.name} <span className="team-sub">{x.position}, {x.season_tds} TD</span>
                  <b>{pct(x.prob)}</b>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <Footer />
    </>
  );
}
