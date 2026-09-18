import type { ReactNode } from 'react';
import Link from 'next/link';
import { EDUCATIONAL_DISCLAIMER, SIMULATION } from '@/lib/learn/simulate';

export const LEARN_LINKS = [
  { href: '/learn', label: 'Learn hub' },
  { href: '/learn/mentor', label: 'AI Trading Mentor' },
  { href: '/learn/path', label: 'Learning path' },
  { href: '/learn/simulator', label: 'Simulator' },
  { href: '/learn/challenges', label: 'Challenges' },
  { href: '/learn/progress', label: 'Progress' },
];

export function LearnShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="pb-10">
      <div className="border-b border-slate-800 bg-slate-950/80">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-xl font-bold text-white sm:text-2xl">{title}</h1>
            <span className="rounded border border-amber-500 bg-amber-950 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-300">
              {SIMULATION}
            </span>
          </div>
          <nav className="flex flex-wrap gap-2 text-xs">
            {LEARN_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-slate-300 hover:border-teal-600 hover:text-white"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
      <p className="border-b border-slate-800 bg-slate-900/80 px-4 py-2 text-center text-xs text-slate-400">{EDUCATIONAL_DISCLAIMER}</p>
      <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
