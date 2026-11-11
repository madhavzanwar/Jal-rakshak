import { createContext, useContext } from 'react';
import type { AgentRun } from '../api/schema';

export interface ActiveRun {
  run: AgentRun;
  /** Number of steps revealed so far (streaming effect). */
  revealed: number;
  streaming: boolean;
  note?: string;
}

export interface RunState {
  active: ActiveRun | null;
  starting: string | null; // city id being started
  error: string | null;
  start: (cityId: string) => Promise<AgentRun | null>;
  show: (run: AgentRun) => void;
  skip: () => void;
  clearError: () => void;
}

export const RunContext = createContext<RunState | null>(null);

export function useRuns(): RunState {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error('useRuns must be used inside <RunProvider>');
  return ctx;
}
