'use client';

type TradingHeroImageProps = {
  className?: string;
  heightClass?: string;
};

export default function TradingHeroImage({ className = '', heightClass = 'h-40 sm:h-56' }: TradingHeroImageProps) {
  return (
    <figure className={`overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/images/trading-command.png"
        alt="Illustrated trading command screens"
        className={`w-full ${heightClass} object-cover object-center`}
      />
      <figcaption className="border-t border-slate-800 px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Illustration only · not live account or market data
      </figcaption>
    </figure>
  );
}
