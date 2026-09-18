'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { copilot } from '@/lib/api';
import { text } from '@/lib/format';

const EXAMPLES = [
  'What is my portfolio?',
  'Why was my trade rejected?',
  'Explain my drawdown.',
  'Explain the latest AI debate.',
  'What are my biggest risks?',
  'Analyze this stock.',
];

type CopilotReply = {
  answer?: string;
  unavailable?: string[];
  sources?: string[];
  can_execute?: boolean;
};

export default function CopilotPage() {
  const [question, setQuestion] = useState(EXAMPLES[0]);
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; text: string }[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function ask(next = question) {
    setBusy(true);
    setError('');
    setMessages((prev) => [...prev, { role: 'user', text: next }]);
    try {
      const response = await copilot.ask(next);
      const reply = response.data as CopilotReply;
      const answer = `${text(reply.answer)}\n\ncan_execute: ${String(reply.can_execute === true)}`;
      setMessages((prev) => [...prev, { role: 'assistant', text: answer }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Copilot unavailable');
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask();
  }

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Quant Copilot</h1>
        <p className="mt-2 text-sm text-slate-400">
          Ask Trade AI about portfolio, decisions and risk. LLM is explanatory only. Copilot never executes trades and cannot place an order.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
        />
        <button type="submit" disabled={busy || !question.trim()} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          Ask Copilot
        </button>
      </form>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((item) => (
          <button
            key={item}
            type="button"
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-sky-600"
            onClick={() => {
              setQuestion(item);
              void ask(item);
            }}
          >
            {item}
          </button>
        ))}
      </div>
      {error ? <p className="text-sm text-amber-300">MARKET DATA ERROR: {error}</p> : null}
      <div className="space-y-3">
        {messages.map((item, index) => (
          <section
            key={`${item.role}-${index}`}
            className={`rounded-xl border p-4 text-sm ${item.role === 'user' ? 'border-slate-700 bg-slate-950' : 'border-slate-800 bg-slate-900'}`}
          >
            <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{item.role === 'user' ? 'You' : 'Trade AI Copilot'}</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-200">{item.text}</p>
          </section>
        ))}
      </div>
      <Link href="/dashboard" className="inline-block text-sm text-sky-300">
        Back to overview
      </Link>
    </main>
  );
}
