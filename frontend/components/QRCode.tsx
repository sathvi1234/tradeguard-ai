'use client';

import { useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { publicAppUrl } from '@/lib/appUrl';

export default function QRCodeComponent() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [{ url, error }] = useState(() => publicAppUrl());

  useEffect(() => {
    if (!url || !canvasRef.current) return;
    QRCode.toCanvas(
      canvasRef.current,
      url,
      {
        width: 200,
        margin: 2,
        color: {
          dark: '#111111',
          light: '#F5F5F3',
        },
      },
      () => undefined
    );
  }, [url]);

  if (error || !url) {
    return (
      <div className="rounded-xl border border-amber-700 bg-amber-950/40 p-4 text-sm text-amber-200">
        <p className="font-semibold">QR code unavailable</p>
        <p className="mt-1 text-amber-100/90">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <canvas ref={canvasRef} className="max-w-full rounded bg-slate-200 p-2" />
      <p className="text-center text-[11px] font-semibold uppercase tracking-wide text-slate-400">Scan to open Trade AI</p>
      <p className="break-all text-center font-mono text-xs text-slate-300">{url}</p>
    </div>
  );
}
