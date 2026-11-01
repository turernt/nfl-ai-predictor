import '@fontsource/barlow/400.css';
import '@fontsource/barlow/500.css';
import '@fontsource/barlow-condensed/600.css';
import '@fontsource/barlow-condensed/700.css';
import './globals.css';

export const metadata = {
  metadataBase: new URL(process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'http://localhost:3000'),
  title: { default: 'Arthur Analytics, prédictions NFL', template: '%s | Arthur Analytics' },
  description: 'Probabilités de victoire, scores projetés et buteurs probables pour chaque match NFL, recalculés chaque semaine.',
  openGraph: { siteName: 'Arthur Analytics', locale: 'fr_FR', type: 'website' },
};

export const viewport = { themeColor: '#0f1b2d' };

export default function RootLayout({ children }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
