'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useAlpacaStatus, useDataQuality, useHealth } from '@/hooks/useApi';
import DemoBanner from '@/components/DemoBanner';
import DemoBadges from '@/components/DemoBadges';
import VoiceAlert from '@/components/VoiceAlert';
import DataQualityIndicator from '@/components/DataQualityIndicator';

const PUBLIC = new Set(['/', '/signin']);

const NAV = [
  { href: '/dashboard', label: 'Overview' },
  { href: '/stocks', label: 'Stocks' },
  { href: '/stock-analytics', label: 'Stock Analytics' },
  { href: '/portfolio', label: 'Portfolio' },
  { href: '/trade-history', label: 'Trade History' },
  { href: '/ai-debate', label: 'AI Debate' },
  { href: '/market-intelligence', label: 'Market Intelligence' },
  { href: '/risk-center', label: 'Risk Center' },
  { href: '/trade-simulator', label: 'Trade Simulator' },
  { href: '/backtest-lab', label: 'Backtest Lab' },
  { href: '/falsification-lab', label: 'Falsification Lab' },
  { href: '/volatility-lab', label: 'Volatility Lab' },
  { href: '/ai-review', label: 'AI Review' },
  { href: '/copilot', label: 'Quant Copilot' },
  { href: '/learn', label: 'Learning' },
  { href: '/activity-log', label: 'Activity' },
  { href: '/call-agent', label: 'Call Agent' },
  { href: '/autonomous', label: 'Autonomous Control' },
];

function navActive(pathname: string, href: string): boolean {
  const path = href.split('#')[0];
  if (path === '/dashboard') return pathname === '/dashboard' && !href.includes('#');
  if (path === '/stocks') return pathname.startsWith('/stocks');
  if (path === '/trade-history') return pathname.startsWith('/trade-history');
  if (path === '/call-agent') return pathname.startsWith('/call-agent');
  if (path === '/stock-analytics') return pathname.startsWith('/stock-analytics');
  if (path === '/market-intelligence') return pathname.startsWith('/market-intelligence');
  if (path === '/trade-simulator') return pathname.startsWith('/trade-simulator');
  if (path === '/backtest-lab') return pathname.startsWith('/backtest-lab');
  if (path === '/falsification-lab') return pathname.startsWith('/falsification-lab');
  if (path === '/volatility-lab') return pathname.startsWith('/volatility-lab');
  if (path === '/ai-review') return pathname.startsWith('/ai-review');
  if (path === '/learn/simulator') return pathname.startsWith('/learn/simulator');
  if (path === '/learn') return pathname.startsWith('/learn') && !pathname.startsWith('/learn/simulator');
  return pathname === path || pathname.startsWith(`${path}/`);
}

export default function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || '/';
  const publicPage = PUBLIC.has(pathname);
  const { user, ready, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState(false);
  const { health, error: healthError } = useHealth();
  const { alpaca, error: alpacaError } = useAlpacaStatus();
  const { quality } = useDataQuality('SPY');

  useEffect(() => {
    if (!publicPage && ready && !user) {
      router.replace('/signin');
    }
  }, [publicPage, ready, user, router]);

  if (publicPage) {
    return <>{children}</>;
  }

  if (!ready || !user) {
    return <div className="min-h-screen bg-background" />;
  }

  const backendOk = !healthError && health?.status === 'healthy';
  const alpacaOk = !alpacaError && Boolean(alpaca?.connected && alpaca?.authenticated);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <DemoBanner />
      <header className="sticky top-0 z-40 border-b border-line bg-background backdrop-blur">
        <div className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold tracking-tight text-foreground">TRADE AI</p>
              <p className="text-[11px] text-muted">AI Trading Mentor & Simulator</p>
            </div>
            <button
              type="button"
              className="rounded-full border border-line px-3 py-1 text-xs text-foreground lg:hidden"
              onClick={() => setOpen((v) => !v)}
            >
              Menu
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wide">
            <DemoBadges alpacaOk={alpacaOk} liveMarketData={Boolean((health as { live_market_data?: boolean } | undefined)?.live_market_data)} />
            <DataQualityIndicator quality={quality} />
            <span className="flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-1 text-muted">
              <span className={`h-1.5 w-1.5 rounded-full ${backendOk ? 'bg-success' : 'bg-danger'}`} />
              Backend {backendOk ? 'Connected' : 'Offline'}
            </span>
          </div>
          <div className="relative flex items-center gap-2">
            <button
              type="button"
              onClick={() => setProfile((v) => !v)}
              className="rounded-xl border border-line bg-surface px-3 py-1.5 text-left text-xs"
            >
              <p className="font-semibold text-foreground">{user.name}</p>
              <p className="text-[10px] text-muted">Profile</p>
            </button>
            <button
              type="button"
              onClick={() => {
                logout();
                router.push('/');
              }}
              className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-foreground hover:border-primary hover:text-primary"
            >
              Sign Out
            </button>
            {profile ? (
              <div className="absolute right-0 top-12 z-50 w-64 rounded-xl border border-line bg-surface p-4 text-xs shadow-lift">
                <p className="font-semibold text-foreground">Profile</p>
                <p className="mt-2 text-muted">{user.name}</p>
                <p className="text-muted-foreground">{user.email}</p>
                <p className="mt-2 text-warning">PAPER / DRY_RUN · REAL-MONEY TRADING OFF</p>
                <p className="mt-2 text-muted-foreground">Hackathon demo session. No broker credentials stored here.</p>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <div className="flex">
        <aside
          className={`${open ? 'block' : 'hidden'} w-full shrink-0 border-b border-line bg-background lg:block lg:w-56 lg:border-b-0 lg:border-r`}
        >
          <nav className="flex flex-col gap-1 p-3">
            {NAV.map((item) => {
              const active = navActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`rounded-lg px-3 py-2 text-sm ${
                    active
                      ? 'bg-primary-soft font-semibold text-primary'
                      : 'text-muted hover:bg-surface hover:text-primary'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>
        <div className="min-w-0 flex-1 overflow-x-hidden pb-24">{children}</div>
      </div>
      <VoiceAlert />
    </div>
  );
}
