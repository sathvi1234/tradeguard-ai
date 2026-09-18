'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { DEMO_EMAIL } from '@/lib/auth';
import TradingHeroImage from '@/components/TradingHeroImage';
import DemoBadges from '@/components/DemoBadges';

export default function SignInPage() {
  const { loginDemo, user, ready } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && user) {
      router.replace('/dashboard');
    }
  }, [ready, user, router]);

  async function enterDemo(asGuest: boolean) {
    setBusy(true);
    setError('');
    try {
      if (asGuest) {
        await loginDemo();
      } else {
        await loginDemo(email.trim() || DEMO_EMAIL, password);
      }
      router.push('/dashboard');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Demo sign-in failed';
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void enterDemo(false);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 lg:grid-cols-2">
        <div className="hidden lg:block">
          <p className="mb-3 text-sm font-bold tracking-tight text-foreground">TRADE AI</p>
          <p className="mb-4 text-sm text-slate-400">AI Trading Mentor & Simulator</p>
          <TradingHeroImage heightClass="h-[28rem]" />
        </div>
        <div className="mx-auto w-full max-w-md">
        <div className="mb-6 lg:hidden">
          <TradingHeroImage heightClass="h-40" />
        </div>
        <Link href="/" className="mb-8 inline-block text-sm text-slate-400 hover:text-white">
          ← Trade AI
        </Link>
        <h1 className="text-2xl font-bold text-foreground">Demo User</h1>
        <p className="mt-2 text-sm text-slate-400">Hackathon demo authentication. Paper trading and DRY_RUN stay on. Real-money trading stays off.</p>
        <DemoBadges className="mt-3" />

        <button
          type="button"
          disabled={busy}
          onClick={() => void enterDemo(true)}
          className="btn-primary mt-6 w-full rounded-xl py-3 disabled:opacity-50"
        >
          Continue as Demo User
        </button>
        <p className="mt-2 text-center text-xs text-slate-500">Demo User · {DEMO_EMAIL}</p>

        <div className="my-6 h-px bg-slate-800" />

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block text-sm">
            <span className="text-slate-300">Email</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={DEMO_EMAIL}
              className="tg-input mt-1"
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-300">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="tg-input mt-1"
            />
          </label>
          <p className="text-xs text-slate-500">Use the demo email. A password is not stored or validated against a secret.</p>
          <button
            type="submit"
            disabled={busy}
            className="btn-secondary w-full disabled:opacity-50"
          >
            Sign in
          </button>
        </form>
        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
        </div>
      </div>
    </div>
  );
}
