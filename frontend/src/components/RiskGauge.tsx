import type { RiskLevel } from '../api/schema';
import { LEVEL_BANDS, LEVEL_COLORS, LEVEL_LABELS } from '../lib/levels';

/** Semicircular 0–100 gauge with level bands; the needle arc is coloured by the level. */
export function RiskGauge({ score, level, size = 220, caption }: { score: number; level: RiskLevel; size?: number; caption?: string }) {
  const r = 80;
  const cx = 100;
  const cy = 96;
  const pt = (v: number, rad = r) => {
    const a = Math.PI * (1 - v / 100);
    return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)] as const;
  };
  const arc = (from: number, to: number, rad = r) => {
    const [x1, y1] = pt(from, rad);
    const [x2, y2] = pt(to, rad);
    return `M ${x1} ${y1} A ${rad} ${rad} 0 0 1 ${x2} ${y2}`;
  };
  const clamped = Math.max(0, Math.min(100, score));
  const [nx, ny] = pt(clamped, r);
  return (
    <figure className="flex flex-col items-center" style={{ width: size }}>
      <svg viewBox="0 0 200 118" width={size} height={(size * 118) / 200} role="img" aria-label={`Risk score ${score.toFixed(1)} of 100, level ${level}`}>
        {LEVEL_BANDS.map((b) => (
          <path key={b.level} d={arc(b.from + 0.6, b.to - 0.6, r + 13)} stroke={LEVEL_COLORS[b.level]} strokeOpacity={0.35} strokeWidth={4} fill="none" />
        ))}
        <path d={arc(0, 100)} stroke="rgba(148,163,184,0.18)" strokeWidth={16} fill="none" strokeLinecap="round" />
        {clamped > 0.5 && <path d={arc(0, clamped)} stroke={LEVEL_COLORS[level]} strokeWidth={16} fill="none" strokeLinecap="round" />}
        <circle cx={nx} cy={ny} r={9} fill="#0b1220" stroke={LEVEL_COLORS[level]} strokeWidth={4} />
        {[0, 30, 55, 75, 100].map((v) => {
          const [x, y] = pt(v, r - 21);
          return (
            <text key={v} x={x} y={y + 3} textAnchor="middle" className="fill-slate-500" fontSize="8.5">
              {v}
            </text>
          );
        })}
      </svg>
      <div className="-mt-[52px] flex flex-col items-center">
        <span data-testid="risk-score" className="font-mono text-4xl font-bold tabular-nums leading-none text-white">
          {score.toFixed(1)}
        </span>
        <span data-testid="risk-level" data-level={level} className="mt-1.5 text-sm font-bold uppercase tracking-widest" style={{ color: LEVEL_COLORS[level] }}>
          {level} · {LEVEL_LABELS[level]}
        </span>
      </div>
      {caption && <figcaption className="mt-1 text-center text-[11px] text-slate-400">{caption}</figcaption>}
    </figure>
  );
}
