'use client';

import { useState } from 'react';
import { LearnShell } from '@/components/LearnShell';
import { CHALLENGES } from '@/lib/learn/content';
import { useLearnProgress } from '@/hooks/useLearnProgress';

export default function ChallengesPage() {
  const { progress, completeChallenge } = useLearnProgress();
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});

  return (
    <LearnShell title="Simulated decision challenges">
      <p className="text-sm text-slate-400">
        Classroom scenarios only. Correct answers teach the simulator’s labeled assumptions. Not personalized financial advice.
      </p>
      <div className="space-y-4">
        {CHALLENGES.map((challenge) => {
          const picked = picks[challenge.id];
          const show = revealed[challenge.id];
          const correct = picked === challenge.correctIndex;
          const done = progress.challengesCompleted.includes(challenge.id);
          return (
            <article key={challenge.id} className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold text-white">{challenge.title}</h2>
                {done ? <span className="text-[10px] font-bold uppercase text-emerald-400">Completed</span> : null}
              </div>
              <p className="mt-2 text-sm text-slate-300">{challenge.prompt}</p>
              <div className="mt-3 space-y-2">
                {challenge.choices.map((choice, index) => (
                  <button
                    key={choice}
                    type="button"
                    onClick={() => setPicks({ ...picks, [challenge.id]: index })}
                    className={`block w-full rounded-lg border px-3 py-2 text-left text-sm ${
                      picked === index ? 'border-teal-500 bg-teal-950/40 text-teal-100' : 'border-slate-700 text-slate-300'
                    }`}
                  >
                    {choice}
                  </button>
                ))}
              </div>
              <button
                type="button"
                disabled={picked === undefined}
                onClick={() => {
                  setRevealed({ ...revealed, [challenge.id]: true });
                  if (picked === challenge.correctIndex) completeChallenge(challenge.id);
                }}
                className="mt-3 rounded bg-teal-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
              >
                Check answer (SIMULATION)
              </button>
              {show ? (
                <div className="mt-3 rounded border border-slate-700 bg-slate-950/50 p-3 text-sm">
                  <p className={correct ? 'font-semibold text-emerald-300' : 'font-semibold text-rose-300'}>
                    {correct ? 'Correct (classroom)' : 'Not the classroom answer'}
                  </p>
                  <p className="mt-2 text-slate-300">{challenge.explanation}</p>
                  <p className="mt-2 text-xs text-slate-500">AI Trade Coach note: review the matching What-If shock in the simulator next.</p>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </LearnShell>
  );
}
