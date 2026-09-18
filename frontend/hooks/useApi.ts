import useSWR, { useSWRConfig } from 'swr';
import api from '@/lib/api';

const fetcher = async (url: string) => {
  try {
    const response = await api.get(url);
    return response.data;
  } catch (error: unknown) {
    const err = error as { response?: { data?: { detail?: string } }; message?: string };
    throw new Error(err.response?.data?.detail || err.message || 'Request failed');
  }
};

export function usePortfolio() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/portfolio',
    fetcher,
    { refreshInterval: 5000, revalidateOnFocus: false }
  );

  return {
    portfolio: data,
    isLoading,
    error,
    mutate,
  };
}

export function usePortfolioHistory(limit = 100) {
  const { data, error, isLoading } = useSWR(
    `/api/v1/portfolio/history?limit=${limit}`,
    fetcher,
    { refreshInterval: 10000 }
  );

  return {
    history: data || [],
    isLoading,
    error,
  };
}

export function usePortfolioStats() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/portfolio/stats',
    fetcher,
    { refreshInterval: 5000 }
  );

  return {
    stats: data,
    isLoading,
    error,
  };
}

export function usePortfolioHealth() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/portfolio/health',
    fetcher,
    { refreshInterval: 5000 }
  );

  return {
    health: data,
    isLoading,
    error,
  };
}

export function usePositions() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/portfolio/positions',
    fetcher,
    { refreshInterval: 5000 }
  );

  return {
    positions: data || [],
    isLoading,
    error,
  };
}

export function useOrders() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/portfolio/orders',
    fetcher,
    { refreshInterval: 5000 }
  );

  return {
    orders: data || [],
    isLoading,
    error,
  };
}

export function useActivity(symbol?: string) {
  const { data, error, isLoading } = useSWR(
    `/api/v1/portfolio/activity${symbol ? `?symbol=${symbol}` : ''}`,
    fetcher,
    { refreshInterval: 10000 }
  );

  return {
    activity: data || [],
    isLoading,
    error,
  };
}

export function useAutonomousStatus() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/autonomous/status',
    fetcher,
    { refreshInterval: 3000, revalidateOnFocus: false }
  );

  return {
    status: data,
    isLoading,
    error,
    mutate,
  };
}

export function useDebateResult(debateId?: string) {
  const { data, error, isLoading } = useSWR(
    debateId ? `/api/v1/debate/${debateId}` : null,
    fetcher,
    { refreshInterval: 2000 }
  );

  return {
    debate: data,
    isLoading,
    error,
  };
}

export function useHealth() {
  const { data, error, isLoading } = useSWR(
    '/health',
    fetcher,
    { refreshInterval: 5000 }
  );

  return {
    health: data,
    isLoading,
    error,
  };
}

export function useAlpacaStatus() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/alpaca/status',
    fetcher,
    { refreshInterval: 8000 }
  );

  return {
    alpaca: data,
    isLoading,
    error,
  };
}

export function useGreeks() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/greeks',
    fetcher,
    { refreshInterval: 8000 }
  );

  return {
    greeks: data,
    isLoading,
    error,
  };
}

export function useIntelligence(symbol = 'SPY') {
  const { data, error, isLoading, mutate } = useSWR(
    `/api/v1/intelligence?symbol=${encodeURIComponent(symbol)}`,
    fetcher,
    { refreshInterval: 10000 }
  );

  return {
    intelligence: data,
    isLoading,
    error,
    mutate,
  };
}

export function useMarketData(symbol: string) {
  const { data, error, isLoading, mutate } = useSWR(
    symbol ? `/api/v1/market-data/${encodeURIComponent(symbol)}` : null,
    fetcher,
    { refreshInterval: 12000, revalidateOnFocus: true }
  );

  return {
    market: data,
    isLoading,
    error,
    mutate,
  };
}

export function useAnalyticsQuote(symbol: string) {
  const { data, error, isLoading, mutate } = useSWR(
    symbol ? `/api/v1/analytics/${encodeURIComponent(symbol)}` : null,
    fetcher,
    { refreshInterval: 30000, revalidateOnFocus: false }
  );

  return {
    analytics: data,
    isLoading,
    error,
    mutate,
  };
}

export function useBodyguard() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/risk/bodyguard',
    fetcher,
    { refreshInterval: 8000 }
  );

  return {
    bodyguard: data,
    isLoading,
    error,
  };
}

export function useMemory(limit = 100) {
  const { data, error, isLoading } = useSWR(
    `/api/v1/memory?limit=${limit}`,
    fetcher,
    { refreshInterval: 8000 }
  );

  return {
    memory: Array.isArray(data) ? data : [],
    isLoading,
    error,
  };
}

