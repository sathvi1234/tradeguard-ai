'use client';

import { CheckCircle, XCircle, Settings as SettingsIcon } from 'lucide-react';
import Link from 'next/link';
import QRCodeComponent from '@/components/QRCode';
import { useDemoMode } from '@/hooks/useDemoMode';

export default function Settings() {
  const { enabled: demoMode, setEnabled } = useDemoMode();
  const settings = {
    alpaca: {
      status: 'configured',
      description: 'Alpaca Trading API Connection (paper only)',
    },
    paper_trading: {
      status: 'enabled',
      description: 'Paper Trading Mode (No Real Money)',
    },
    dry_run: {
      status: 'enabled',
      description: 'Dry Run Mode — real-money execution stays off',
    },
    live_trading: {
      status: 'off',
      description: 'Real-money order execution is disabled',
    },
    voice_alerts: {
      status: 'mock',
      description: 'Mock voice only — no real phone calls',
    },
  };

  const toggleDemoMode = () => {
    setEnabled(!demoMode);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'configured':
      case 'enabled':
      case 'blocked':
      case 'off':
      case 'mock':
        return 'text-green-400';
      case 'not_configured':
      case 'disabled':
        return 'text-yellow-400';
      default:
        return 'text-slate-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'configured':
      case 'enabled':
      case 'blocked':
      case 'off':
      case 'mock':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'not_configured':
      case 'disabled':
        return <XCircle className="w-5 h-5 text-yellow-400" />;
      default:
        return <SettingsIcon className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 pb-40">
      <div className="border-b border-slate-700 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-xs text-slate-400 mt-2">Configuration Status Only • No Secrets Displayed</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          <div className="rounded-lg border border-fuchsia-600 bg-fuchsia-950/40 p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-white">DEMO MODE</h2>
                <p className="text-sm text-fuchsia-200 mt-1">
                  Hackathon walkthrough with SIMULATED values. Never enables live trading. Paper / DRY_RUN only.
                </p>
              </div>
              <button
                type="button"
                onClick={toggleDemoMode}
                className={`px-6 py-2 rounded-lg font-semibold transition ${
                  demoMode
                    ? 'bg-fuchsia-600 hover:bg-fuchsia-700 text-white'
                    : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                }`}
              >
                {demoMode ? 'ENABLED' : 'Disabled'}
              </button>
            </div>
            {demoMode && (
              <div className="mt-4 p-3 bg-fuchsia-900/40 border border-fuchsia-600 rounded">
                <p className="text-sm text-fuchsia-100">
                  DEMO MODE is active. Simulated values are labeled SIMULATED and are not your live paper account. Live
                  trading remains blocked.
                </p>
                <Link href="/demo" className="mt-2 inline-block text-sm font-semibold text-white underline">
                  Open demo walkthrough
                </Link>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-slate-700 bg-slate-800/50 backdrop-blur p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Configuration Status</h2>
            <div className="space-y-3">
              {Object.entries(settings).map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-center justify-between p-4 rounded-lg border border-slate-700 bg-slate-700/30"
                >
                  <div className="flex items-center gap-3 flex-1">
                    {getStatusIcon(value.status)}
                    <div>
                      <p className="font-semibold text-white capitalize">{key.replace(/_/g, ' ')}</p>
                      <p className="text-sm text-slate-400">{value.description}</p>
                    </div>
                  </div>
                  <span className={`font-semibold text-sm uppercase ${getStatusColor(value.status)}`}>
                    {value.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-blue-700 bg-blue-900/20 p-6">
            <h3 className="text-sm font-semibold text-blue-300 mb-2">Security Notice</h3>
            <ul className="text-sm text-blue-300 space-y-1 list-disc list-inside">
              <li>No API keys are displayed in this interface</li>
              <li>All secrets are stored server-side only</li>
              <li>Paper trading is enforced (no live trading)</li>
              <li>DEMO MODE cannot submit live orders</li>
            </ul>
          </div>

          <div className="rounded-lg border border-slate-700 bg-slate-800/50 backdrop-blur p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Mobile QR</h2>
            <QRCodeComponent />
          </div>
        </div>
      </div>
    </div>
  );
}
