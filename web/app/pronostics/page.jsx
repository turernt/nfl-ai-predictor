import Link from 'next/link';
import data from '../../data/predictions.json';
import { Topbar, Footer, Logo } from '../ui';
import { kickoff, fmtDay, fmtHour, num, pct } from '../lib';

export const metadata = {
  title: 'Pronostics les plus fiables',
  description: 'Les victoires et buteurs les plus probables de la semaine, avec leur fiabilité vérifiée sur les saisons passées.',
};

const odds = (x) => num(x, 2);
const tierClass = { 'Très sûr': 't1', 'Sûr': 't2', 'Probable': 't3', 'Serré': 't4' };

function When({ g }) {
  const d = kickoff(g.gameday, g.gametime);
  return <span className="pk-when">{d ? `${fmtDay(d)}, ${fmtHour(d)}` : 'Date à confirmer'}</span>;
}

function WinPick({ p, rank }) {
  return (
    <li className="pk">
      <span className="pk-rank">{rank}</span>
      <div className="pk-main">
        <div className="pk-teams">
          <Logo team={p.team} size={40} />
          <div>
            <span className="pk-title">Victoire des {p.team.nick}</span>
            <span className="pk-sub">
              {p.home ? 'à domicile contre' : 'à l’extérieur contre'} les {p.opponent.nick}, <When g={p} />
            </span>
          </div>
        </div>
        <div className="pk-facts">
          <span className={`badge ${tierClass[p.tier]}`}>{p.tier}</span>
          {p.hist && (
            <span>
              Les favoris de ce niveau ont gagné <b>{num(p.hist.actual)}&nbsp;%</b> du temps ({p.hist.games} matchs depuis 2012)
            </span>
          )}
          <span className={p.model_agrees ? 'ok' : 'warn'}>
            {p.model_agrees ? `Notre modèle confirme (${pct(p.model_prob)})` : `Notre modèle doute (${pct(p.model_prob)})`}
          </span>
        </div>
      </div>
      <div className="pk-side">
        <span className="pk-prob">{pct(p.prob)}</span>
        <span className="pk-odds">Cote juste {odds(p.fair_odds)}</span>
        <Link href={`/match/${p.game_id}`} className="pk-link">Analyse</Link>
      </div>
    </li>
  );
}

function ScorerPick({ s, rank }) {
  return (
    <li className="pk">
      <span className="pk-rank">{rank}</span>
      <div className="pk-main">
        <div className="pk-teams">
          {s.headshot ? <img className="face lg" src={s.headshot} alt="" width="40" height="40" loading="lazy" /> : <span className="face lg" />}
          <div>
            <span className="pk-title">{s.name} marque un touchdown</span>
            <span className="pk-sub">{s.team} contre {s.opponent}, {s.position}, {s.season_tds} TD cette saison</span>
          </div>
        </div>
        {s.hist && (
          <div className="pk-facts">
            <span>
              Cette saison, nos buteurs annoncés à {s.hist.label} ont marqué <b>{num(s.hist.actual)}&nbsp;%</b> du temps ({s.hist.n} cas)
            </span>
            {s.status && <span className="warn">Statut incertain</span>}
          </div>
        )}
      </div>
      <div className="pk-side">
        <span className="pk-prob">{pct(s.prob)}</span>
        <span className="pk-odds">Cote juste {odds(s.fair_odds)}</span>
      </div>
    </li>
  );
}

