import { Clock3 } from 'lucide-react';

export function StaleBadge({ ageMinutes, className = '' }: { ageMinutes?: number | null; className?: string }) {
  return (
    <span
      role="status"
      data-testid="stale-badge"
      className={`inline-flex items-center gap-1.5 rounded-md border border-amber-400/50 bg-amber-400/15 px-2 py-1 text-xs font-medium text-amber-200 ${className}`}
    >
      <Clock3 className="h-3.5 w-3.5" aria-hidden />
      Stale data — showing last known values{ageMinutes != null ? ` (age ${Math.round(ageMinutes)} min)` : ''}
    </span>
  );
}
