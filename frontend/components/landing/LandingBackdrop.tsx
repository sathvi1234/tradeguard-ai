'use client';

import { useEffect } from 'react';

/** Decorative only. Never represents live quotes, returns, or Alpaca prices. */
export default function LandingBackdrop() {
  useEffect(() => {
    const sync = () => {
      document.documentElement.classList.toggle('lp-bg-paused', document.hidden);
    };
    sync();
    document.addEventListener('visibilitychange', sync);
    return () => document.removeEventListener('visibilitychange', sync);
  }, []);

  return (
    <div className="lp-backdrop" aria-hidden="true">
      <div className="lp-backdrop-gradient" />
      <div className="lp-backdrop-grid" />
      <svg className="lp-backdrop-svg" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="lpLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0" />
            <stop offset="35%" stopColor="#38bdf8" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#f97316" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <path
          className="lp-draw-line"
          d="M40 620 C 180 610, 220 480, 360 500 S 520 640, 680 520 S 900 300, 1080 360 S 1280 520, 1400 410"
          fill="none"
          stroke="url(#lpLine)"
          strokeWidth="1.6"
        />
        <path
          className="lp-draw-line lp-draw-line-delay"
          d="M20 740 C 160 700, 280 760, 420 690 S 640 580, 820 640 S 1100 780, 1420 700"
          fill="none"
          stroke="rgba(52,211,153,0.28)"
          strokeWidth="1.2"
        />
        <g className="lp-candles">
          <rect x="180" y="430" width="7" height="70" rx="1" />
          <rect x="210" y="400" width="7" height="95" rx="1" />
          <rect x="240" y="455" width="7" height="48" rx="1" />
          <rect x="270" y="390" width="7" height="110" rx="1" />
          <rect x="300" y="440" width="7" height="62" rx="1" />
          <rect x="980" y="220" width="6" height="80" rx="1" />
          <rect x="1006" y="200" width="6" height="108" rx="1" />
          <rect x="1032" y="245" width="6" height="54" rx="1" />
          <rect x="1058" y="210" width="6" height="92" rx="1" />
        </g>
        <g className="lp-nodes">
          <circle cx="360" cy="500" r="3.5" />
          <circle cx="680" cy="520" r="3.5" />
          <circle cx="1080" cy="360" r="3.5" />
          <circle cx="820" cy="640" r="3" />
          <line x1="360" y1="500" x2="680" y2="520" />
          <line x1="680" y1="520" x2="1080" y2="360" />
        </g>
        <circle className="lp-pulse" cx="680" cy="520" r="14" />
      </svg>
      <div className="lp-ticker">
        <span>DECORATIVE VISUALIZATION · NOT MARKET DATA · RISK GUARDIAN · ADVISORY AI · DEMO MONEY · DRY RUN · REAL-MONEY OFF · </span>
        <span>DECORATIVE VISUALIZATION · NOT MARKET DATA · RISK GUARDIAN · ADVISORY AI · DEMO MONEY · DRY RUN · REAL-MONEY OFF · </span>
      </div>
    </div>
  );
}
