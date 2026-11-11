import type { GaugeStatus, RiskLevel } from '../api/schema';

/** Level colour tokens (shared with tailwind `lvl-*`). */
export const LEVEL_COLORS: Record<RiskLevel, string> = {
  green: '#16a34a',
  yellow: '#eab308',
  orange: '#f97316',
  red: '#dc2626',
};

export const LEVEL_LABELS: Record<RiskLevel, string> = {
  green: 'Low',
  yellow: 'Watch',
  orange: 'Alert',
  red: 'Severe',
};

/** Text colour that keeps WCAG AA contrast on top of the level colour. */
export const LEVEL_ON_COLORS: Record<RiskLevel, string> = {
  green: '#ffffff',
  yellow: '#1a1300',
  orange: '#1a0a00',
  red: '#ffffff',
};

export const LEVEL_ORDER: Record<RiskLevel, number> = { green: 0, yellow: 1, orange: 2, red: 3 };

/** Fixed contract cut-offs: green <30, yellow 30–54.99, orange 55–74.99, red >=75. */
export function levelForScore(score: number): RiskLevel {
  if (score >= 75) return 'red';
  if (score >= 55) return 'orange';
  if (score >= 30) return 'yellow';
  return 'green';
}

export function levelColor(level: RiskLevel): string {
  return LEVEL_COLORS[level];
}

export const LEVEL_BANDS: { level: RiskLevel; from: number; to: number }[] = [
  { level: 'green', from: 0, to: 30 },
  { level: 'yellow', from: 30, to: 55 },
  { level: 'orange', from: 55, to: 75 },
  { level: 'red', from: 75, to: 100 },
];

export const GAUGE_STATUS_LEVEL: Record<GaugeStatus, RiskLevel> = {
  normal: 'green',
  warning: 'yellow',
  danger: 'orange',
  extreme: 'red',
};
