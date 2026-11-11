const IST = 'Asia/Kolkata';

export function fmtTime(iso: string | null | undefined, opts: { date?: boolean } = {}): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-IN', {
    timeZone: IST,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...(opts.date !== false ? { day: '2-digit', month: 'short' } : {}),
  });
}

/** Compact axis tick: "1 Jul 05h" (IST). */
export function fmtHour(iso: string): string {
  const d = new Date(iso);
  const day = d.toLocaleString('en-GB', { timeZone: IST, day: 'numeric', month: 'short' });
  const hh = d.toLocaleString('en-GB', { timeZone: IST, hour: '2-digit', hour12: false });
  return `${day} ${hh}h`;
}

export function fmtDay(dateStr: string): string {
  const d = new Date(dateStr.length === 10 ? `${dateStr}T00:00:00Z` : dateStr);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'UTC' });
}

export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString('en-IN');
}

export function fmtCompact(n: number): string {
  if (n >= 1e7) return `${(n / 1e7).toFixed(1)} cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)} lakh`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(Math.round(n));
}

export function fmtDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

export function fmtDuration(s: number): string {
  const min = Math.round(s / 60);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

export function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
