import { Area, AreaChart, CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { HorizonPoint } from '../../api/schema';
import { LEVEL_BANDS, LEVEL_COLORS, levelForScore } from '../../lib/levels';
import { fmtHour, fmtTime } from '../../lib/format';
import { AXIS, GRID, TOOLTIP_STYLE } from './theme';

/** 72-h risk horizon (3-hourly). Background bands show the fixed level cut-offs. */
export default function HorizonChart({ points, height = 170 }: { points: HorizonPoint[]; height?: number }) {
  const data = points.map((p) => ({ t: p.t, score: p.score }));
  const peak = points.reduce<HorizonPoint | null>((m, p) => (!m || p.score > m.score ? p : m), null);
  const max = Math.max(1, ...points.map((p) => p.score));
  const min = Math.min(...points.map((p) => p.score), max - 1);
  return (
    <div style={{ height }} role="img" aria-label={`72-hour risk horizon; peak ${peak?.score.toFixed(1) ?? '–'} at ${fmtTime(peak?.t)}`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <LevelGradient id="hz-fill" lo={0} hi={max} />
            <LevelGradient id="hz-stroke" lo={min} hi={max} />
          </defs>
          {LEVEL_BANDS.map((b) => (
            <ReferenceArea key={b.level} y1={b.from} y2={b.to} fill={LEVEL_COLORS[b.level]} fillOpacity={0.05} stroke="none" ifOverflow="hidden" />
          ))}
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="t" tickFormatter={fmtHour} interval={3} {...AXIS} tickLine={false} />
          <YAxis domain={[0, 100]} ticks={[0, 30, 55, 75, 100]} {...AXIS} tickLine={false} width={44} />
          <Tooltip
            {...TOOLTIP_STYLE}
            labelFormatter={(l) => `${fmtTime(String(l))} IST`}
            formatter={(v) => {
              const n = Number(v);
              return [`${n.toFixed(1)} (${levelForScore(n)})`, 'Risk score'];
            }}
          />
          {peak && <ReferenceLine x={peak.t} stroke="#e2e8f0" strokeDasharray="3 3" strokeOpacity={0.5} label={{ value: 'peak', position: 'insideTopRight', fill: '#cbd5e1', fontSize: 10 }} />}
          <Area type="monotone" dataKey="score" stroke="url(#hz-stroke)" strokeWidth={2} fill="url(#hz-fill)" fillOpacity={0.22} isAnimationActive={false} activeDot={{ r: 4, stroke: '#0b1220', strokeWidth: 2 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Hard-edged vertical gradient whose colour changes exactly at the level cut-offs.
 * objectBoundingBox spans [lo, hi] in score units, so offsets are computed in that range.
 */
function LevelGradient({ id, lo, hi }: { id: string; lo: number; hi: number }) {
  const span = Math.max(1e-6, hi - lo);
  const off = (v: number) => `${Math.max(0, Math.min(100, ((hi - v) / span) * 100))}%`;
  const stops: { o: string; c: string }[] = [];
  const bands = [...LEVEL_BANDS].reverse(); // red → green, top → bottom
  for (const b of bands) {
    stops.push({ o: off(b.to), c: LEVEL_COLORS[b.level] }, { o: off(b.from), c: LEVEL_COLORS[b.level] });
  }
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      {stops.map((s, i) => (
        <stop key={i} offset={s.o} stopColor={s.c} />
      ))}
    </linearGradient>
  );
}
