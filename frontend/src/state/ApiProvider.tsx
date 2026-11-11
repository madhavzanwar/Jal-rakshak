import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { HttpClient } from '../api/http';
import { DemoClient } from '../api/demo';
import type { Health } from '../api/schema';
import { ApiContext, type ApiState } from './api-context';
import { demoRequested, scenarioUrl } from './mode';
import { Logo } from '../components/Logo';

type Boot =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'ready'; client: HttpClient | DemoClient; demo: DemoClient | null; health: Health | null; fallbackReason: string | null };

async function loadDemo(): Promise<DemoClient> {
  try {
    return await DemoClient.load(scenarioUrl());
  } catch (e) {
    if (import.meta.env.DEV) {
      // Dev-only fallback: the small hand-written fixture (tree-shaken from production builds).
      const { fixtureScenario } = await import('../demo/__fixtures__/fixture');
      console.warn('[demo] scenario.json unavailable, using dev fixture:', (e as Error).message);
      return new DemoClient(fixtureScenario, { latencyMs: 80 });
    }
    throw e;
  }
}

async function boot(): Promise<Boot> {
  if (demoRequested()) {
    const demo = await loadDemo();
    return { phase: 'ready', client: demo, demo, health: await demo.health(), fallbackReason: null };
  }
  const http = new HttpClient();
  try {
    const health = await http.health();
    return { phase: 'ready', client: http, demo: null, health, fallbackReason: null };
  } catch (e) {
    const demo = await loadDemo();
    return {
      phase: 'ready',
      client: demo,
      demo,
      health: await demo.health(),
      fallbackReason: `Live backend unreachable (${(e as Error).message}). Showing the offline demo replay.`,
    };
  }
}

export function ApiProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Boot>({ phase: 'loading' });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    boot()
      .then((b) => alive && setState(b))
      .catch((e: Error) => alive && setState({ phase: 'error', message: e.message }));
    return () => {
      alive = false;
    };
  }, []);

  const demo = state.phase === 'ready' ? state.demo : null;
  useEffect(() => {
    if (!demo) return;
    return demo.subscribe(() => setVersion((v) => v + 1));
  }, [demo]);

  const value = useMemo<ApiState | null>(
    () =>
      state.phase === 'ready'
        ? { client: state.client, demo: state.demo, health: state.health, fallbackReason: state.fallbackReason, version }
        : null,
    [state, version],
  );

  if (state.phase === 'loading') {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-900 text-slate-300" role="status" aria-live="polite">
        <div className="flex flex-col items-center gap-4">
          <Logo className="h-14 w-14 animate-pulse" />
          <p className="text-sm tracking-wide">Connecting to JalRakshak…</p>
        </div>
      </div>
    );
  }
  if (state.phase === 'error' || !value) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-900 p-6 text-slate-200">
        <div className="max-w-lg rounded-xl border border-red-500/40 bg-red-950/40 p-6">
          <h1 className="mb-2 text-lg font-semibold">JalRakshak could not start</h1>
          <p className="whitespace-pre-wrap text-sm text-slate-300">{state.phase === 'error' ? state.message : ''}</p>
          <p className="mt-4 text-sm">In an emergency call <a className="font-bold underline" href="tel:112">112</a>.</p>
        </div>
      </div>
    );
  }
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
}
