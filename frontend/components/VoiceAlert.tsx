'use client';

import { Volume2, VolumeX } from 'lucide-react';
import { useState } from 'react';
import { useAutonomousStatus, usePortfolio } from '@/hooks/useApi';
import { useDemoMode } from '@/hooks/useDemoMode';
import { isMissing, money, pct, text } from '@/lib/format';
import { canSpeak, speak, stopSpeech } from '@/lib/speech';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

export default function VoiceAlert() {
  const demo = useDemoMode();
  const { status: liveStatus } = useAutonomousStatus();
  const { portfolio } = usePortfolio();
  const [speechNote, setSpeechNote] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const engine = asDict(demo.enabled ? demo.bundle.status : liveStatus);
  const dd = asDict(asDict(engine.drawdown_guardian).state);
  const mode = String(engine.current_mode || dd.current_mode || '').toLowerCase();
  const isCritical = mode === 'critical';
  const isProtection = mode === 'protection';
  const active = isCritical || isProtection;
  const snap = asDict(portfolio);
  const reason = text(
    engine.last_cycle_message || engine.last_halt_reason || (isCritical ? 'CRITICAL mode: new trades are blocked' : null)
  );
  const noTrade = /NO TRADE/i.test(reason);
  const script = [
    'Hello Demo User. This is your Trade AI risk assistant.',
    'Your current portfolio is being monitored in paper trading mode.',
    `The current portfolio value is ${isMissing(snap.account_value) ? 'unavailable' : money(snap.account_value)}.`,
    `The current drawdown is ${isMissing(dd.drawdown_percentage ?? engine.current_drawdown) ? 'unavailable' : pct(dd.drawdown_percentage ?? engine.current_drawdown, true)}.`,
    `The current risk mode is ${mode || 'unavailable'}.`,
    `Risk Guardian cycle status is ${text(engine.last_cycle_status)}.`,
    'This is a simulated educational alert. No real phone call.',
  ].join(' ');

  function onSpeak() {
    if (!canSpeak()) {
      setSpeechNote('Speech synthesis unavailable in this browser. Text fallback is shown.');
      return;
    }
    const started = speak(script, {
      onStart: () => setSpeaking(true),
      onEnd: () => setSpeaking(false),
    });
    if (started) setSpeaking(true);
    setSpeechNote('');
  }

  function onStop() {
    stopSpeech();
    setSpeaking(false);
  }

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-40 w-[min(18rem,calc(100vw-2rem))]">
      <div className="pointer-events-auto rounded-lg border border-indigo-200 bg-indigo-50/95 p-3 shadow-lg">
        <div className="flex items-center gap-3">
          {active ? (
            <Volume2 className={`h-5 w-5 ${isCritical ? 'text-rose-600' : 'text-indigo-600'}`} />
          ) : (
            <VolumeX className="h-5 w-5 text-indigo-500" />
          )}
          <div className="flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-700">Voice alert</p>
            <p className="text-sm font-semibold text-foreground">
              <span
                className={`rounded px-1.5 py-0.5 text-[11px] ${
                  isCritical ? 'bg-rose-100 text-rose-800' : isProtection ? 'bg-amber-100 text-amber-900' : 'bg-white text-slate-700'
                }`}
              >
                {isCritical ? 'CRITICAL' : isProtection ? 'PROTECTION' : 'NORMAL'}
              </span>
              <span className="ml-1 text-[11px] font-medium text-indigo-600">· simulated</span>
            </p>
            {!isMissing(dd.drawdown_percentage ?? engine.current_drawdown) ? (
              <p className="mt-1 text-xs text-slate-600">Drawdown {pct(dd.drawdown_percentage ?? engine.current_drawdown, true)}</p>
            ) : null}
            {reason && !isMissing(reason) ? (
              <p className={`mt-1 text-xs ${noTrade ? 'font-semibold text-amber-800' : 'text-slate-600'}`}>{reason}</p>
            ) : null}
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={onSpeak}
            className="rounded border border-indigo-300 bg-indigo-600 px-2 py-1 text-[10px] font-bold uppercase text-white"
          >
            Speak
          </button>
          <button
            type="button"
            onClick={onStop}
            className={`rounded border px-2 py-1 text-[10px] font-bold uppercase ${
              speaking ? 'border-rose-300 bg-rose-50 text-rose-800' : 'border-slate-300 bg-white text-slate-700'
            }`}
          >
            Stop
          </button>
        </div>
        {speechNote ? <p className="mt-2 text-[10px] text-amber-800">{speechNote}</p> : null}
        <p className="mt-2 text-[10px] font-semibold uppercase text-indigo-800">Simulated AI voice · no real phone call</p>
      </div>
    </div>
  );
}
