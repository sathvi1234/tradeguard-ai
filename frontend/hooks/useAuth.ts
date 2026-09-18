'use client';

import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import api from '@/lib/api';
import { DEMO_EMAIL, clearSession, readSession, writeSession, type DemoSession } from '@/lib/auth';

export function useAuth() {
  const [user, setUser] = useState<DemoSession | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sync = () => setUser(readSession());
    sync();
    setReady(true);
    window.addEventListener('tradeai-auth', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('tradeai-auth', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const loginDemo = useCallback(async (email?: string, password?: string) => {
    const payload = email
      ? { email, password: password || undefined, continue_as_demo: false }
      : { continue_as_demo: true };
    try {
      const response = await api.post('/api/v1/auth/demo', payload);
      const userBody = response.data?.user;
      const session: DemoSession = {
        name: String(userBody?.name || 'Demo User'),
        email: String(userBody?.email || DEMO_EMAIL),
        role: 'demo',
        paper_trading: true,
        dry_run: true,
        live_trading: false,
      };
      writeSession(session);
      setUser(session);
      return session;
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail || err.response?.data?.error || err.message;
        throw new Error(String(detail));
      }
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  return { user, ready, loginDemo, logout };
}
