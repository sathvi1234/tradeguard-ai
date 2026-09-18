'use client';

import type { ReactNode } from 'react';

export default function DemoProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
