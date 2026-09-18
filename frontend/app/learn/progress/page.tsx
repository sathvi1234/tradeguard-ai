'use client';

import { LearnShell } from '@/components/LearnShell';
import { CHALLENGES, LESSONS } from '@/lib/learn/content';
import { useLearnProgress } from '@/hooks/useLearnProgress';

export default function ProgressPage() {
  const { progress } = useLearnProgress();

  return (
    <LearnShell title="Learning progress">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card label="Lessons completed" value={`${progress.lessonsCompleted.length} / ${LESSONS.length}`} />
        <Card label="Challenges completed" value={`${progress.challengesCompleted.length} / ${CHALLENGES.length}`} />
        <Card label="Concepts learned" value={String(progress.conceptsLearned.length)} />
        <Card label="Simulation results" value={String(progress.simulations.length)} />
      </div>

      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Concepts learned</h2>
        {progress.conceptsLearned.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">None yet. Complete a lesson or challenge.</p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-2">
            {progress.conceptsLearned.map((concept) => (
              <li key={concept} className="rounded border border-teal-800 bg-teal-950/40 px-2 py-1 text-xs text-teal-100">
                {concept}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Simulation results</h2>
        {progress.simulations.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No classroom simulations recorded yet.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {progress.simulations.map((row) => (
              <li key={row.id} className="rounded border border-slate-800 bg-slate-950/40 p-3">
                <p className="text-[10px] font-bold uppercase text-amber-300">{row.label}</p>
                <p className="text-white">
                  {row.direction} {row.side} · {row.shock} · {row.pnl < 0 ? '-' : ''}${Math.abs(row.pnl).toFixed(2)}
                </p>
                <p className="text-xs text-slate-500">{row.timestamp}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </LearnShell>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}
