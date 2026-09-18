'use client';

import { useState, useEffect } from 'react';
import { Zap, TrendingUp, TrendingDown } from 'lucide-react';

export default function Opportunities() {
  const [mockData, setMockData] = useState<any[]>([]);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    const demo = localStorage.getItem('demo-mode') === 'true';
    setIsDemo(demo);

    if (demo && mockData.length === 0) {
      setMockData([
        {
          symbol: 'AAPL',
          direction: 'bullish',
          confidence: 0.68,
          option_contract: 'AAPL 240120C00185000',
          strategy: 'buy_call',
          reward: 250,
          risk: 325,
          ratio: 0.77,
          market_score: 0.68,
          timestamp: new Date().toISOString(),
        },
        {
          symbol: 'SPY',
          direction: 'bearish',
          confidence: 0.52,
          option_contract: 'SPY 240215P00500000',
          strategy: 'buy_put',
          reward: 150,
          risk: 280,
          ratio: 0.54,
          market_score: 0.48,
          timestamp: new Date(Date.now() - 300000).toISOString(),
        },
        {
          symbol: 'QQQ',
          direction: 'bullish',
          confidence: 0.61,
          option_contract: 'QQQ 240110C00380000',
          strategy: 'vertical_spread',
          reward: 180,
          risk: 200,
          ratio: 0.90,
          market_score: 0.65,
          timestamp: new Date(Date.now() - 600000).toISOString(),
        },
      ]);
    }
  }, [mockData]);

  const data = isDemo ? mockData : [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-700 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-white">Market Opportunities</h1>
          {isDemo && <p className="text-sm text-purple-400 mt-1">DEMO MODE - SIMULATED</p>}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {data.length === 0 ? (
          <div className="rounded-lg border border-slate-700 bg-slate-800/50 backdrop-blur p-12 text-center">
            <Zap className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400">No opportunities identified at this time</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.map((opp, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-700/50 backdrop-blur p-6 transition cursor-pointer"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-white">
                      {opp.symbol} {isDemo ? <span className="text-xs text-amber-300">SIMULATED</span> : null}
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 font-mono">{opp.option_contract}</p>
                  </div>
                  {opp.direction === 'bullish' ? (
                    <TrendingUp className="w-5 h-5 text-green-400" />
                  ) : (
                    <TrendingDown className="w-5 h-5 text-red-400" />
                  )}
                </div>

                {/* Direction */}
                <div className="mb-4">
                  <span
                    className={`px-3 py-1 rounded text-xs font-semibold ${
                      opp.direction === 'bullish'
                        ? 'bg-green-900/30 text-green-300 border border-green-700'
                        : 'bg-red-900/30 text-red-300 border border-red-700'
                    }`}
                  >
                    {opp.direction.toUpperCase()}
                  </span>
                </div>

                {/* Confidence */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-slate-400">Confidence</span>
                    <span className="text-sm font-semibold text-white">{(opp.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="bg-slate-700 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-blue-500 h-full"
                      style={{ width: `${opp.confidence * 100}%` }}
                    ></div>
                  </div>
                </div>

                {/* Strategy */}
                <div className="mb-4 p-3 bg-slate-700/30 rounded">
                  <p className="text-xs text-slate-400">Strategy</p>
                  <p className="text-sm font-semibold text-white capitalize mt-1">{opp.strategy.replace(/_/g, ' ')}</p>
                </div>

                {/* Risk/Reward */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <p className="text-xs text-slate-400">Potential Reward</p>
                    <p className="text-lg font-bold text-green-400">${opp.reward}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Max Risk</p>
                    <p className="text-lg font-bold text-red-400">${opp.risk}</p>
                  </div>
                </div>

                {/* Risk/Reward Ratio */}
                <div className="p-3 bg-blue-900/20 border border-blue-700 rounded">
                  <p className="text-xs text-blue-300">Risk/Reward Ratio</p>
                  <p className="text-lg font-bold text-blue-300 mt-1">{opp.ratio.toFixed(2)}</p>
                </div>

                {/* Timestamp */}
                <p className="text-xs text-slate-500 mt-4">
                  {new Date(opp.timestamp).toLocaleTimeString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}