'use client';

import { useState } from 'react';
import TradeSimulatePanel from '@/components/TradeSimulatePanel';
import { useMarketData } from '@/hooks/useApi';
import { moneyPositive } from '@/lib/format';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

export default function TradeSimulatorPage() {
  const [symbol, setSymbol] = useState('AAPL');
  const { market } = useMarketData(symbol);
  const quote = asDict(asDict(market).quote);
  const trade = asDict(asDict(market).trade);
  const clock = asDict(asDict(market).clock);
  const bars = Array.isArray(asDict(market).bars) ? (asDict(market).bars as Dict[]) : [];
  const last = asDict(bars[bars.length - 1]);

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">Trade Simulator</h1>
        <p className="mt-2 text-sm text-slate-400">
          Educational DRY_RUN equity simulation. Fresh quotes are required. Stale or closed-session data fails closed. Never a live trade.
        </p>
      </div>
      <TradeSimulatePanel
        symbol={symbol}
        onSymbolChange={setSymbol}
        market={{
          price: quote.last_trade_price ?? trade.price,
          bid: quote.bid,
          ask: quote.ask,
          volume: last.volume,
          session: typeof clock.is_open === 'boolean' ? (clock.is_open ? 'OPEN' : 'CLOSED') : undefined,
          freshness: quote.freshness || trade.freshness,
          spread:
            typeof quote.bid === 'number' && typeof quote.ask === 'number' && quote.bid > 0 && quote.ask > 0
              ? quote.ask - quote.bid
              : undefined,
        }}
      />
      <p className="text-xs text-slate-500">Bid {moneyPositive(quote.bid)} · Ask {moneyPositive(quote.ask)} · Alpaca paper quotes only.</p>
    </main>
  );
}
