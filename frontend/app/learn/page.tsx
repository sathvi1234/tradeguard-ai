'use client';

import Link from 'next/link';
import { LearnShell } from '@/components/LearnShell';
import { LEARNING_LOOP } from '@/lib/learn/content';
import { useLearnProgress } from '@/hooks/useLearnProgress';

export default function LearnHubPage() {
  const { progress } = useLearnProgress();
  const topics = ['Stocks', 'Options', 'Calls & Puts', 'Greeks', 'Risk', 'Spreads', 'IV', 'Hedging', 'Portfolio Risk'];

  return (
    <LearnShell title="Learning Center">
      <p className="text-sm text-slate-400">Beginner · Intermediate · Advanced. Educational simulation only.</p>
      <div className="flex flex-wrap gap-2">
        {['Beginner', 'Intermediate', 'Advanced'].map((level) => (
          <Link key={level} href="/learn/path" className="rounded-full border border-teal-700 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-teal-200">
            {level}
          </Link>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {topics.map((topic) => (
          <Link key={topic} href="/learn/path" className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-200">
            {topic}
          </Link>
        ))}
      </div>
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {LEARNING_LOOP.map((step, index) => (
          <li key={step} className="rounded-xl border border-teal-800 bg-teal-950/40 px-3 py-4 text-center">
            <p className="text-[10px] uppercase tracking-wide text-teal-400">{index + 1}</p>
            <p className="mt-1 text-xs font-bold text-white">{step}</p>
          </li>
        ))}
      </ol>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Link href="/learn/mentor" className="rounded-xl border border-slate-700 bg-slate-900/70 p-5 hover:border-teal-600">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300">AI Trading Mentor</h2>
          <p className="mt-2 text-sm text-slate-300">Concepts, options basics, calls/puts, Greeks, risk, strategies. Scripted education, not advice.</p>
        </Link>
        <Link href="/learn/simulator" className="rounded-xl border border-slate-700 bg-slate-900/70 p-5 hover:border-teal-600">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300">Interactive + What-If Simulator</h2>
          <p className="mt-2 text-sm text-slate-300">SIMULATION only. Price, volatility, DTE, and drawdown shocks with labeled assumptions.</p>
        </Link>
        <Link href="/learn/path" className="rounded-xl border border-slate-700 bg-slate-900/70 p-5 hover:border-teal-600">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300">Learning path</h2>
          <p className="mt-2 text-sm text-slate-300">Beginner, Intermediate, Advanced lesson tracks.</p>
        </Link>
        <Link href="/learn/challenges" className="rounded-xl border border-slate-700 bg-slate-900/70 p-5 hover:border-teal-600">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300">Challenges</h2>
          <p className="mt-2 text-sm text-slate-300">Simulated decision-making scenarios with an AI Trade Coach explanation.</p>
        </Link>
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Progress snapshot</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Lessons completed" value={progress.lessonsCompleted.length} />
          <Stat label="Challenges completed" value={progress.challengesCompleted.length} />
          <Stat label="Concepts learned" value={progress.conceptsLearned.length} />
          <Stat label="Simulation results" value={progress.simulations.length} />
        </div>
        <Link href="/learn/progress" className="mt-3 inline-block text-sm text-teal-300 hover:text-white">
          Open full progress
        </Link>
      </section>
    </LearnShell>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}
