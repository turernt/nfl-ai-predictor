import Link from 'next/link';
import data from '../../data/predictions.json';
import { Topbar, Footer, Logo } from '../ui';
import { kickoff, fmtDay, fmtHour, num, pct, fr1, windNote } from '../lib';

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
          {p.best_fr && (
            <span className={p.ev > 0 ? 'ok' : ''}>
              Meilleure cote française : <b>{odds(p.best_fr.price)}</b> ({p.best_fr.book}), espérance {p.ev > 0 ? '+' : '−'}{num(Math.abs(p.ev))}&nbsp;%
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

function ValuePick({ v }) {
  return (
    <li className="pk">
      <span className="pk-rank">+</span>
      <div className="pk-main">
        <div className="pk-teams">
          <Logo team={v.team} size={40} />
          <div>
            <span className="pk-title">Victoire des {v.team.nick} à {odds(v.price)} chez {v.book}</span>
            <span className="pk-sub">contre les {v.opponent.nick}, <When g={v} /></span>
          </div>
        </div>
        <div className="pk-facts">
          <span>Probabilité réelle {pct(v.prob)}, cote juste <b>{odds(v.fair_odds)}</b></span>
          {v.stake_pct > 0 && <span>Mise prudente : <b>{num(v.stake_pct, 1)}&nbsp;%</b> de votre budget de jeu (quart de Kelly)</span>}
          {v.prob < 40 && <span className="warn">Outsider : gagne rarement, rentable seulement sur la durée</span>}
        </div>
      </div>
      <div className="pk-side">
        <span className="pk-prob">+{num(v.ev)}&nbsp;%</span>
        <span className="pk-odds">espérance de gain</span>
        <Link href={`/match/${v.game_id}`} className="pk-link">Analyse</Link>
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
        <div className="pk-facts">
          {s.form?.length > 0 && (
            <span>
              A marqué dans <b>{s.scored_last} de ses {s.form.length} derniers matchs</b>
              {s.snap != null ? `, joue ${s.snap}\u00a0% des actions offensives` : ''}
            </span>
          )}
          {s.hist && (
            <span>
              Cette saison, nos buteurs annoncés à {s.hist.label} ont marqué <b>{num(s.hist.actual)}&nbsp;%</b> du temps ({s.hist.n} cas)
            </span>
          )}
          {s.status && <span className="warn">Statut incertain</span>}
        </div>
      </div>
      <div className="pk-side">
        <span className="pk-prob">{pct(s.prob)}</span>
        <span className="pk-odds">Cote juste {odds(s.fair_odds)}</span>
      </div>
    </li>
  );
}

export default function Pronostics() {
  const { week, picks, bilan, odds_source: src, scorer_model: sm, studies: st = {} } = data;
  const dv = st.devig, wn = windNote(st);
  const consensus = src?.type === 'consensus';
  if (!picks) return null;
  const s = bilan.summary;
  const rel = picks.reliability;

  return (
    <>
      <Topbar current="Pronostics" />
      <main className="wrap narrow">
        <header className="hero">
          <div>
            <h1>Pronostics, {(data.week_label || `semaine ${week}`).replace(/^Semaine/, 'semaine')}</h1>
            <p>
              Les issues les plus probables de la semaine, classées par fiabilité. Ce ne sont pas les paris les plus
              rentables : ce sont ceux qui ont le plus de chances de se réaliser, avec leur taux de réussite vérifié.
            </p>
            <p className="src">
              {consensus
                ? `Probabilités : médiane de ${src.books} bookmakers, en ne gardant que ceux dont la marge ne dépasse pas 6 % (marge retirée par la méthode de Shin).`
                : 'Probabilités calculées sur les cotes de référence nflverse, marge retirée par la méthode de Shin.'}
            </p>
          </div>
        </header>

        <aside className="howto">
          <b>Comment lire la cote juste ?</b> C’est la cote qui correspond exactement à la probabilité affichée
          (1 ÷ probabilité). Un pari n’est intéressant que si la cote proposée par votre site de paris est
          <b> supérieure</b> à la cote juste. Si elle est inférieure, le pari perd de l’argent sur la durée, même s’il gagne souvent.
        </aside>

        {consensus && (
          <section className="panel">
            <h2>Cotes françaises au-dessus du juste prix</h2>
            <p className="lede">
              Une cote proposée par un site français dépasse d’au moins 3&nbsp;% la cote juste du marché. C’est la seule
              situation où un pari peut être rentable sur la durée, à condition que l’écart se confirme : le bilan suit chaque
              cote signalée face à la cote de clôture.
            </p>
            {picks.value?.length
              ? <ol className="picks">{picks.value.map((v) => <ValuePick key={v.game_id + v.team.abbr} v={v} />)}</ol>
              : <p className="lede">Aucune pour l’instant : les sites français proposent tous des cotes inférieures au juste prix. Mieux vaut ne pas jouer que jouer à perte.</p>}
          </section>
        )}

        <section className="panel">
          <h2>Victoires les plus sûres</h2>
          <p className="lede">
            Favoris à 70&nbsp;% ou plus.
            {s.safe_picks?.n ? ` Cette saison, ${s.safe_picks.correct} sur ${s.safe_picks.n} ont gagné (${num((s.safe_picks.correct / s.safe_picks.n) * 100)}\u00a0%).` : ''}
          </p>
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
            <li><b>Les cotes du marché sont le meilleur prédicteur disponible.</b> Elles intègrent déjà la forme, les blessures, l’avantage du terrain et la météo. Sur 899 matchs, aucun mélange avec notre modèle n’a fait mieux que les cotes seules (score de Brier 0,213 contre 0,215) : l’écart est faible, mais rien ne justifie de s’en écarter.</li>
            <li><b>La forme récente et l’historique des confrontations n’apportent rien de plus.</b> Utiles seuls, ils ne prédisent presque rien une fois les cotes connues (corrélation inférieure à 0,04 avec l’écart restant).</li>
            <li><b>La marge des bookmakers est retirée par la méthode de Shin.</b> Avec deux issues, elle donne presque les mêmes probabilités que la méthode simple.
              {dv?.shin && ` Sur ${dv.games.toLocaleString('fr-FR')} matchs depuis 2012, les outsiders sous 25\u00a0% sont annoncés à ${fr1(dv.shin.dog_pred)}\u00a0% et gagnent ${fr1(dv.shin.dog_actual)}\u00a0% du temps (méthode simple : ${fr1(dv.prop.dog_pred)}\u00a0% annoncés, ${fr1(dv.prop.dog_actual)}\u00a0% réels).`}
            </li>
            {st.spread_sd && (
              <li><b>Un écart de points se convertit en probabilité avec un écart-type d’environ {num(st.spread_sd.best_sd, 2)} points</b>, mesuré sur {st.spread_sd.games.toLocaleString('fr-FR')} matchs depuis 2016. Nous utilisons 11,5 pour le modèle maison et la simulation des playoffs.</li>
            )}
            <li><b>Ne misez jamais beaucoup, même sur une bonne occasion.</b> La mise prudente indiquée correspond à un quart du critère de Kelly, plafonnée à 2&nbsp;% du budget : assez pour profiter d’un avantage, sans risquer de tout perdre sur une série défavorable.</li>
            <li><b>L’avantage du terrain ne vaut plus qu’environ 1,5 point</b>, contre 3 il y a quinze ans. Il est déjà pris en compte par les bookmakers.</li>
            <li><b>Le quarterback titulaire est le facteur individuel le plus important.</b> Un changement de dernière minute peut faire basculer un match : vérifiez toujours les annonces avant de jouer. Si le quarterback prévu est forfait, nous prenons le suivant dans la hiérarchie de l’équipe.</li>
            <li>
              <b>Buteurs : le modèle suit chaque joueur match par match.</b> Il regarde ses courses et ses cibles près de l’en-but,
              son temps de jeu, ses touchdowns, son statut médical et la composition de l’équipe (la part d’un forfait est
              redistribuée à ses coéquipiers du même poste). Il se réajuste à chaque mise à jour
              {sm?.train_rows ? ` sur ${sm.train_rows.toLocaleString('fr-FR')} prédictions passées` : ''}.
              Vérifié sur 375 matchs qu’il n’avait jamais vus (2025 et 2026), son buteur n°1 de chaque match a marqué 48,0&nbsp;% du temps,
              contre 42,9&nbsp;% avec l’ancien calcul : amélioration probable, à confirmer par le suivi réel (page Bilan).
            </li>
            <li>
              <b>Nous ne proposons pas de paris contre l’écart (handicap).</b> Quand notre modèle s’éloigne des bookmakers d’au moins 3 points,
              il a eu raison dans 46,7&nbsp;% des cas sur 210 matchs depuis 2023, avec une marge d’erreur de 40 à 53&nbsp;%
              {s.ats_games ? ` (${s.ats_correct} sur ${s.ats_games} cette saison)` : ''}. Aucun avantage démontré, alors qu’il faut 52,4&nbsp;% pour gagner de l’argent.
            </li>
            {wn && (
              <li>
                <b>Le vent fort réduit le nombre de points</b> : depuis 2012, avec un vent observé de 19 km/h ou plus, le total est passé sous la ligne {fr1(wn.observed.under)}&nbsp;% du temps ({wn.observed.n} matchs, ±{fr1(wn.observed.ci)} points ; {st.wind_observed.periods.map((x) => `${x.label} : ${fr1(x.under)}\u00a0%`).join(', ')}).
                {wn.forecast
                  ? ` Avec le vent prévu (archive Open-Meteo depuis ${wn.forecast.since}) : ${fr1(wn.forecast.windy.under)}\u00a0% sur ${wn.forecast.windy.n} matchs (±${fr1(wn.forecast.windy.ci)}).`
                  : ' L’effet avec le vent prévu est en cours de mesure.'}
                {wn.validated
                  ? ' L’effet est assez net pour être signalé sur les matchs venteux.'
                  : ' Il n’est pas encore assez net pour un pronostic : les matchs venteux sont signalés et suivis dans le bilan.'}
              </li>
            )}
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
