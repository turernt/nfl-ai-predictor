import { Topbar, Footer } from '../ui';

export const metadata = { title: 'Mentions légales', robots: { index: false } };

export default function Mentions() {
  return (
    <>
      <Topbar />
      <main className="wrap narrow legal">
        <h1>Mentions légales</h1>

        <h2>Éditeur</h2>
        <p>
          Arthur Analytics est un site personnel édité à titre non professionnel par une personne physique, qui a
          communiqué ses coordonnées à l’hébergeur conformément à l’article 6 de la loi n° 2004-575 du 21 juin 2004
          pour la confiance dans l’économie numérique. Contact : via la page « Issues » du dépôt public GitHub
          {' '}<a href="https://github.com/turernt/nfl-ai-predictor/issues">turernt/nfl-ai-predictor</a>.
        </p>

        <h2>Hébergeur</h2>
        <p>Vercel Inc., 440 N Barranca Avenue #4133, Covina, CA 91723, États-Unis. vercel.com</p>

        <h2>Nature du contenu</h2>
        <p>
          Les probabilités, pronostics et analyses publiés sont des estimations statistiques fournies à titre
          informatif. Ils ne constituent ni un conseil en paris, ni une garantie de résultat. Le site ne propose
          aucun pari, ne perçoit aucune commission et ne contient aucun lien d’affiliation vers un opérateur de jeux.
        </p>
        <p>
          <b>Jouer comporte des risques : endettement, isolement, dépendance.</b> Pour être aidé, appelez le
          09 74 75 13 13 (appel non surtaxé). Les jeux d’argent sont interdits aux mineurs. En France, seuls les
          opérateurs agréés par l’Autorité nationale des jeux (ANJ) sont autorisés.
        </p>

        <h2>Données et marques</h2>
        <p>
          Statistiques : nflverse (nflreadpy). Cotes : lignes publiées par nflverse et, le cas échéant, The Odds API.
          Météo : Open-Meteo. Les noms, logos et photos des équipes et joueurs sont la propriété de la NFL, de ses clubs
          et de leurs ayants droit. Ce site n’est ni affilié ni approuvé par la NFL.
        </p>

        <h2>Données personnelles et cookies</h2>
        <p>
          Le site ne dépose aucun cookie, ne contient aucun outil de mesure d’audience et ne collecte aucune donnée
          personnelle. Les journaux techniques éventuellement conservés par l’hébergeur relèvent de sa propre politique
          de confidentialité.
        </p>
      </main>
      <Footer />
    </>
  );
}
