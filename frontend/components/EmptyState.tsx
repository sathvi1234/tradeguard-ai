'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';

export function EmptyState({
  title,
  body,
  href,
  action,
}: {
  title: string;
  body: string;
  href?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface p-4 shadow-card">
      <p className="font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted">{body}</p>
      {href ? (
        <Link href={href} className="btn-primary mt-3 text-xs">
          {typeof action === 'string' ? action : 'Continue'}
        </Link>
      ) : (
        action
      )}
    </div>
  );
}
