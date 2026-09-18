'use client';

import { LearnShell } from '@/components/LearnShell';
import { LESSONS, type LessonLevel } from '@/lib/learn/content';
import { useLearnProgress } from '@/hooks/useLearnProgress';

const LEVELS: { id: LessonLevel; title: string }[] = [
  { id: 'beginner', title: 'BEGINNER' },
  { id: 'intermediate', title: 'INTERMEDIATE' },
  { id: 'advanced', title: 'ADVANCED' },
];

export default function PathPage() {
  const { progress, completeLesson } = useLearnProgress();

  return (
    <LearnShell title="Learning path">
      {LEVELS.map((level) => (
        <section key={level.id} className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-teal-300">{level.title}</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {LESSONS.filter((lesson) => lesson.level === level.id).map((lesson) => {
              const done = progress.lessonsCompleted.includes(lesson.id);
              return (
                <article key={lesson.id} className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-white">{lesson.title}</h3>
                    {done ? <span className="text-[10px] font-bold uppercase text-emerald-400">Completed</span> : null}
                  </div>
                  <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">{lesson.concept}</p>
                  <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-300">
                    {lesson.body.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={() => completeLesson(lesson.id)}
                    className="mt-3 rounded border border-teal-700 px-3 py-1.5 text-xs font-semibold text-teal-200"
                  >
                    {done ? 'Completed' : 'Mark lesson complete'}
                  </button>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </LearnShell>
  );
}
