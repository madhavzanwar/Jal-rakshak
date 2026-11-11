import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { RainPoint } from '../../api/schema';
import { fmtHour, fmtTime } from '../../lib/format';
import { AXIS, GRID, TOOLTIP_STYLE } from './theme';

/** Hourly precipitation bars; bar shade deepens with intensity (sequential, single hue). */
function shade(mm: number): string {
  if (mm >= 15) return '#1d4ed8';
  if (mm >= 7.5) return '#2563eb';
  if (mm >= 2.5) return '#3b82f6';
  return '#60a5fa';
}

export default function RainfallChart({ points, height = 150 }: { points: RainPoint[]; height?: number }) {
  const total = points.reduce((s, p) => s + p.mm, 0);
  return (
    <div style={{ height }} role="img" aria-label={`Hourly rainfall forecast, ${total.toFixed(0)} mm total over 72 hours`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barCategoryGap={1}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="t" tickFormatter={fmtHour} interval={11} {...AXIS} tickLine={false} />
          <YAxis {...AXIS} tickLine={false} width={44} unit="" />
          <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: 'rgba(148,163,184,0.08)' }} labelFormatter={(l) => `${fmtTime(String(l))} IST`} formatter={(v) => [`${Number(v).toFixed(1)} mm`, 'Rain']} />
          <Bar dataKey="mm" isAnimationActive={false} radius={[2, 2, 0, 0]} shape={(props: unknown) => {
            const p = props as { x: number; y: number; width: number; height: number; payload: RainPoint };
            return <rect x={p.x} y={p.y} width={Math.max(1, p.width)} height={Math.max(0, p.height)} rx={1.5} fill={shade(p.payload.mm)} />;
          }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
