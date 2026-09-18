'use client';

import { useState } from 'react';
import { LearnShell } from '@/components/LearnShell';
import { MENTOR_TOPICS } from '@/lib/learn/content';
import { useLearnProgress } from '@/hooks/useLearnProgress';

export default function MentorPage() {
  const [topicId, setTopicId] = useState(MENTOR_TOPICS[0].id);
  const topic = MENTOR_TOPICS.find((item) => item.id === topicId) || MENTOR_TOPICS[0];
  const { completeLesson } = useLearnProgress();

  return (
    <LearnShell title="AI Trading Mentor">
      <p className="text-sm text-slate-400">
        Scripted educational mentor. It does not use your account. It does not give personalized financial advice.
      </p>
      <div className="flex flex-wrap gap-2">
        {MENTOR_TOPICS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTopicId(item.id)}
            className={`rounded-lg border px-3 py-2 text-sm ${
              item.id === topicId ? 'border-teal-500 bg-teal-950 text-teal-100' : 'border-slate-700 text-slate-300'
            }`}
          >
            {item.title}
          </button>
        ))}
      </div>
      <article className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
        <p className="text-[10px] font-bold uppercase tracking-wide text-amber-300">SIMULATION / EDUCATION</p>
        <h2 className="mt-2 text-lg font-semibold text-white">{topic.title}</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-200">
          {topic.explanation.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => completeLesson(topic.id === 'concepts' ? 'beg-market' : topic.id === 'calls-puts' ? 'beg-calls-puts' : topic.id === 'greeks' ? 'beg-greeks' : topic.id === 'risk' ? 'beg-risk' : topic.id === 'strategies' ? 'int-spreads' : 'beg-options')}
          className="mt-4 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white"
        >
          Mark concept learned
        </button>
      </article>
    </LearnShell>
  );
}