export default function Pronostics() {
  const { week, picks, bilan } = data;
  if (!picks) return null;
  const s = bilan.summary;
  const rel = picks.reliability;

  return (
    <>
      <Topbar current="Pronostics" />
      <main className="wrap narrow">
        <header className="hero">
          <div>
            <h1>Pronostics de la semaine {week}</h1>
            <p>
              Les issues les plus probables de la semaine, classées par fiabilité. Ce ne sont pas les paris les plus
              rentables : ce sont ceux qui ont le plus de chances de se réaliser, avec leur taux de réussite vérifié.
            </p>
          </div>
        </header>

        <aside className="howto">
          <b>Comment lire la cote juste ?</b> C’est la cote qui correspond exactement à la probabilité affichée
          (1 ÷ probabilité). Un pari n’est intéressant que si la cote proposée par votre site de paris est
          <b> supérieure</b> à la cote juste. Si elle est inférieure, le pari perd de l’argent sur la durée, même s’il gagne souvent.
        </aside>

        <section className="panel">
          <h2>Victoires les plus sûres</h2>
          <p className="lede">Favoris à 70&nbsp;% ou plus.</p>
          {picks.safest.length
            ? <ol className="picks">{picks.safest.map((p, i) => <WinPick key={p.game_id} p={p} rank={i + 1} />)}</ol>
            : <p className="lede">Aucun favori à 70&nbsp;% ou plus cette semaine : semaine très ouverte.</p>}
        </section>

        {picks.scorers.length > 0 && (
          <section className="panel">
            <h2>Buteurs les plus probables</h2>
            <p className="lede">Joueurs à 40&nbsp;% ou plus de marquer au moins un touchdown à la course ou à la réception.</p>
            <ol className="picks">{picks.scorers.map((x, i) => <ScorerPick key={x.player_id || x.name} s={x} rank={i + 1} />)}</ol>
          </section>
        )}

        {picks.coin_flips.length > 0 && (
          <section className="panel">
            <h2>Matchs à éviter</h2>
            <p className="lede">Le favori a moins de 57&nbsp;% de chances : c’est presque pile ou face.</p>
            <ul className="flips">
              {picks.coin_flips.map((p) => (
                <li key={p.game_id}>
                  <Logo team={p.team} size={24} /> {p.team.nick} <span className="team-sub">contre</span> {p.opponent.nick} <Logo team={p.opponent} size={24} />
                  <b>{pct(p.prob)}</b>
                  <Link href={`/match/${p.game_id}`}>Analyse</Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="panel">
          <h2>Fiabilité vérifiée</h2>
          <p className="lede">
            Probabilité annoncée et taux de réussite réel du favori, sur tous les matchs NFL depuis 2012.
            Quand les deux colonnes sont proches, les probabilités sont fiables.
          </p>
          <table className="compare rel">
            <thead><tr><th>Palier</th><th>Matchs</th><th>Annoncé</th><th>Réel</th></tr></thead>
            <tbody>
              {rel.map((r) => (
                <tr key={r.tier}>
                  <th scope="row"><span className={`badge ${tierClass[r.tier]}`}>{r.tier}</span> {Math.round(r.min * 100)}&nbsp;% et plus</th>
                  <td>{r.games}</td><td>{num(r.predicted)}&nbsp;%</td><td><b>{num(r.actual)}&nbsp;%</b></td>
                </tr>
              ))}
            </tbody>
          </table>
          {s.scorer_tiers && (
            <table className="compare rel">
              <thead><tr><th>Buteurs (saison en cours)</th><th>Cas</th><th>Annoncé</th><th>Réel</th></tr></thead>
              <tbody>
                {s.scorer_tiers.filter((t) => t.n).map((t) => (
                  <tr key={t.label}><th scope="row">{t.label}</th><td>{t.n}</td><td>{num(t.predicted)}&nbsp;%</td><td><b>{num(t.actual)}&nbsp;%</b></td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          <h2>Ce qui compte vraiment, et ce qui ne compte pas</h2>
          <p className="lede">Nous avons testé chaque facteur sur 899 matchs (saisons 2023 à 2026), en vérifiant ce qu’il apporte en plus des cotes.</p>
          <ul className="findings">
            <li><b>Les cotes du marché sont le meilleur prédicteur.</b> Elles intègrent déjà la forme, les blessures, l’avantage du terrain et la météo. C’est pourquoi nos probabilités en sont tirées.</li>
            <li><b>La forme récente et l’historique des confrontations n’apportent rien de plus.</b> Utiles seuls, ils ne prédisent presque rien une fois les cotes connues (corrélation inférieure à 0,04 avec l’écart restant).</li>
            <li><b>L’avantage du terrain ne vaut plus qu’environ 1,5 point</b>, contre 3 il y a quinze ans. Il est déjà pris en compte par les bookmakers.</li>
            <li><b>Le quarterback titulaire est le facteur individuel le plus important.</b> Un changement de dernière minute peut faire basculer un match : vérifiez toujours les annonces avant de jouer.</li>
            <li>
              <b>Nous ne proposons pas de paris contre l’écart (handicap).</b> Quand notre modèle s’éloigne des bookmakers d’au moins 3 points,
              il a eu raison dans seulement 46,7&nbsp;% des cas sur 210 matchs depuis 2023
              {s.ats_games ? ` (${s.ats_correct} sur ${s.ats_games} cette saison)` : ''}. Il faut 52,4&nbsp;% pour gagner de l’argent.
            </li>
            <li><b>Le vent fort réduit le nombre de points</b> : avec un vent de 19 km/h ou plus, le total est passé sous la ligne 56&nbsp;% du temps (109 matchs). L’échantillon est faible et la météo n’est pas connue à l’avance dans nos données : nous ne l’utilisons pas encore.</li>
          </ul>
        </section>

        <aside className="responsible">
          <b>Jouer comporte des risques : endettement, isolement, dépendance.</b> Pour être aidé, appelez le 09 74 75 13 13 (appel non surtaxé).
          Les jeux d’argent sont interdits aux mineurs. Ces pronostics sont des probabilités, jamais des certitudes.
        </aside>
      </main>
      <Footer />
    </>
  );
}
