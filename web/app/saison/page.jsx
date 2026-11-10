import Link from 'next/link';
import data from '../../data/predictions.json';
import { Topbar, Footer, Logo, Sparkline } from '../ui';
import { num } from '../lib';

export const metadata = {
  title: 'Course aux playoffs',
  description: 'Chances de playoffs, de titre de division et de Super Bowl pour les 32 équipes, sur 10 000 simulations de la fin de saison.',
};

const p = (x) => (x == null ? '—' : x >= 99.95 ? '>99\u00a0%' : x > 0 && x < 0.5 ? '<1\u00a0%' : `${Math.round(x)}\u00a0%`);

function Cell({ v, strong }) {
  return (
    <td className={`heat ${strong ? 'strong' : ''}`} style={{ '--h': `${Math.min(v ?? 0, 100)}%` }}>
      <span>{p(v)}</span>
    </td>
  );
}

function ConfTable({ conf, teams }) {
  const rows = teams.filter((t) => t.conf === conf && t.sim).sort((a, b) => b.sim.playoff - a.sim.playoff || b.sim.proj_wins - a.sim.proj_wins);
  return (
    <section className="panel">
      <h2>{conf}</h2>
      <div className="table-scroll">
        <table className="sim">
          <thead>
            <tr>
              <th className="t-left">Équipe</th><th>Bilan</th><th>Victoires projetées</th><th>Playoffs</th>
              <th>Évolution</th><th>Si victoire</th><th>Si défaite</th><th>Division</th><th>N°1</th><th>Super Bowl</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => (
              <tr key={t.abbr} className={i === 6 ? 'cut' : ''}>
                <th scope="row" className="t-left"><span className="team-cell"><Logo team={t} size={22} /><Link href={`/equipe/${t.abbr}`}>{t.nick}</Link><span className="team-sub">{t.division?.replace(`${conf} `, '')}</span></span></th>
                <td>{t.record}</td>
                <td>{num(t.sim.proj_wins)}</td>
                <Cell v={t.sim.playoff} strong />
                <td><Sparkline values={(t.sim_history || []).map((x) => x[1])} color="var(--accent)" width={64} height={20} /></td>
                <td className="muted">{t.sim.if_win != null ? p(t.sim.if_win) : ''}</td>
                <td className="muted">{t.sim.if_lose != null ? p(t.sim.if_lose) : ''}</td>
                <Cell v={t.sim.division} />
                <Cell v={t.sim.seed1} />
                <Cell v={t.sim.sb} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function Saison() {
  const { season, week, ranking } = data;
  const withSim = ranking.filter((t) => t.sim);
  const favs = [...withSim].sort((a, b) => b.sim.sb - a.sim.sb).slice(0, 8);
  const confs = [...new Set(withSim.map((t) => t.conf))].sort();
  const post = data.postseason || [];
  const byAbbr = Object.fromEntries(ranking.map((t) => [t.abbr, t]));
  const rounds = [...new Set(post.map((g) => g.round))];

  return (
    <>
      <Topbar current="Playoffs" />
      <main className="wrap">
        <header className="hero">
          <div>
            <h1>Course aux playoffs {season}</h1>
            <p>
              10 000 simulations de la fin de saison, avant la semaine {week}. Chaque simulation joue tous les matchs restants
              selon la force des équipes (Elo et efficacité par jeu, cotes du marché pour la semaine en cours), puis les playoffs
              au format NFL : 7 qualifiés par conférence, le n°1 exempté du premier tour.
            </p>
          </div>
        </header>

        {favs.length > 0 && (
          <section className="panel">
            <h2>Favoris pour le Super Bowl</h2>
            <ol className="sb-favs">
              {favs.map((t) => (
                <li key={t.abbr}>
                  <Logo team={t} size={36} />
                  <span className="sb-fav-name">{t.nick}<span className="team-sub">{t.record}</span></span>
                  <b>{p(t.sim.sb)}</b>
                  <span className="team-sub">cote juste {t.sim.sb > 0 ? num(100 / t.sim.sb, 1) : '—'}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {confs.map((c) => <ConfTable key={c} conf={c} teams={withSim} />)}

        {data.studies?.playoff_backtest && (() => {
          const pb = data.studies.playoff_backtest;
          return (
            <section className="panel">
              <h2>Fiabilité vérifiée</h2>
              <p className="lede">
                La même simulation rejouée sur les saisons {pb.seasons[0]} à {pb.seasons[1]}, après les semaines {pb.weeks.join(', ')},
                avec les seules informations alors disponibles ({pb.n} cas). Quand les deux colonnes sont proches, les chances annoncées sont fiables.
              </p>
              <table className="compare rel">
                <thead><tr><th>Chances annoncées</th><th>Cas</th><th>Annoncé</th><th>Qualifiées</th></tr></thead>
                <tbody>
                  {pb.buckets.map((b) => (
                    <tr key={b.label}><th scope="row">{b.label}</th><td>{b.n}</td><td>{num(b.predicted)}&nbsp;%</td><td><b>{num(b.actual)}&nbsp;%</b></td></tr>
                  ))}
                </tbody>
              </table>
              <p className="fine">
                Score de Brier {num(pb.brier, 3)}, contre {num(pb.brier_base, 3)} en annonçant la même chance à toutes les équipes.
                Il passe de {num(pb.by_week[0].brier, 3)} après la semaine {pb.by_week[0].week} à {num(pb.by_week.at(-1).brier, 3)} après la semaine {pb.by_week.at(-1).week}.
              </p>
            </section>
          );
        })()}

        {post.length > 0 && (
          <section className="panel">
            <h2>Phases finales</h2>
            {rounds.map((r) => (
              <div key={r} className="round">
                <h3 className="col-title">{r}</h3>
                <ul className="flips">
                  {post.filter((g) => g.round === r).map((g) => (
                    <li key={g.game_id}>
                      {byAbbr[g.away] && <Logo team={byAbbr[g.away]} size={22} />} {byAbbr[g.away]?.nick || g.away}
                      <span className="team-sub">à</span>
                      {byAbbr[g.home] && <Logo team={byAbbr[g.home]} size={22} />} {byAbbr[g.home]?.nick || g.home}
                      <b>{g.score ? `${g.score.away}-${g.score.home}` : g.prob_home != null ? `${byAbbr[g.home]?.nick || g.home} ${Math.round(g.prob_home)}\u00a0%` : 'À venir'}</b>
                      {!g.score && g.prob_home != null && <Link href={`/match/${g.game_id}`}>Analyse</Link>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        )}

        {withSim.length === 0 && post.length === 0 && (
          <div className="empty">Les chances de playoffs reviendront avec le calendrier de la prochaine saison.</div>
        )}

        <p className="fine">
          « Si victoire » et « Si défaite » : chances de playoffs selon le résultat du match de cette semaine.
          La ligne marque la limite des 7 places qualificatives. Les départages officiels (confrontations directes,
          bilan de division…) sont simplifiés : les écarts de moins de 2 points sont à lire avec prudence.
          {' '}<Link href="/#classement">Voir le classement Elo</Link>.
        </p>
      </main>
      <Footer />
    </>
  );
}
