'use client';

import Link from 'next/link';

export default function CallAgentButton({
  symbol,
  className = '',
}: {
  symbol?: string;
  className?: string;
}) {
  const href = symbol ? `/call-agent?symbol=${encodeURIComponent(symbol)}` : '/call-agent';
  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-bold uppercase tracking-wide text-white shadow-lift hover:bg-primary-hover ${className}`}
    >
      🎙️ Call Agent
    </Link>
  );
}
