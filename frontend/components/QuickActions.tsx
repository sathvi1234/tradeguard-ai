'use client';

import Link from 'next/link';

const ACTIONS = [
  { href: '/stock-analytics', label: 'Analyze Stock' },
  { href: '/ai-debate', label: 'Run AI Debate' },
  { href: '/trade-simulator', label: 'Simulate Buy' },
  { href: '/portfolio', label: 'Portfolio' },
  { href: '/copilot', label: 'Ask Copilot' },
  { href: '/call-agent', label: 'Start AI Call' },
  { href: '/learn/simulator', label: 'What-If Simulator' },
];

export default function QuickActions() {
  return (
    <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Quick actions</h2>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-lg border border-slate-600 px-3 py-2 text-xs font-semibold text-slate-100 hover:border-sky-500"
          >
            {item.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
