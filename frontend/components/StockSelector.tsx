'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { WATCHLIST, isValidSymbol, normalizeSymbol } from '@/lib/symbols';

export default function StockSelector({
  value,
  onChange,
  label = 'Select Stock',
}: {
  value: string;
  onChange: (symbol: string) => void;
  label?: string;
}) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [invalid, setInvalid] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    function onDoc(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const matches = useMemo(() => {
    const q = normalizeSymbol(query);
    if (!q) return [...WATCHLIST];
    const fromList = WATCHLIST.filter((item) => item.includes(q));
    if (q && isValidSymbol(q) && !fromList.includes(q as (typeof WATCHLIST)[number])) {
      return [q, ...fromList];
    }
    return fromList;
  }, [query]);

  function commit(next: string) {
    const symbol = normalizeSymbol(next);
    if (!isValidSymbol(symbol)) {
      setInvalid('INVALID SYMBOL');
      return;
    }
    setInvalid('');
    setQuery(symbol);
    setOpen(false);
    onChange(symbol);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    commit(query);
  }

  return (
    <div className="relative" ref={rootRef}>
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => {
            setQuery(normalizeSymbol(e.target.value));
            setOpen(true);
            setInvalid('');
          }}
          onFocus={() => setOpen(true)}
          placeholder="Search stocks..."
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm uppercase text-white"
          aria-label="Search stocks"
        />
        <button type="submit" className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold uppercase text-white">
          Load
        </button>
      </form>
      {invalid ? <p className="mt-1 text-xs font-semibold text-rose-300">{invalid}</p> : null}
      {open ? (
        <ul className="absolute z-30 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-slate-700 bg-slate-900 text-sm shadow-xl">
          {matches.length === 0 ? (
            <li className="px-3 py-2 text-slate-500">No matching symbols</li>
          ) : (
            matches.map((item) => (
              <li key={item}>
                <button
                  type="button"
                  className={`w-full px-3 py-2 text-left hover:bg-slate-800 ${item === value ? 'text-sky-300' : 'text-white'}`}
                  onClick={() => commit(item)}
                >
                  {item}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