export function useOptions(symbol: string) {
  const { data, error, isLoading, mutate } = useSWR(
    symbol ? `/api/v1/options/${encodeURIComponent(symbol)}` : null,
    fetcher,
    { refreshInterval: 15000 }
  );

  return {
    options: data,
    isLoading,
    error,
    mutate,
  };
}

export function useWatchlist(symbols?: string[]) {
  const query = (symbols && symbols.length ? symbols : undefined)?.join(',');
  const { data, error, isLoading, mutate } = useSWR(
    query ? `/api/v1/market-data?symbols=${encodeURIComponent(query)}` : '/api/v1/market-data',
    fetcher,
    { refreshInterval: 15000, revalidateOnFocus: true }
  );
  return {
    watchlist: data,
    items: Array.isArray(data?.items) ? data.items : [],
    liveMarketData: Boolean(data?.live_market_data),
    isLoading,
    error,
    mutate,
  };
}

export function useRefreshTrading() {
  const { mutate } = useSWRConfig();
  return () =>
    Promise.all([
      mutate('/api/v1/demo/orders'),
      mutate('/api/v1/demo/positions'),
      mutate('/api/v1/demo/portfolio'),
      mutate('/api/v1/portfolio'),
      mutate('/api/v1/portfolio/positions'),
      mutate('/api/v1/portfolio/orders'),
      mutate('/api/v1/portfolio/health'),
    ]);
}

export function useDemoOrders() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/demo/orders',
    fetcher,
    { refreshInterval: 4000, revalidateOnFocus: true }
  );
  const orders = Array.isArray(data?.orders) ? data.orders : Array.isArray(data) ? data : [];
  return {
    orders,
    isLoading,
    error,
    mutate,
  };
}

export function useDemoPortfolio() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/demo/portfolio',
    fetcher,
    { refreshInterval: 4000, revalidateOnFocus: true }
  );
  return {
    portfolio: data,
    isLoading,
    error,
    mutate,
  };
}

export function useDemoPositions() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/demo/positions',
    fetcher,
    { refreshInterval: 4000, revalidateOnFocus: true }
  );
  const positions = Array.isArray(data?.positions) ? data.positions : Array.isArray(data) ? data : [];
  return {
    positions,
    isLoading,
    error,
    mutate,
  };
}

export function usePaperOrders() {
  return useDemoOrders();
}

export function useStreamStatus() {
  const { data, error, isLoading } = useSWR('/api/v1/stream/status', fetcher, { refreshInterval: 5000 });
  return {
    stream: data,
    isLoading,
    error,
  };
}

export function useSimulatedFills() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/simulate/equity',
    fetcher,
    { refreshInterval: 5000 }
  );
  return {
    fills: Array.isArray(data?.fills) ? data.fills : [],
    positions: Array.isArray(data?.positions) ? data.positions : [],
    isLoading,
    error,
    mutate,
  };
}

export function useVoiceStatus() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/voice',
    fetcher,
    { refreshInterval: 15000 }
  );

  return {
    voice: data,
    isLoading,
    error,
  };
}

export function useDataQuality(symbol = 'SPY') {
  const { data, error, isLoading } = useSWR(
    symbol ? `/api/v1/data-quality/${encodeURIComponent(symbol)}` : null,
    fetcher,
    { refreshInterval: 15000, revalidateOnFocus: true }
  );
  return {
    quality: data,
    isLoading,
    error,
  };
}

export function useBacktestStrategies() {
  const { data, error, isLoading } = useSWR('/api/v1/backtest/strategies', fetcher, {
    revalidateOnFocus: false,
  });
  return {
    strategies: Array.isArray(data?.strategies) ? data.strategies : [],
    isLoading,
    error,
  };
}

export function useBacktestRuns() {
  const { data, error, isLoading, mutate } = useSWR('/api/v1/backtest/runs?limit=20', fetcher, {
    revalidateOnFocus: true,
  });
  return {
    runs: Array.isArray(data?.runs) ? data.runs : [],
    isLoading,
    error,
    mutate,
  };
}

export function useFalsificationReports() {
  const { data, error, isLoading, mutate } = useSWR('/api/v1/falsification/reports?limit=20', fetcher, {
    revalidateOnFocus: true,
  });
  return {
    reports: Array.isArray(data?.reports) ? data.reports : [],
    isLoading,
    error,
    mutate,
  };
}

export function useLastReview() {
  const { data, error, isLoading, mutate } = useSWR('/api/v1/review/last', fetcher, {
    revalidateOnFocus: true,
  });
  return {
    last: data,
    isLoading,
    error,
    mutate,
  };
}

export function useVolatilityForecasts() {
  const { data, error, isLoading, mutate } = useSWR('/api/v1/volatility/forecasts?limit=20', fetcher, {
    revalidateOnFocus: true,
  });
  return {
    forecasts: Array.isArray(data?.forecasts) ? data.forecasts : [],
    isLoading,
    error,
    mutate,
  };
}
