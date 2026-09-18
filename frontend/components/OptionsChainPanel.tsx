'use client';

import { useEffect, useMemo, useState } from 'react';
import { isMissing, isUnavailableDisplay, moneyPositive, num, text } from '@/lib/format';
import StockSelector from '@/components/StockSelector';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function show(value: unknown, fallback = 'NOT AVAILABLE'): string {
  if (isMissing(value)) return fallback;
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : fallback;
  return String(value);
}

export default function OptionsChainPanel({
  symbol,
  onSymbolChange,
  options,
  error,
}: {
  symbol: string;
  onSymbolChange: (symbol: string) => void;
  options: unknown;
  error?: unknown;
}) {
  const payload = asDict(options);
  const contracts = (Array.isArray(payload.contracts) ? payload.contracts : []).map(asDict);
  const snapshots = asDict(payload.snapshots);
  const [expiration, setExpiration] = useState('');
  const [optionType, setOptionType] = useState<'call' | 'put'>('call');
  const [strike, setStrike] = useState('');

  useEffect(() => {
    setExpiration('');
    setStrike('');
    setOptionType('call');
  }, [symbol]);

  const expirations = useMemo(() => {
    const set = new Set<string>();
    for (const row of contracts) {
      const exp = String(row.expiration || '').slice(0, 10);
      if (exp) set.add(exp);
    }
    return [...set].sort();
  }, [contracts]);

  const strikes = useMemo(() => {
    const set = new Set<number>();
    for (const row of contracts) {
      const exp = String(row.expiration || '').slice(0, 10);
      const type = String(row.option_type || '').toLowerCase();
      if (expiration && exp !== expiration) continue;
      if (type && type !== optionType) continue;
      if (typeof row.strike === 'number') set.add(row.strike);
    }
    return [...set].sort((a, b) => a - b);
  }, [contracts, expiration, optionType]);

  const selected = useMemo(() => {
    if (!expiration || !strike) return {};
    return (
      contracts.find((row) => {
        const exp = String(row.expiration || '').slice(0, 10);
        const type = String(row.option_type || '').toLowerCase();
        return exp === expiration && type === optionType && Number(row.strike) === Number(strike);
      }) || {}
    );
  }, [contracts, expiration, optionType, strike]);

  const occ = String(selected.occ_symbol || '');
  const snap = occ ? asDict(snapshots[occ]) : {};
  const err = error instanceof Error ? error.message : error ? String(error) : '';

  return (
    <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Options Analysis</h2>
      <p className="mb-3 text-xs text-slate-500">Alpaca option contracts and snapshots only. Missing Greeks stay GREEKS NOT AVAILABLE — they are not replaced with zero.</p>
      <StockSelector value={symbol} onChange={onSymbolChange} label="Underlying" />
      {err ? <p className="mt-2 text-sm text-rose-300">NETWORK ERROR · {err}</p> : null}
      {contracts.length === 0 && !err ? (
        <p className="mt-3 text-sm text-slate-400">No option contracts returned for {symbol}.</p>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="text-xs text-slate-400">
              Expiration
              <select
                value={expiration}
                onChange={(e) => {
                  setExpiration(e.target.value);
                  setStrike('');
                }}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"
              >
                <option value="">Select expiration</option>
                {expirations.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-400">
              Option Type
              <select
                value={optionType}
                onChange={(e) => {
                  setOptionType(e.target.value as 'call' | 'put');
                  setStrike('');
                }}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"
              >
                <option value="call">CALL</option>
                <option value="put">PUT</option>
              </select>
            </label>
            <label className="text-xs text-slate-400">
              Strike
              <select
                value={strike}
                onChange={(e) => setStrike(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"
              >
                <option value="">Select strike</option>
                {strikes.map((item) => (
                  <option key={item} value={String(item)}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {expiration && strike ? (
              <>
                <Field label="Bid" value={moneyPositive(snap.bid)} />
                <Field label="Ask" value={moneyPositive(snap.ask)} />
                <Field
                  label="Midpoint"
                  value={
                    typeof snap.bid === 'number' && typeof snap.ask === 'number' && snap.bid > 0 && snap.ask > 0
                      ? moneyPositive((snap.bid + snap.ask) / 2)
                      : 'NO MIDPOINT'
                  }
                />
                <Field label="Volume" value={show(snap.volume, 'VOLUME NOT AVAILABLE')} />
                <Field label="Open Interest" value={show(snap.open_interest ?? selected.open_interest, 'OPEN INTEREST NOT AVAILABLE')} />
                <Field label="IV" value={show(snap.implied_volatility, 'IV NOT AVAILABLE')} />
                <Field label="Delta" value={typeof snap.delta === 'number' ? num(snap.delta, 4) : 'GREEKS NOT AVAILABLE'} />
                <Field label="Gamma" value={typeof snap.gamma === 'number' ? num(snap.gamma, 4) : 'GREEKS NOT AVAILABLE'} />
                <Field label="Theta" value={typeof snap.theta === 'number' ? num(snap.theta, 4) : 'GREEKS NOT AVAILABLE'} />
                <Field label="Vega" value={typeof snap.vega === 'number' ? num(snap.vega, 4) : 'GREEKS NOT AVAILABLE'} />
              </>
            ) : (
              <p className="col-span-2 text-sm text-slate-400 sm:col-span-5">Select expiration and strike to load the Alpaca option snapshot.</p>
            )}
          </div>
          {occ ? <p className="mt-2 text-xs text-slate-500">Contract {text(occ)}</p> : null}
        </>
      )}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`text-sm font-semibold ${isUnavailableDisplay(value) ? 'text-amber-300' : 'text-white'}`}>{value}</p>
    </div>
  );
}
