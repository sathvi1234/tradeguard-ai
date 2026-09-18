import { isMissing } from '@/lib/format';
import { toMarketState, type MarketDataState } from '@/lib/marketState';

export type Dict = Record<string, unknown>;

export function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

export function asNum(value: unknown): number | null {
  if (typeof value === 'boolean' || isMissing(value)) return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export type ChartPoint = { t: string; price: number };

export function barsToSeries(bars: unknown): ChartPoint[] {
  if (!Array.isArray(bars)) return [];
  const points: ChartPoint[] = [];
  for (const item of bars) {
    const row = asDict(item);
    const close = asNum(row.close);
    if (close === null) continue;
    const stamp = String(row.timestamp || row.t || row.date || '').trim();
    points.push({
      t: stamp ? stamp.slice(0, 10) : String(points.length + 1),
      price: close,
    });
  }
  return points;
}

export function quoteCard(raw: unknown, fallbackSymbol: string): {
  state: MarketDataState;
  change: number | null;
  changePct: number | null;
  company: string | null;
  bars: ChartPoint[];
  barCount: number;
} {
  const data = asDict(raw);
  const state = toMarketState(raw, { symbol: fallbackSymbol });
  const change = asNum(data.day_change);
  const changePct = asNum(data.day_change_pct);
  const company = isMissing(data.company) ? null : String(data.company);
  const bars = barsToSeries(data.bars);
  const barCount = asNum(data.bar_count) ?? bars.length;
  return { state, change, changePct, company, bars, barCount };
}

export function chartStatus(state: MarketDataState, bars: ChartPoint[], loading: boolean, error: unknown): {
  kind: 'loading' | 'error' | 'unavailable' | 'empty' | 'limited' | 'stale' | 'closed' | 'ready';
  message: string;
} {
  if (loading && bars.length === 0) {
    return { kind: 'loading', message: 'Loading market history…' };
  }
  if (error && bars.length === 0 && !state.quoteAvailable) {
    return { kind: 'error', message: 'Market data unavailable' };
  }
  if (state.dataError && bars.length === 0) {
    return { kind: 'error', message: 'Market data unavailable' };
  }
  if (!state.quoteAvailable && bars.length === 0) {
    return { kind: 'unavailable', message: 'Market data unavailable' };
  }
  if (bars.length === 0) {
    return { kind: 'empty', message: 'No historical bars were returned for this symbol. A trend is not drawn from a quote alone.' };
  }
  if (bars.length === 1) {
    return { kind: 'limited', message: 'Only one historical bar is available. A trend line is not drawn from a single point.' };
  }
  if (state.freshness === 'STALE') {
    return { kind: 'stale', message: 'Showing last available Alpaca bars. Quote is STALE.' };
  }
  if (state.marketStatus === 'CLOSED') {
    return { kind: 'closed', message: 'Market is closed. Chart shows last available Alpaca daily bars.' };
  }
  return { kind: 'ready', message: `${bars.length} Alpaca daily bars` };
}
