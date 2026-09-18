'use client';

import { useDemoPositions } from '@/hooks/useApi';
import { useDemoMode } from '@/hooks/useDemoMode';

export default function Positions() {
  const { positions, isLoading } = useDemoPositions();
  const demo = useDemoMode();
  const isDemo = demo.enabled;
  const data = positions || [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-700 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-white">Open Positions</h1>
          {isDemo && <p className="text-sm text-purple-400 mt-1">DEMO MODE - SIMULATED</p>}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading && data.length === 0 ? (
          <p className="text-sm text-slate-400">Loading positions…</p>
        ) : data.length === 0 ? (
          <div className="rounded-lg border border-slate-700 bg-slate-800/50 backdrop-blur p-12 text-center">
            <p className="text-slate-400">No open positions</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Symbol</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-300">Type</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Qty</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Entry</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Current</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Market Value</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">P&L</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Expiry</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Days</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-300">Greeks</th>
                </tr>
              </thead>
              <tbody>
                {data.map((pos: any, idx: number) => {
                  const entry = Number(pos.avg_entry ?? pos.avg_fill_price);
                  const current = Number(pos.current_price);
                  const pnl = Number(pos.unrealized_pnl ?? pos.pnl ?? 0);
                  const pnlPct = Number(pos.pnl_pct);
                  return (
                  <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-800/30 transition">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-semibold text-white">{pos.symbol}</p>
                        <p className="text-xs text-sky-300">{pos.label || (isDemo ? 'SIMULATED' : 'ALPACA PAPER')}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 rounded text-xs font-semibold border border-slate-600 text-slate-200">
                        {pos.type || pos.side || 'EQUITY'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-white">{pos.quantity}</td>
                    <td className="px-4 py-3 text-right text-slate-300">{Number.isFinite(entry) ? `$${entry.toFixed(2)}` : 'Not available'}</td>
                    <td className="px-4 py-3 text-right text-white font-semibold">{Number.isFinite(current) ? `$${current.toFixed(2)}` : 'Not available'}</td>
                    <td className="px-4 py-3 text-right text-slate-300">{Number.isFinite(Number(pos.market_value)) ? `$${Number(pos.market_value).toFixed(2)}` : 'Not available'}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <span className={`font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          ${Math.abs(pnl).toFixed(2)}
                        </span>
                        {Number.isFinite(pnlPct) ? (
                          <span className={`text-xs ${pnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {pnlPct.toFixed(1)}%
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">{pos.expiration || '—'}</td>
                    <td className="px-4 py-3 text-right text-slate-300">{pos.days ?? '—'}</td>
                    <td className="px-4 py-3 text-right text-slate-500 text-xs">{pos.simulated ? 'Greeks unavailable — no option position' : '—'}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}