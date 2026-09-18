'use client';

import Link from 'next/link';
import {
  Activity,
  BookOpen,
  Brain,
  History,
  LineChart,
  MessageSquare,
  Mic,
  Radar,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Swords,
  TrendingUp,
  Lock,
} from 'lucide-react';
import LandingChart from '@/components/landing/LandingChart';
import LandingHero from '@/components/landing/LandingHero';
import { asDict, asNum, chartStatus, quoteCard, type Dict } from '@/components/landing/landingData';
import {
  useDemoOrders,
  useDemoPortfolio,
  useDemoPositions,
  useGreeks,
  useHealth,
  useOptions,
  useWatchlist,
} from '@/hooks/useApi';
import { money, pct } from '@/lib/format';
import { freshnessLabel, greeksDisplay, greeksState, marketStatusHeadline, priceLabel } from '@/lib/marketState';

const MARKET_SYMBOLS = ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'GOOGL'];

const AGENTS = [
  { name: 'Market Scout', body: 'Reads available quotes, session, and freshness. Never invents a tape.' },
  { name: 'Strategy Brain', body: 'Frames an educational strategy from listed facts only.' },
  { name: 'Bull Agent', body: 'Builds a bullish case from available data. Missing inputs stay missing.' },
  { name: 'Bear Agent', body: 'Stresses the downside without fabricating catalysts.' },
  { name: 'Red Team Critic', body: 'Attacks the thesis so weak assumptions do not pass as facts.' },
  { name: 'Decision Agent', body: 'Produces a recommendation. It cannot authorize execution.' },
  { name: 'Risk Guardian', body: 'Deterministic final authority. AI cannot override this gate.' },
];

const PIPELINE = [
  'Market Data',
  'Market Scout',
  'Strategy Brain',
  'Bull / Bear',
  'Red Team Critic',
  'Decision Agent',
  'Risk Guardian',
  'Simulation',
];

const FEATURES = [
  { href: '/dashboard', title: 'AI Trading Mentor', body: 'Explains markets, options, Greeks, and risk in plain language.', icon: Sparkles },
  { href: '/ai-debate', title: 'Multi-Agent Debate', body: 'Bull, Bear, Strategy, and Red Team analyze the same scenario.', icon: Swords },
  { href: '/market-intelligence', title: 'Real Market Intelligence', body: 'Price, session, and freshness from Alpaca paper market data.', icon: Radar },
  { href: '/stock-analytics', title: 'Stock Analytics', body: 'Indicators only from available bars. Gaps stay marked, not filled.', icon: LineChart },
  { href: '/stock-analytics', title: 'Options Analysis', body: 'Contracts, IV, and Greeks only when the options snapshot provides them.', icon: Activity },
  { href: '/risk-center', title: 'Risk Guardian', body: 'Deterministic engine. AI cannot override the final decision.', icon: Shield },
  { href: '/trade-simulator', title: 'Paper Trading Simulator', body: 'Virtual buys and sells. Never a live broker order.', icon: Scale },
  { href: '/copilot', title: 'AI Quant Copilot', body: 'Ask about portfolio, risk, and debates. Copilot never executes.', icon: MessageSquare },
  { href: '/call-agent', title: 'AI Voice Alerts', body: 'Simulated browser speech. No real phone call.', icon: Mic },
  { href: '/learn', title: 'Learning Platform', body: 'Lessons and a classroom what-if simulator.', icon: BookOpen },
  { href: '/trade-history', title: 'Trade History', body: 'Review Demo User simulated fills and activity.', icon: History },
  { href: '/ai-review', title: 'AI Review', body: 'Restricted LLM review after Risk Guardian. Advisory only.', icon: Brain },
];

function Change({ change, changePct }: { change: number | null; changePct: number | null }) {
  if (change === null && changePct === null) return <span>Change not available</span>;
  const up = (change ?? 0) >= 0;
  return (
    <span className={up ? 'lp-up' : 'lp-down'}>
      {change === null ? '—' : `${change >= 0 ? '+' : ''}${money(change)}`}
      {changePct === null ? '' : ` (${pct(changePct)})`}
    </span>
  );
}

