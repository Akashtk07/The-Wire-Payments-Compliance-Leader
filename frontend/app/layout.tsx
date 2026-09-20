import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import ConditionalLayout from '@/components/ConditionalLayout';
import { AuthProvider } from '@/lib/AuthProvider';

const inter = Inter({
  subsets: ['latin'],
  weight: ['100', '200', '300', '400', '500', '600', '700', '800', '900'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'The Compliance Leader | ISO 20022 Enterprise Platform',
  description:
    'Production-grade cross-border regulatory lineage, translation validation, document intelligence & real-time telemetry platform',
  keywords: [
    'ISO 20022',
    'SWIFT CBPR+',
    'compliance',
    'wire payment',
    'MT to MX',
    'financial messaging',
  ],
  authors: [{ name: 'The Compliance Leader' }],
  robots: 'noindex, nofollow',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable} style={{ width: '100%', height: '100%' }}>
      <body style={{ width: '100%', height: '100%', margin: 0, padding: 0 }}>
        <AuthProvider>
          <div className="bg-orb bg-orb-1" aria-hidden="true" />
          <div className="bg-orb bg-orb-2" aria-hidden="true" />
          <ConditionalLayout>{children}</ConditionalLayout>
        </AuthProvider>
      </body>
    </html>
  );
}
