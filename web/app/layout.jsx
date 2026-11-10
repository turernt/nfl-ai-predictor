import '@fontsource/barlow/400.css';
import '@fontsource/barlow/500.css';
import '@fontsource/barlow-condensed/600.css';
import '@fontsource/barlow-condensed/700.css';
import './globals.css';
import data from '../data/predictions.json';
import StaleBanner from './StaleBanner';

export const metadata = {
  metadataBase: new URL(process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'http://localhost:3000'),
  title: { default: 'Arthur Analytics, prédictions NFL', template: '%s | Arthur Analytics' },
  description: 'Probabilités de victoire, scores projetés et buteurs probables pour chaque match NFL, recalculés chaque semaine.',
  openGraph: { siteName: 'Arthur Analytics', locale: 'fr_FR', type: 'website' },
  // Usage personnel : le site n'est pas proposé aux moteurs de recherche
  robots: { index: false, follow: false },
};

export const viewport = { themeColor: '#0f1b2d' };

export default function RootLayout({ children }) {
  return (
    <html lang="fr">
      <body>
        <StaleBanner at={data.generated_at} />
        {children}
      </body>
    </html>
  );
}
