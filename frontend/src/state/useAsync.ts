import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => void;
}

/**
 * Minimal data hook: re-runs `fn` when deps change, keeps the previous data while
 * reloading (no flicker during replay playback) and ignores out-of-order responses.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[], opts: { enabled?: boolean; pollMs?: number } = {}): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);
  const enabled = opts.enabled ?? true;
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled) return;
    const my = ++seq.current;
    setLoading(true);
    fnRef
      .current()
      .then((d) => {
        if (my !== seq.current) return;
        setData(d);
        setError(undefined);
      })
      .catch((e: Error) => {
        if (my !== seq.current) return;
        setError(e);
      })
      .finally(() => {
        if (my === seq.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled]);

  useEffect(() => {
    if (!opts.pollMs || !enabled) return;
    const id = setInterval(() => setTick((t) => t + 1), opts.pollMs);
    return () => clearInterval(id);
  }, [opts.pollMs, enabled]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
