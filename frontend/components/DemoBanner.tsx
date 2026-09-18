'use client';

import Link from 'next/link';
import { useDemoMode } from '@/hooks/useDemoMode';

export default function DemoBanner() {
  const { enabled, scene, setScene, setEnabled } = useDemoMode();
  if (!enabled) return null;

  return (
    <div className="sticky top-0 z-[60] border-b border-line bg-primary-soft px-4 py-2 text-foreground">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide">
          DEMO MODE · NO LIVE TRADING · PAPER / DRY_RUN ONLY · values marked SIMULATED are not live paper account data
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Link href="/demo" className="rounded-full border border-line bg-surface px-2 py-1 font-semibold hover:border-primary hover:text-primary">
            Demo walkthrough
          </Link>
          <button
            type="button"
            onClick={() => setScene(scene === 'critical' ? 'protection' : 'critical')}
            className="rounded-full border border-line bg-surface px-2 py-1 font-semibold hover:border-primary hover:text-primary"
          >
            {scene === 'critical' ? 'Show PROTECTION (SIMULATED)' : 'Show CRITICAL (SIMULATED)'}
          </button>
          <button
            type="button"
            onClick={() => setEnabled(false)}
            className="rounded-full bg-primary px-2 py-1 font-semibold text-white hover:bg-primary-hover"
          >
            Exit demo
          </button>
        </div>
      </div>
    </div>
  );
}

export function SimulatedMark() {
  return (
    <span className="ml-2 inline-flex rounded-full border border-line bg-warning/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-warning">
      SIMULATED
    </span>
  );
}