export default function LandingExperience() {
  const { items, isLoading, error, liveMarketData } = useWatchlist(MARKET_SYMBOLS);
  const { health } = useHealth();
  const { portfolio, isLoading: portLoading, error: portError } = useDemoPortfolio();
  const { positions, isLoading: posLoading } = useDemoPositions();
  const { orders, isLoading: orderLoading } = useDemoOrders();
  const { greeks, isLoading: greeksLoading, error: greeksError } = useGreeks();
  const { options, isLoading: optionsLoading, error: optionsError } = useOptions('AAPL');

  const aaplRaw =
    (items as Dict[]).find((item) => String(asDict(item).symbol || '').toUpperCase() === 'AAPL') || null;
  const quotes = MARKET_SYMBOLS.map((symbol) => {
    const row = (items as Dict[]).find((item) => String(asDict(item).symbol || '').toUpperCase() === symbol);
    return { symbol, ...quoteCard(row, symbol) };
  });
  const featured = quotes[0];
  const live = liveMarketData || Boolean((health as Dict | undefined)?.live_market_data);
  const chart = chartStatus(featured.state, featured.bars, isLoading, error);
  const port = asDict(portfolio);
  const greeksKind = greeksState(greeks, greeksError);
  const optionRows = Array.isArray(asDict(options).contracts)
    ? (asDict(options).contracts as unknown[])
    : Array.isArray(options)
      ? (options as unknown[])
      : [];
  const iv = asNum(asDict(options).implied_volatility ?? asDict(asDict(options).snapshot).implied_volatility);

  const sortedOrders = [...orders].sort((a, b) => {
    const left = String(asDict(a).timestamp || asDict(a).created_at || '');
    const right = String(asDict(b).timestamp || asDict(b).created_at || '');
    return left.localeCompare(right);
  });
  const tradePoints = sortedOrders.map((row, index) => {
    const item = asDict(row);
    const stamp = String(item.timestamp || item.created_at || item.filled_at || '');
    return { t: stamp ? stamp.slice(0, 16).replace('T', ' ') : `Trade ${index + 1}`, price: index + 1 };
  });

  return (
    <div className="lp">
      <LandingHero featured={aaplRaw} loading={isLoading} error={error} liveMarketData={live} />

      <section className="lp-story" aria-label="Product story">
        <div className="lp-wrap lp-story-row">
          {['REAL MARKET DATA', 'AI ANALYSIS', 'MULTI-AGENT DEBATE', 'RISK VALIDATION', 'SAFE SIMULATION', 'LEARN'].map(
            (step, index) => (
              <span key={step} className="lp-story-step">
                {step}
                {index < 5 ? <span aria-hidden="true">↓</span> : null}
              </span>
            )
          )}
        </div>
      </section>

      <section id="market" className="lp-section">
        <div className="lp-wrap">
          <p className="lp-kicker">Market tape</p>
          <h2>Real Market Intelligence</h2>
          <p className="lp-section-copy">Quotes and session status from the existing Alpaca market-data API. Prices are never invented.</p>
          {isLoading && items.length === 0 ? (
            <div className="lp-grid-5">
              {MARKET_SYMBOLS.map((symbol) => (
                <div key={symbol} className="lp-card lp-skeleton-card" aria-hidden="true" />
              ))}
            </div>
          ) : error && items.length === 0 ? (
            <p className="lp-banner">Market data unavailable</p>
          ) : (
            <div className="lp-grid-5">
              {quotes.map((card) => (
                <article key={card.symbol} className="lp-card">
                  <p className="lp-card-kicker">{card.symbol}</p>
                  <p className="lp-card-value">{priceLabel(card.state)}</p>
                  <p className="lp-card-meta">
                    <Change change={card.change} changePct={card.changePct} />
                  </p>
                  <p className="lp-card-meta">
                    {marketStatusHeadline(card.state)} · {card.state.session} · {freshnessLabel(card.state)}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="movement">
        <div className="lp-wrap lp-chart-layout">
          <div className="lp-chart-main">
            <p className="lp-kicker">{featured.state.symbol || 'AAPL'}</p>
            <h2>Market Movement</h2>
            <p className="lp-section-copy">Explore real market data before placing a simulated trade.</p>
            <p className="lp-price">{priceLabel(featured.state)}</p>
            {chart.kind === 'loading' ? (
              <div className="lp-skeleton" style={{ minHeight: 360 }} />
            ) : (
              <LandingChart series={featured.bars} height={380} label={chart.message} empty={chart.message} />
            )}
          </div>
          <aside className="lp-card lp-chart-side">
            <p className="lp-card-kicker">Quote board</p>
            <dl className="lp-dl">
              <div>
                <dt>Current price</dt>
                <dd>{priceLabel(featured.state)}</dd>
              </div>
              <div>
                <dt>Change</dt>
                <dd>
                  <Change change={featured.change} changePct={featured.changePct} />
                </dd>
              </div>
              <div>
                <dt>Session</dt>
                <dd>{featured.state.session}</dd>
              </div>
              <div>
                <dt>Freshness</dt>
                <dd>{freshnessLabel(featured.state)}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{featured.state.source}</dd>
              </div>
            </dl>
            <p className="lp-note">Historical series uses Alpaca daily bars returned by the market-data API. Missing history is not synthesized.</p>
          </aside>
        </div>
      </section>

      <section className="lp-section" id="intelligence">
        <div className="lp-wrap">
          <p className="lp-kicker">Multi-agent architecture</p>
          <h2>AI Trading Intelligence</h2>
          <p className="lp-section-copy">
            AI agents provide analysis and recommendations. The deterministic Risk Guardian remains the final authority.
          </p>
          <div className="lp-pipeline" aria-label="Analysis pipeline">
            {PIPELINE.map((step, index) => (
              <span key={step} className="lp-pipe-wrap">
                <span className={step === 'Risk Guardian' ? 'lp-pipe lp-pipe-final' : 'lp-pipe'}>
                  {step === 'Risk Guardian' ? 'Risk Guardian · FINAL AUTHORITY' : step}
                </span>
                {index < PIPELINE.length - 1 ? (
                  <span className="lp-pipe-link" aria-hidden="true">
                    <span className="lp-pipe-dot" />
                  </span>
                ) : null}
              </span>
            ))}
          </div>
          <div className="lp-grid-4">
            {AGENTS.map((agent) => (
              <article key={agent.name} className={agent.name === 'Risk Guardian' ? 'lp-card lp-card-final' : 'lp-card'}>
                <h3>{agent.name === 'Risk Guardian' ? 'Risk Guardian — Final Authority' : agent.name}</h3>
                <p>{agent.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="demo">
        <div className="lp-wrap">
          <p className="lp-kicker">Demo User</p>
          <h2>Portfolio / Simulation Preview</h2>
          <div className="lp-pills">
            <span className="lp-pill">DEMO MONEY</span>
            <span className="lp-pill">SIMULATION ONLY</span>
            <span className="lp-pill lp-pill-off">REAL-MONEY TRADING OFF</span>
          </div>
          {portError ? (
            <p className="lp-banner">Demo portfolio is unavailable right now. Virtual balances were not invented.</p>
          ) : (
            <div className="lp-grid-5">
              <article className="lp-card">
                <p className="lp-card-kicker">Virtual Cash</p>
                <p className="lp-card-value">{portLoading ? 'Loading…' : money(port.cash)}</p>
              </article>
              <article className="lp-card">
                <p className="lp-card-kicker">Portfolio Value</p>
                <p className="lp-card-value">{portLoading ? 'Loading…' : money(port.portfolio_value ?? port.equity)}</p>
              </article>
              <article className="lp-card">
                <p className="lp-card-kicker">Positions</p>
                <p className="lp-card-value">{posLoading ? 'Loading…' : String(positions.length)}</p>
              </article>
              <article className="lp-card">
                <p className="lp-card-kicker">Today&apos;s P&amp;L</p>
                <p className="lp-card-value">{portLoading ? 'Loading…' : money(port.daily_pnl ?? port.unrealized_pnl)}</p>
              </article>
              <article className="lp-card">
                <p className="lp-card-kicker">Trade Count</p>
                <p className="lp-card-value">{orderLoading ? 'Loading…' : String(orders.length)}</p>
              </article>
            </div>
          )}
        </div>
      </section>

      <section className="lp-section" id="performance">
        <div className="lp-wrap">
          <p className="lp-kicker">Demo User activity</p>
          <h2>Track Your Trading Journey</h2>
          <p className="lp-section-copy">Cumulative simulated trade count from the Demo User ledger. Performance is not fabricated.</p>
          {orderLoading && orders.length === 0 ? (
            <div className="lp-skeleton" style={{ minHeight: 280 }} />
          ) : tradePoints.length < 2 ? (
            <div className="lp-empty">
              <p>Your performance graph will appear after you make simulated trades.</p>
            </div>
          ) : (
            <LandingChart
              series={tradePoints}
              height={300}
              format="count"
              label="Cumulative Demo User simulated trades"
              empty="Your performance graph will appear after you make simulated trades."
            />
          )}
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="options">
        <div className="lp-wrap">
          <p className="lp-kicker">Derivatives</p>
          <h2>Options Analysis</h2>
          <div className="lp-grid-5">
            <article className="lp-card">
              <p className="lp-card-kicker">Options contracts</p>
              <p className="lp-card-value">
                {optionsLoading ? 'Loading…' : optionsError ? 'Options snapshot unavailable' : String(asNum(asDict(options).count) ?? optionRows.length)}
              </p>
            </article>
            <article className="lp-card">
              <p className="lp-card-kicker">Implied volatility</p>
              <p className="lp-card-value">{iv === null ? 'IV not available' : pct(iv)}</p>
            </article>
            <article className="lp-card">
              <p className="lp-card-kicker">Greeks</p>
              <p className="lp-card-value">
                {greeksLoading
                  ? 'Loading…'
                  : greeksKind === 'NO_OPTION_POSITIONS'
                    ? 'No option positions yet'
                    : `Δ ${greeksDisplay(greeks, asDict(greeks).delta)}`}
              </p>
            </article>
            <article className="lp-card">
              <p className="lp-card-kicker">Strategy analysis</p>
              <p className="lp-card-value">Educational only</p>
              <p className="lp-card-meta">Run Stock Analytics for contract-level detail from Alpaca.</p>
            </article>
            <article className="lp-card">
              <p className="lp-card-kicker">Risk assessment</p>
              <p className="lp-card-value">Risk Guardian</p>
              <p className="lp-card-meta">Deterministic limits stay in charge of any simulated order.</p>
            </article>
          </div>
          {greeksKind === 'NO_OPTION_POSITIONS' ? <p className="lp-note">No option positions yet</p> : null}
        </div>
      </section>

      <section className="lp-section" id="copilot">
        <div className="lp-wrap lp-split">
          <div>
            <p className="lp-kicker">Quant Copilot</p>
            <h2>Ask Your AI Trading Mentor</h2>
            <p className="lp-section-copy">Explanatory only. Copilot cannot execute orders or override Risk Guardian.</p>
            <Link href="/copilot" className="lp-btn lp-btn-solid">
              Try AI Copilot
            </Link>
          </div>
          <ul className="lp-questions">
            <li>Why did the system reject this trade?</li>
            <li>What is the current market risk?</li>
            <li>Explain this option strategy.</li>
            <li>How does the Risk Guardian work?</li>
          </ul>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="voice">
        <div className="lp-wrap lp-split">
          <div className="lp-voice" aria-hidden="true">
            <Mic className="lp-mic" />
            <span className="lp-voice-ring" />
          </div>
          <div>
            <p className="lp-kicker">Simulated speech</p>
            <h2>AI Voice Alerts</h2>
            <p className="lp-section-copy">
              Trade AI can provide simulated voice alerts for risk warnings, trade decisions, market conditions, and
              portfolio events. Browser speech only — no real phone call.
            </p>
            <Link href="/call-agent" className="lp-btn lp-btn-ghost">
              Open Call Agent
            </Link>
          </div>
        </div>
      </section>

      <section className="lp-section" id="safety">
        <div className="lp-wrap">
          <p className="lp-kicker">Controls</p>
          <h2>Built With Safety at the Core</h2>

          <article className="lp-llm-card">
            <div className="lp-llm-head">
              <ShieldCheck aria-hidden="true" />
              <Lock aria-hidden="true" />
              <h3>Restricted AI Reviewer</h3>
            </div>
            <p className="lp-llm-statement">
              LLM may only return VETO, SHRINK, or NO_CHANGE. It cannot approve a blocked trade, increase size, override
              risk limits, stale data, MARKET_CLOSED, or CRITICAL drawdown, execute orders, or access Alpaca credentials.
            </p>
            <p className="lp-note">AI review is advisory only. Risk Guardian remains the final deterministic authority.</p>
            <ul className="lp-llm-list">
              <li>LLM cannot approve blocked trades</li>
              <li>LLM cannot increase position size</li>
              <li>LLM cannot override risk limits</li>
              <li>LLM cannot override stale market data protection</li>
              <li>LLM cannot override MARKET_CLOSED</li>
              <li>LLM cannot override CRITICAL drawdown protection</li>
              <li>LLM cannot execute orders</li>
              <li>LLM cannot access Alpaca credentials</li>
            </ul>
          </article>

          <div className="lp-safety-board">
            <div className="lp-pills" aria-label="System status">
              <span className="lp-pill lp-pill-live">LIVE MARKET DATA</span>
              <span className="lp-pill lp-pill-demo">DEMO MONEY</span>
              <span className="lp-pill lp-pill-sim">SIMULATION ONLY</span>
              <span className="lp-pill lp-pill-off">REAL-MONEY TRADING OFF</span>
            </div>
            <ul className="lp-checks">
              <li>AI advisory analysis</li>
              <li>Deterministic Risk Guardian</li>
              <li>Restricted LLM Reviewer</li>
              <li>Drawdown Guardian</li>
              <li>Demo virtual money</li>
              <li>DRY_RUN enabled</li>
              <li>Real-money trading OFF</li>
            </ul>
          </div>

          <div className="lp-grid-4">
            <article className="lp-card">
              <Radar />
              <h3>LIVE MARKET DATA</h3>
              <p>Real market information can be displayed from Alpaca. Missing quotes stay missing.</p>
            </article>
            <article className="lp-card">
              <Scale />
              <h3>DEMO MONEY</h3>
              <p>Demo users trade using virtual money. Fills are DEMO_SIMULATED.</p>
            </article>
            <article className="lp-card">
              <Shield />
              <h3>DRY RUN</h3>
              <p>Simulation mode remains enabled. The app does not place live broker orders.</p>
            </article>
            <article className="lp-card lp-card-alert">
              <ShieldAlert />
              <h3>REAL-MONEY TRADING OFF</h3>
              <p>Real-money execution remains disabled. Alpaca order endpoints are not used for Demo User trades.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt" id="how-it-works">
        <div className="lp-wrap">
          <p className="lp-kicker">Workflow</p>
          <h2>How it works</h2>
          <div className="lp-steps">
            <article className="lp-card">
              <Radar />
              <p className="lp-step-num">01</p>
              <h3>Connect</h3>
              <p>Open the Demo User session and load live or last-available market data.</p>
            </article>
            <article className="lp-card">
              <Brain />
              <p className="lp-step-num">02</p>
              <h3>Analyze</h3>
              <p>Run the agent pipeline. Recommendations stay advisory.</p>
            </article>
            <article className="lp-card">
              <TrendingUp />
              <p className="lp-step-num">03</p>
              <h3>Simulate</h3>
              <p>Place virtual trades. Risk Guardian is the last gate before a demo fill.</p>
            </article>
            <article className="lp-card">
              <BookOpen />
              <p className="lp-step-num">04</p>
              <h3>Learn</h3>
              <p>Review history, copilot explanations, and voice alerts. No live execution.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="lp-section" id="features">
        <div className="lp-wrap">
          <p className="lp-kicker">Platform</p>
          <h2>Explore Trade AI</h2>
          <div className="lp-feature-grid">
            {FEATURES.map((item) => {
              const Icon = item.icon;
              return (
                <Link key={item.title} href={item.href} className="lp-card lp-feature">
                  <Icon aria-hidden="true" />
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <section className="lp-cta">
        <div className="lp-wrap">
          <h2>Experience Trade AI</h2>
          <p>
            Explore real market intelligence, simulate trades with virtual money, and learn how AI-assisted trading
            decisions are evaluated.
          </p>
          <div className="lp-actions">
            <Link href="/signin" className="lp-btn lp-btn-solid">
              Start Demo
            </Link>
            <Link href="/dashboard" className="lp-btn lp-btn-ghost">
              Explore Dashboard
            </Link>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-wrap">
          <p className="lp-logo">Trade AI</p>
          <p className="lp-tag">AI Trading Mentor &amp; Simulator</p>
          <nav aria-label="Footer">
            <a href="#features">Product</a>
            <a href="#how-it-works">Practice</a>
            <a href="#safety">Safety</a>
            <Link href="/signin">Start Demo</Link>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/stock-analytics">Stock Analytics</Link>
            <Link href="/learn">Learning</Link>
            <Link href="/ai-debate">AI Debate</Link>
            <Link href="/risk-center">Risk Center</Link>
            <Link href="/copilot">Quant Copilot</Link>
            <Link href="/call-agent">Voice</Link>
            <Link href="/activity-log">Activity</Link>
            <Link href="/ai-review">AI Review</Link>
          </nav>
          <p className="lp-legal">
            Trade AI is an educational trading simulator. Market data may be live, but trading is simulated and
            real-money execution is disabled.
          </p>
        </div>
      </footer>
    </div>
  );
}
