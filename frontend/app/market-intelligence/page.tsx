'use client';

import { FormEvent, useState } from 'react';
import { analytics } from '@/lib/api';
import { isMissing, isUnavailableDisplay, money, moneyPositive, text } from '@/lib/format';
import MarketClosedNotice from '@/components/MarketClosedNotice';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function show(value: unknown, fallback = 'NOT AVAILABLE'): string {
  if (isMissing(value)) return fallback;
  if (typeof value === 'number') return String(value);
  return String(value);
}

export default function MarketIntelligencePage() {
  const [symbol, setSymbol] = useState('AAPL');
  const [loaded, setLoaded] = useState<Dict | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await analytics.get(symbol.trim().toUpperCase());
      setLoaded(response.data as Dict);
      setSymbol(String((response.data as Dict).symbol || symbol).toUpperCase());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'MARKET DATA ERROR');
      setLoaded(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">Market Intelligence</h1>
        <p className="mt-2 text-sm text-slate-400">Alpaca paper quotes only. Session and freshness are shown separately. Closed markets are not treated as an outage.</p>
      </div>
      <form onSubmit={(e) => void load(e)} className="flex flex-wrap gap-2">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
        />
        <button type="submit" disabled={busy} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">
          Load
        </button>
      </form>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {loaded ? (
        <>
          <MarketClosedNotice market={loaded} symbol={String(loaded.symbol || '')} />
          <section className="grid grid-cols-2 gap-3 rounded-xl border border-slate-700 bg-slate-900/70 p-4 sm:grid-cols-4">
            <Field label="Price" value={typeof loaded.price === 'number' && loaded.price > 0 ? money(loaded.price) : 'NO QUOTE AVAILABLE'} />
            <Field label="Bid" value={typeof loaded.bid === 'number' ? moneyPositive(loaded.bid) : 'NO BID'} />
            <Field label="Ask" value={typeof loaded.ask === 'number' ? moneyPositive(loaded.ask) : 'NO ASK'} />
            <Field label="Spread" value={typeof loaded.spread === 'number' ? moneyPositive(loaded.spread) : 'NO SPREAD'} />
            <Field label="Volume" value={show(loaded.volume, 'VOLUME NOT AVAILABLE')} />
            <Field label="Session" value={show(loaded.session, 'SESSION UNKNOWN')} />
            <Field label="Freshness" value={show(loaded.freshness, 'FRESHNESS UNKNOWN')} />
          </section>
          <p className="text-xs text-slate-500">{text(asDict(loaded.intelligence).notes)}</p>
        </>
      ) : (
        <p className="text-sm text-slate-400">Enter a ticker and load market intelligence from the paper feed.</p>
      )}
    </main>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase text-slate-500">{label}</p>
      <p className={`text-sm ${isUnavailableDisplay(value) ? 'text-amber-300' : 'text-white'}`}>{value}</p>
    </div>
  );
}
