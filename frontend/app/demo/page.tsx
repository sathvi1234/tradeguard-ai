'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useAlpacaStatus } from '@/hooks/useApi';
import { useDemoMode } from '@/hooks/useDemoMode';
import { writeDemoEnabled } from '@/lib/demo';
import { money, pct, sim } from '@/lib/format';
import { SimulatedMark } from '@/components/DemoBanner';

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4 sm:p-5">
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
        {title}
        <SimulatedMark />
      </h2>
      {children}
    </section>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-sm text-slate-200">
      <span className="text-slate-500">{label}: </span>
      {sim(value)}
    </p>
  );
}

export default function HackathonDemoPage() {
  const { enabled, setEnabled, scene, setScene, bundle } = useDemoMode();
  const { alpaca, error: alpacaError } = useAlpacaStatus();

  useEffect(() => {
    writeDemoEnabled(true);
  }, []);
  const p = bundle.portfolio;
  const pos = bundle.positions[0] || {};
  const g = bundle.greeks;
  const trade = bundle.paperTrade;
  const copilot = bundle.copilot;
  const connected = Boolean(alpaca?.connected && alpaca?.authenticated);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 pb-40">
      <header className="border-b border-slate-800 bg-slate-950/80 px-4 py-4 sm:px-6">
        <p className="text-[11px] uppercase tracking-[0.2em] text-fuchsia-300">Hackathon</p>
        <h1 className="text-2xl font-bold text-white">DEMO MODE</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-300">
          Clearly labeled simulated walkthrough. Live trading is never enabled. DRY_RUN stays true. Simulated values are
          not mixed with live paper account balances.
        </p>
      </header>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-6 sm:px-6">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setEnabled(!enabled)}
            className="rounded-lg bg-fuchsia-700 px-4 py-2 text-sm font-semibold text-white"
          >
            {enabled ? 'Demo is ON' : 'Enable DEMO MODE'}
          </button>
          <button
            type="button"
            onClick={() => setScene('protection')}
            className={`rounded-lg border px-4 py-2 text-sm font-semibold ${
              scene === 'protection' ? 'border-amber-500 bg-amber-950 text-amber-200' : 'border-slate-700 text-slate-300'
            }`}
          >
            PROTECTION (SIMULATED)
          </button>
          <button
            type="button"
            onClick={() => setScene('critical')}
            className={`rounded-lg border px-4 py-2 text-sm font-semibold ${
              scene === 'critical' ? 'border-rose-500 bg-rose-950 text-rose-200' : 'border-slate-700 text-slate-300'
            }`}
          >
            CRITICAL (SIMULATED)
          </button>
          <Link href="/dashboard" className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200">
            Dashboard
          </Link>
        </div>

        <section className="rounded-xl border border-sky-700 bg-sky-950/40 p-4">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-300">
            Alpaca paper connection (live paper API status — not simulated capital)
          </h2>
          <p className="mt-2 text-sm text-sky-100">
            {alpacaError
              ? 'Paper API status unavailable'
              : connected
                ? 'Connected to Alpaca paper API'
                : 'Not connected'}
          </p>
          <p className="mt-1 text-xs text-sky-200">paper_trading=true · live_trading=false · no credentials shown</p>
        </section>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card title="$100k paper starting capital">
            <Line label="Starting capital" value={money(bundle.starting_capital)} />
            <Line label="Current value" value={money(p.account_value)} />
            <Line label="Cash" value={money(p.cash)} />
          </Card>
          <Card title="P&L">
            <Line label="Total P&L" value={money(p.total_pnl)} />
            <Line label="Daily P&L" value={money(p.daily_pnl)} />
            <Line label="Drawdown" value={pct(p.drawdown_pct, false)} />
          </Card>
          <Card title="Trading mode">
            <p className="text-2xl font-bold uppercase text-white">{sim(scene)}</p>
            <p className="mt-2 text-sm text-slate-300">
              {scene === 'critical'
                ? sim('New trades blocked')
                : sim('Reduced risk / PROTECTION')}
            </p>
          </Card>
          <Card title="Simulated paper trade">
            <Line label="Contract" value={String(trade.contract)} />
            <Line label="Side / qty" value={`${trade.side} ${trade.quantity}`} />
            <Line label="Status" value={String(trade.status)} />
            <p className="mt-2 text-xs font-semibold uppercase text-rose-300">No live trading · not submitted to Alpaca</p>
          </Card>
        </div>

        <Card title="Market Scout">
          <Line label="Recommendation" value="constructive SPY tape" />
          <Line label="Reasoning" value="directional enough to debate a debit call" />
        </Card>
        <Card title="Market Intelligence">
          <Line label="IV / spread / session" value={`${bundle.intelligence.iv} / ${bundle.intelligence.bid_ask_spread} / ${bundle.intelligence.market_session}`} />
        </Card>
        <Card title="Strategy Brain">
          <Line label="Top scenario" value="BULL" />
          <Line label="Thesis" value="bullish continuation on SPY paper tape" />
        </Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card title="Bull debate">
            <Line label="Recommendation" value="BUY" />
          </Card>
          <Card title="Bear debate">
            <Line label="Recommendation" value="NO_TRADE" />
          </Card>
        </div>
        <Card title="Red Team">
          <Line label="Severity" value={scene === 'critical' ? 'CRITICAL' : 'HIGH'} />
          <Line label="Objection" value="debit can go to zero" />
        </Card>
        <Card title="Options Strategy">
          <Line label="Structure" value="long call debit" />
        </Card>
        <Card title="Decision Agent">
          <Line label="Decision" value={scene === 'critical' ? 'no_trade' : 'approve'} />
        </Card>
        <Card title="RiskGuardian">
          <Line
            label="Result"
            value={scene === 'critical' ? 'rejected — CRITICAL blocks new trades' : 'approved for DRY_RUN only'}
          />
        </Card>
        <Card title="DrawdownGuardian">
          <Line label="Mode" value={scene} />
          <Line label="Drawdown" value={pct(p.drawdown_pct, false)} />
        </Card>
        <Card title="RiskBodyguard">
          <Line label="Action" value={String(bundle.bodyguard.action)} />
          <Line label="Freeze new trades" value={String(bundle.bodyguard.freeze_new_trades)} />
        </Card>
        <Card title="Portfolio Greeks">
          <Line label="Delta" value={String(g.delta)} />
          <Line label="Gamma" value={String(g.gamma)} />
          <Line label="Theta" value={String(g.theta)} />
          <Line label="Vega" value={String(g.vega)} />
        </Card>
        <Card title="Quant Copilot">
          <Line label="Advisory" value={String(copilot.summary)} />
        </Card>
        <Card title="Mock voice alert">
          <p className="text-sm font-semibold text-amber-300">SIMULATED CALL · MOCK VOICE · NO REAL PHONE CALL</p>
          <Line label="Alert" value={scene === 'critical' ? 'CRITICAL mock alert' : 'PROTECTION mock alert'} />
        </Card>
        <Card title="Audit trail">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
            {bundle.activity.map((row) => (
              <li key={String(row.event_id)}>
                {sim(String(row.event_type))} — {String(row.message)}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Positions">
          <Line label="Symbol" value={String(pos.symbol)} />
          <Line label="P&L" value={money(pos.unrealized_pnl)} />
        </Card>
      </main>
    </div>
  );
}
