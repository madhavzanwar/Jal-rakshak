import type { RiskLevel } from '../api/schema';
import { LEVEL_COLORS, LEVEL_LABELS, LEVEL_ON_COLORS } from '../lib/levels';

export function LevelChip({ level, size = 'sm', label, testId }: { level: RiskLevel; size?: 'xs' | 'sm' | 'md' | 'lg'; label?: string; testId?: string }) {
  const pad = { xs: 'px-1.5 py-0 text-[10px]', sm: 'px-2 py-0.5 text-[11px]', md: 'px-2.5 py-1 text-xs', lg: 'px-3 py-1 text-sm' }[size];
  return (
    <span
      data-testid={testId}
      data-level={level}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full font-semibold uppercase tracking-wide ${pad}`}
      style={{ background: LEVEL_COLORS[level], color: LEVEL_ON_COLORS[level] }}
    >
      {label ?? `${level} · ${LEVEL_LABELS[level]}`}
    </span>
  );
}

export function LevelDot({ level, className = 'h-2.5 w-2.5' }: { level: RiskLevel; className?: string }) {
  return <span aria-hidden className={`inline-block shrink-0 rounded-full ${className}`} style={{ background: LEVEL_COLORS[level] }} />;
}
