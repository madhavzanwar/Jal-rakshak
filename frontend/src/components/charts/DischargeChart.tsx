import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { GaugeReading } from '../../api/schema';
import { LEVEL_COLORS } from '../../lib/levels';
import { fmtDay, fmtInt } from '../../lib/format';
import { AXIS, GRID, TOOLTIP_STYLE } from './theme';

/** River discharge (past 7 + forecast 7 days) against warning/danger/extreme thresholds. */
export default function DischargeChart({ reading, today, height = 130 }: { reading: GaugeReading; today?: string; height?: number }) {
  const g = reading.gauge;
  const max = Math.max(g.extreme_m3s * 1.05, ...reading.series.map((p) => p.m3s));
  const min = Math.min(...reading.series.map((p) => p.m3s), g.warning_m3s) * 0.85;
  const fmtK = (v: number) => (v >= 10_000 ? `${Math.round(v / 1000)}k` : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v)));
  const refs = [
    { v: g.warning_m3s, c: LEVEL_COLORS.yellow, l: 'warning' },
    { v: g.danger_m3s, c: LEVEL_COLORS.orange, l: 'danger' },
    { v: g.extreme_m3s, c: LEVEL_COLORS.red, l: 'extreme' },
  ];
  return (
    <div style={{ height }} role="img" aria-label={`${g.river} discharge; peak ${fmtInt(reading.peak_m3s)} cubic metres per second on ${reading.peak_date}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={reading.series} margin={{ top: 6, right: 52, bottom: 0, left: -12 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={fmtDay} interval={2} {...AXIS} tickLine={false} />
          <YAxis domain={[Math.floor(min), Math.ceil(max)]} tickFormatter={fmtK} {...AXIS} tickLine={false} width={48} />
          <Tooltip {...TOOLTIP_STYLE} labelFormatter={(l) => fmtDay(String(l))} formatter={(v) => [`${fmtInt(Number(v))} m³/s`, 'Discharge']} />
          {refs.map((r) => (
            <ReferenceLine key={r.l} y={r.v} stroke={r.c} strokeDasharray="4 3" strokeOpacity={0.85} ifOverflow="extendDomain" label={{ value: r.l, position: 'right', fill: '#cbd5e1', fontSize: 10 }} />
          ))}
          {today && <ReferenceLine x={today} stroke="#94a3b8" strokeOpacity={0.5} label={{ value: 'today', position: 'insideTopLeft', fill: '#94a3b8', fontSize: 10 }} />}
          <Line type="monotone" dataKey="m3s" stroke="#7dd3fc" strokeWidth={2} dot={false} isAnimationActive={false} activeDot={{ r: 4, stroke: '#0b1220', strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
