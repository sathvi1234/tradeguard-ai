'use client';

import Link from 'next/link';
import LandingBackdrop from '@/components/landing/LandingBackdrop';
import LandingChart from '@/components/landing/LandingChart';
import { chartStatus, quoteCard, type Dict } from '@/components/landing/landingData';
import { money, pct } from '@/lib/format';
import { freshnessLabel, marketStatusHeadline, priceLabel } from '@/lib/marketState';

export default function LandingHero({
  featured,
  loading,
  error,
  liveMarketData,
}: {
  featured: Dict | null;
  loading: boolean;
  error: unknown;
  liveMarketData: boolean;
}) {
  const quote = quoteCard(featured, 'AAPL');
  const status = chartStatus(quote.state, quote.bars, loading, error);
  const changeClass = quote.change === null ? '' : quote.change >= 0 ? 'lp-up' : 'lp-down';
  const unavailable =
    status.kind === 'error' ||
    status.kind === 'unavailable' ||
    (status.kind !== 'loading' && (!quote.state.quoteAvailable || quote.state.price === null));

  return (
    <section className="lp-hero" aria-label="Trade AI hero">
      <LandingBackdrop />
      <div className="lp-hero-glow" aria-hidden="true" />

      <header className="lp-nav">
        <div className="lp-brand">
          <span className="lp-mark" aria-hidden="true">
            TA
          </span>
          <div>
            <p className="lp-logo">Trade AI</p>
            <p className="lp-tag">Mentor &amp; simulator</p>
          </div>
        </div>
        <nav className="lp-links" aria-label="Landing">
          <a href="#market">Product</a>
          <a href="#how-it-works">Practice</a>
          <a href="#safety">Safety</a>
          <Link href="/signin">Start Demo</Link>
        </nav>
        <Link href="/signin" className="lp-btn lp-btn-solid">
          Start Demo
        </Link>
      </header>

      <div className="lp-hero-grid">
        <div className="lp-hero-copy">
          <p className="lp-kicker">Educational paper trading</p>
          <h1>Trade Smarter. Learn Faster. Stay in Control.</h1>
          <p className="lp-lede">
            Trade AI is an intelligent trading mentor and paper-trading simulator powered by real market data,
            multi-agent analysis, and deterministic risk controls.
          </p>
          <div className="lp-actions">
            <Link href="/signin" className="lp-btn lp-btn-solid">
              Start Demo
            </Link>
            <a href="#market" className="lp-btn lp-btn-ghost">
              Explore Trade AI
            </a>
          </div>
          <ul className="lp-pills" aria-label="Safety status">
            <li className={liveMarketData ? 'lp-pill lp-pill-live' : 'lp-pill'}>
              {liveMarketData ? 'LIVE MARKET DATA' : 'MARKET DATA STATUS UNKNOWN'}
            </li>
            <li className="lp-pill lp-pill-demo">DEMO MONEY</li>
            <li className="lp-pill lp-pill-sim">SIMULATION ONLY</li>
            <li className="lp-pill lp-pill-off">REAL-MONEY TRADING OFF</li>
          </ul>
        </div>

        <aside className="lp-terminal" aria-label="Live market terminal from the market-data API">
          <div className="lp-terminal-head">
            <div>
              <p className="lp-kicker">LIVE MARKET DATA</p>
              <p className="lp-kicker">{quote.state.symbol || 'AAPL'}</p>
              <p className="lp-price">
                {status.kind === 'loading'
                  ? 'Loading…'
                  : unavailable
                    ? 'Market data unavailable'
                    : priceLabel(quote.state)}
              </p>
              <p className={`lp-change ${changeClass}`}>
                {unavailable || quote.change === null
                  ? 'Change not available'
                  : `${quote.change >= 0 ? '+' : ''}${money(quote.change)}`}
                {unavailable || quote.changePct === null ? '' : ` · ${pct(quote.changePct)}`}
              </p>
            </div>
            <div className="lp-terminal-flags">
              <span className={liveMarketData ? 'lp-dot live' : 'lp-dot'}>{liveMarketData ? 'LIVE MARKET DATA' : 'QUOTE FEED'}</span>
              <span className="lp-dot demo">DEMO MONEY</span>
              <span className="lp-dot off">REAL-MONEY TRADING OFF</span>
            </div>
          </div>
          <p className="lp-meta">
            Session {marketStatusHeadline(quote.state)} · {quote.state.session} · {freshnessLabel(quote.state)}
          </p>
          <p className="lp-note">Real quotes and bars from the market-data API. The animated background is decorative only.</p>
          {status.kind === 'loading' ? (
            <div className="lp-skeleton" aria-hidden="true" />
          ) : (
            <LandingChart series={quote.bars} height={280} label={status.message} empty={unavailable ? 'Market data unavailable' : status.message} />
          )}
        </aside>
      </div>
    </section>
  );
}
