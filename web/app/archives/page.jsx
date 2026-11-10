import Link from 'next/link';
import seasons from '../../data/seasons.json';
import { Topbar, Footer, Logo, Sparkline } from '../ui';
import { num } from '../lib';

export const metadata = { title: 'Archives des saisons' };

const rate = (a, b) => (b ? `${num((a / b) * 100)}\u00a0%` : '—');
const p = (x) => (x == null ? '—' : x >= 99.95 ? '>99\u00a0%' : x > 0 && x < 0.5 ? '<1\u00a0%' : `${Math.round(x)}\u00a0%`);

function Season({ year, s }) {
  const tr = s.tracking || {};
  const confs = [...new Set(s.teams.map((t) => t.conf))].sort();
  return (
    <section className="panel season-card">
      <h2>Saison {year}</h2>
      <p className="lede">État après la semaine {s.week - 1 > 0 ? s.week - 1 : s.week}, mis à jour le {new Date(s.updated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}.</p>
      <div className="stats">
        <div className="stat main"><span className="stat-label">Pronostics publiés</span>
          <span className="stat-big">{rate(tr.correct, tr.settled)}</span>
          <span className="stat-sub">{tr.correct ?? 0} sur {tr.settled ?? 0}, Brier {tr.brier != null ? num(tr.brier, 3) : '—'}</span></div>
        <div className="stat"><span className="stat-label">Buteurs affichés</span>
          <span className="stat-big">{tr.scorers?.n ? rate(tr.scorers.hits, tr.scorers.n) : '—'}</span>
          <span className="stat-sub">{tr.scorers?.n ? `${tr.scorers.hits} sur ${tr.scorers.n}, ${num(tr.scorers.expected, 0)} attendus` : 'aucun suivi'}</span></div>
        <div className="stat"><span className="stat-label">Cotes signalées</span>
          <span className="stat-big">{tr.value?.settled ? `${tr.value.units >= 0 ? '+' : '−'}${num(Math.abs(tr.value.units), 2)}\u00a0€` : '—'}</span>
          <span className="stat-sub">{tr.value?.n ? `${tr.value.n} signalées, clôture ${tr.value.clv_avg != null ? num(tr.value.clv_avg, 1) : '—'}\u00a0%` : 'aucune'}</span></div>
        <div className="stat"><span className="stat-label">Simulation rétrospective</span>
          <span className="stat-big">{rate(s.simulation?.correct, s.simulation?.games)}</span>
          <span className="stat-sub">{s.simulation?.correct} sur {s.simulation?.games}</span></div>
      </div>
      <div className="two-col">
        {confs.map((c) => (
          <div key={c}>
            <h3 className="col-title">{c} : chances de playoffs semaine par semaine</h3>
            <ul className="flips">
              {s.teams.filter((t) => t.conf === c).sort((a, b) => (b.playoff ?? 0) - (a.playoff ?? 0)).map((t) => (
                <li key={t.abbr}>
                  <Logo team={t} size={22} /> <Link href={`/equipe/${t.abbr}`}>{t.nick}</Link> <span className="team-sub">{t.record}</span>
                  <Sparkline values={(t.history || []).map((x) => x[1])} color="var(--accent)" width={80} height={20} />
                  <b>{p(t.playoff)}</b>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Archives() {
  const years = Object.keys(seasons).sort((a, b) => b - a);
  return (
    <>
      <Topbar />
      <main className="wrap narrow">
        <header className="hero">
          <div>
            <h1>Archives des saisons</h1>
            <p>Le bilan réel de chaque saison et l’évolution des chances de playoffs, conservés d’une année à l’autre.</p>
          </div>
        </header>
        {years.length ? years.map((y) => <Season key={y} year={y} s={seasons[y]} />)
          : <div className="empty">Aucune saison archivée pour l’instant.</div>}
      </main>
      <Footer />
    </>
  );
}
