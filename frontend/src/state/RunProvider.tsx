import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { AgentRun } from '../api/schema';
import { useApi } from './api-context';
import { RunContext, type ActiveRun, type RunState } from './run-context';

/** Holds the run being watched and reveals its steps one by one, across page navigation. */
export function RunProvider({ children }: { children: ReactNode }) {
  const { client } = useApi();
  const [active, setActive] = useState<ActiveRun | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const stepMs = client.mode === 'demo' ? 420 : 140;

  const stop = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };

  const stream = useCallback(
    (run: AgentRun, note?: string) => {
      stop();
      const total = run.steps.length;
      setActive({ run, revealed: total ? 1 : 0, streaming: total > 1, ...(note ? { note } : {}) });
      if (total <= 1) return;
      timer.current = setInterval(() => {
        setActive((a) => {
          if (!a || a.run.id !== run.id) return a;
          const revealed = Math.min(total, a.revealed + 1);
          if (revealed >= total) stop();
          return { ...a, revealed, streaming: revealed < total };
        });
      }, stepMs);
    },
    [stepMs],
  );

  useEffect(() => stop, []);

  const start = useCallback(
    async (cityId: string) => {
      setStarting(cityId);
      setError(null);
      try {
        const res = await client.runAgents(cityId);
        stream(res.run, res.note);
        return res.run;
      } catch (e) {
        setError((e as Error).message);
        return null;
      } finally {
        setStarting(null);
      }
    },
    [client, stream],
  );

  const value = useMemo<RunState>(
    () => ({
      active,
      starting,
      error,
      start,
      show: (run) => {
        stop();
        setActive({ run, revealed: run.steps.length, streaming: false });
      },
      skip: () => {
        stop();
        setActive((a) => (a ? { ...a, revealed: a.run.steps.length, streaming: false } : a));
      },
      clearError: () => setError(null),
    }),
    [active, starting, error, start],
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
