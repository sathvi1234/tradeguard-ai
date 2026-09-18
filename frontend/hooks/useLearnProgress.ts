'use client';

import { useCallback, useEffect, useState } from 'react';
import { CHALLENGES, LESSONS } from '@/lib/learn/content';
import {
  addUnique,
  emptyProgress,
  readProgress,
  writeProgress,
  type LearnProgress,
  type SimulationRecord,
} from '@/lib/learn/progress';

export function useLearnProgress() {
  const [progress, setProgress] = useState<LearnProgress>(emptyProgress);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setProgress(readProgress());
    setReady(true);
  }, []);

  const commit = useCallback((next: LearnProgress) => {
    setProgress(writeProgress(next));
  }, []);

  const completeLesson = useCallback(
    (lessonId: string) => {
      const lesson = LESSONS.find((item) => item.id === lessonId);
      commit({
        ...progress,
        lessonsCompleted: addUnique(progress.lessonsCompleted, lessonId),
        conceptsLearned: lesson ? addUnique(progress.conceptsLearned, lesson.concept) : progress.conceptsLearned,
      });
    },
    [commit, progress]
  );

  const completeChallenge = useCallback(
    (challengeId: string) => {
      const challenge = CHALLENGES.find((item) => item.id === challengeId);
      commit({
        ...progress,
        challengesCompleted: addUnique(progress.challengesCompleted, challengeId),
        conceptsLearned: challenge ? addUnique(progress.conceptsLearned, challenge.concept) : progress.conceptsLearned,
      });
    },
    [commit, progress]
  );

  const recordSimulation = useCallback(
    (row: Omit<SimulationRecord, 'id' | 'timestamp' | 'label'>) => {
      const record: SimulationRecord = {
        ...row,
        id: `sim-${Date.now()}`,
        timestamp: new Date().toISOString(),
        label: 'SIMULATION',
      };
      commit({ ...progress, simulations: [record, ...progress.simulations].slice(0, 50) });
    },
    [commit, progress]
  );

  return { progress, ready, completeLesson, completeChallenge, recordSimulation };
}
