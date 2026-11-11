/** Demo mode if VITE_DEMO=1 at build time, or ?demo=1 in the URL (before or inside the #hash). */
export function demoRequested(): boolean {
  if (import.meta.env.VITE_DEMO === '1') return true;
  if (typeof window === 'undefined') return false;
  const { search, hash } = window.location;
  if (new URLSearchParams(search).get('demo') === '1') return true;
  const q = hash.indexOf('?');
  return q >= 0 && new URLSearchParams(hash.slice(q + 1)).get('demo') === '1';
}

export function scenarioUrl(): string {
  return `${import.meta.env.BASE_URL}demo/scenario.json`;
}
