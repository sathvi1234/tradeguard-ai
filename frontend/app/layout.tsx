import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import DemoProvider from '@/components/DemoProvider';
import AppFrame from '@/components/AppFrame';
import { MarketStreamProvider } from '@/components/MarketStreamProvider';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Trade AI — AI Trading Mentor & Simulator',
  description: 'Learn how markets work. Simulate trades. Understand risk. Educational paper-trading simulator — not guaranteed-profit software.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-background text-foreground`}>
        <DemoProvider>
          <MarketStreamProvider>
            <AppFrame>{children}</AppFrame>
          </MarketStreamProvider>
        </DemoProvider>
      </body>
    </html>
  );
}