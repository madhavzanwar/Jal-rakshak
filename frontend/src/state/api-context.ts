import { createContext, useContext } from 'react';
import type { ApiClient } from '../api/client';
import type { DemoClient } from '../api/demo';
import type { Health } from '../api/schema';

export interface ApiState {
  client: ApiClient;
  demo: DemoClient | null;
  health: Health | null;
  /** Set when we fell back to demo because the backend was unreachable. */
  fallbackReason: string | null;
  /** Increments whenever demo replay state changes (frame, alerts) → hooks refetch. */
  version: number;
}

export const ApiContext = createContext<ApiState | null>(null);

export function useApi(): ApiState {
  const ctx = useContext(ApiContext);
  if (!ctx) throw new Error('useApi must be used inside <ApiProvider>');
  return ctx;
}
