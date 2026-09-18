'use client';

import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { LearnShell } from '@/components/LearnShell';
import { useLearnProgress } from '@/hooks/useLearnProgress';
import {
  DEFAULT_SIM,
  WHAT_IF_SHOCKS,
  coachFeedback,
  estimateSimulatedPnl,
  maxLossSimulated,
  signedGreeks,
  type OptionSide,
  type Direction,
  type SimInputs,
  type WhatIfShock,
} from '@/lib/learn/simulate';

export default function SimulatorPage() {
  const { recordSimulation } = useLearnProgress();
  const [inputs, setInputs] = useState<SimInputs>(DEFAULT_SIM);
  const [shock, setShock] = useState<WhatIfShock>(WHAT_IF_SHOCKS[1]);
  const [ran, setRan] = useState(false);

  const greeks = signedGreeks(inputs);
  const pnl = useMemo(() => estimateSimulatedPnl(inputs, shock), [inputs, shock]);
  const coach = useMemo(() => coachFeedback(inputs, shock, pnl), [inputs, shock, pnl]);
  const maxLoss = maxLossSimulated(inputs);

  function run() {
    setRan(true);
    recordSimulation({
      shock: shock.label,
      pnl,
      side: inputs.side,
      direction: inputs.direction,
    });
  }

  return (
    <LearnShell title="Interactive simulator">
      <p className="rounded-lg border border-amber-700 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
        EDUCATIONAL SIMULATION — not a broker order. First-order + gamma approximation. Assumptions are listed on each shock. No live trading.
      </p>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Classroom position</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <Field label="Side">
              <select
                className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
                value={inputs.side}
                onChange={(e) => setInputs({ ...inputs, side: e.target.value as OptionSide })}
              >
                <option value="call">Call</option>
                <option value="put">Put</option>
              </select>
            </Field>
            <Field label="Direction">
              <select
                className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
                value={inputs.direction}
                onChange={(e) => setInputs({ ...inputs, direction: e.target.value as Direction })}
              >
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </Field>
            <Num label="Qty" value={inputs.qty} onChange={(qty) => setInputs({ ...inputs, qty })} />
            <Num label="Spot" value={inputs.spot} onChange={(spot) => setInputs({ ...inputs, spot })} />
            <Num label="Strike" value={inputs.strike} onChange={(strike) => setInputs({ ...inputs, strike })} />
            <Num label="Premium" value={inputs.premium} onChange={(premium) => setInputs({ ...inputs, premium })} />
            <Num label="|Delta|" value={inputs.delta} onChange={(delta) => setInputs({ ...inputs, delta })} />
            <Num label="|Gamma|" value={inputs.gamma} onChange={(gamma) => setInputs({ ...inputs, gamma })} />
            <Num label="|Vega|" value={inputs.vega} onChange={(vega) => setInputs({ ...inputs, vega })} />
            <Num label="|Theta|" value={inputs.theta} onChange={(theta) => setInputs({ ...inputs, theta })} />
            <Num label="DTE" value={inputs.dte} onChange={(dte) => setInputs({ ...inputs, dte })} />
            <Num label="IV %" value={inputs.iv} onChange={(iv) => setInputs({ ...inputs, iv })} />
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Signed classroom Greeks: Δ {greeks.delta.toFixed(2)} Γ {greeks.gamma.toFixed(3)} ν {greeks.vega.toFixed(2)} Θ{' '}
            {greeks.theta.toFixed(2)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">What-If Analysis</h2>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {WHAT_IF_SHOCKS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setShock(item);
                  setRan(false);
                }}
                className={`rounded-lg border px-3 py-2 text-left text-sm ${
                  shock.id === item.id ? 'border-teal-500 bg-teal-950/50 text-teal-100' : 'border-slate-700 text-slate-300'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <p className="mt-3 text-xs text-amber-200">{shock.assumption}</p>
          <button type="button" onClick={run} className="mt-4 w-full rounded-lg bg-teal-700 py-2 text-sm font-semibold text-white">
            Run SIMULATION
          </button>
        </div>
      </section>

      {ran ? (
        <section className="space-y-4">
          <div className="rounded-xl border border-amber-600 bg-amber-950/30 p-5">
            <p className="text-[10px] font-bold uppercase tracking-wide text-amber-300">SIMULATION result · not executed</p>
            <p className="mt-2 text-[11px] uppercase tracking-wide text-slate-500">Scenario</p>
            <p className="text-white">{shock.label}</p>
            <p className="mt-2 text-[11px] uppercase tracking-wide text-slate-500">Assumptions</p>
            <p className="text-sm text-slate-300">{shock.assumption}</p>
            <p className="mt-2 text-3xl font-bold text-white">
              {pnl < 0 ? '-' : ''}${Math.abs(pnl).toFixed(2)}
            </p>
            <p className="mt-1 text-sm text-slate-300">
              Potential portfolio impact (classroom): {pnl < 0 ? '-' : ''}${Math.abs(pnl).toFixed(2)} estimated P&amp;L. Classroom max loss (long premium only): {Number.isFinite(maxLoss) ? `$${maxLoss.toFixed(2)}` : 'uncapped in this model (short)'}
            </p>
            {shock.extraDrawdownPct ? (
              <p className="mt-2 text-sm text-rose-200">
                Risk impact: educational drawdown overlay {(shock.extraDrawdownPct * 100).toFixed(0)}% (SIMULATION assumption, not your account).
              </p>
            ) : (
              <p className="mt-2 text-sm text-slate-400">Risk impact: held constant except the selected shock.</p>
            )}
            <p className="mt-2 text-xs text-slate-400">Educational explanation: this is a first-order + gamma classroom estimate. SIMULATION ONLY. No broker execution.</p>
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300">AI Trade Coach</h2>
            <p className="mt-1 text-xs text-slate-500">Scripted feedback from the simulation engine. Not personalized financial advice.</p>
            <CoachBlock title="What happened?" text={coach.whatHappened} />
            <CoachBlock title="Why?" text={coach.why} />
            <CoachList title="What risk was involved?" items={coach.risks} />
            <CoachBlock title="What could change the result?" text={coach.couldChange} />
            <CoachBlock title="What did I learn?" text={coach.learned} />
            <CoachList title="Alternatives" items={coach.alternatives} />
            <p className="mt-4 text-[10px] font-bold uppercase tracking-wide text-amber-300">Educational Simulation</p>
          </div>
        </section>
      ) : (
        <p className="text-sm text-slate-500">Choose a shock and run the SIMULATION to unlock AI Trade Coach notes.</p>
      )}
    </LearnShell>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-xs text-slate-400">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Num({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return (
    <Field label={label}>
      <input
        type="number"
        className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-white"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Field>
  );
}

function CoachBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <p className="mt-1 text-sm text-slate-200">{text}</p>
    </div>
  );
}

function CoachList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
