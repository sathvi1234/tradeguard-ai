'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  DEMO_EVENT,
  buildDemoBundle,
  isDemoEnabled,
  readDemoScene,
  writeDemoEnabled,
  writeDemoScene,
  type DemoScene,
} from '@/lib/demo';

export function useDemoMode() {
  const [enabled, setEnabledState] = useState(false);
  const [scene, setSceneState] = useState<DemoScene>('protection');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sync = () => {
      setEnabledState(isDemoEnabled());
      setSceneState(readDemoScene());
      setReady(true);
    };
    sync();
    window.addEventListener(DEMO_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(DEMO_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const bundle = useMemo(() => buildDemoBundle(scene), [scene]);

  return {
    ready,
    enabled,
    scene,
    bundle,
    setEnabled: (value: boolean) => writeDemoEnabled(value),
    setScene: (value: DemoScene) => writeDemoScene(value),
  };
}
