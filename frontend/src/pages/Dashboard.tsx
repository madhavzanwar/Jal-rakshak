import { lazy, Suspense, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronRight,
  CloudRain,
  Database,
  Droplets,
  Loader2,
  MapPin,
  Search,
  ShieldAlert,
  Users,
  Waves,
  X,
  XCircle,
} from 'lucide-react';
import type { CityRisk, CitySummary, Facility, GaugeReading, RiskLevel, RiskScore, Ward } from '../api/schema';
import { useApi } from '../state/api-context';
import { useAsync } from '../state/useAsync';
import { useRuns } from '../state/run-context';
import { LevelChip, LevelDot } from '../components/LevelChip';
import { RiskGauge } from '../components/RiskGauge';
import { StaleBadge } from '../components/StaleBadge';
import { EmptyState, ErrorNote, Panel, Skeleton } from '../components/Panel';
import { GAUGE_STATUS_LEVEL, LEVEL_COLORS, LEVEL_ORDER } from '../lib/levels';
import { fmtCompact, fmtInt, fmtTime } from '../lib/format';
import { haversineKm, osmDirectionsUrl } from '../lib/geo';
import { FACILITY_STYLE } from '../components/map/icons';

const CommandMap = lazy(() => import('../components/map/CommandMap'));
const HorizonChart = lazy(() => import('../components/charts/HorizonChart'));
const RainfallChart = lazy(() => import('../components/charts/RainfallChart'));
const DischargeChart = lazy(() => import('../components/charts/DischargeChart'));

function sortByRisk(list: CitySummary[]): CitySummary[] {
  return [...list].sort((a, b) => b.risk.score - a.risk.score);
}

// ---------------------------------------------------------------- left rail
function CityRail({ cities, selectedId, onSelect }: { cities: CitySummary[]; selectedId: string | null; onSelect: (id: string | null) => void }) {
  const [q, setQ] = useState('');
  const counts = useMemo(() => {
    const c: Record<RiskLevel, number> = { green: 0, yellow: 0, orange: 0, red: 0 };
    for (const s of cities) c[s.risk.level] += 1;
    return c;
  }, [cities]);
  const shown = sortByRisk(cities).filter((c) => `${c.city.name} ${c.city.state}`.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <aside aria-label="Cities by risk" className="flex min-h-0 flex-col border-white/[0.06] bg-ink-950/60 lg:border-r">
      <div className="border-b border-white/[0.06] p-3">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="kicker">Cities · {cities.length}</h2>
          <button type="button" onClick={() => onSelect(null)} className="text-[11px] text-sky-300 hover:underline">
            All India
          </button>
        </div>
        <div className="mb-3 grid grid-cols-4 gap-1.5" aria-label="Cities per level">
          {(['red', 'orange', 'yellow', 'green'] as const).map((l) => (
            <div key={l} className="rounded-md border border-white/[0.06] bg-ink-850 px-2 py-1.5 text-center">
              <div className="font-mono text-lg font-bold leading-none" style={{ color: LEVEL_COLORS[l] }}>
                {counts[l]}
              </div>
              <div className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-400">{l}</div>
            </div>
          ))}
        </div>
        <label className="relative block">
          <span className="sr-only">Filter cities</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter cities…" className="input py-1.5 pl-8" />
        </label>
      </div>
      <ol className="scroll-thin min-h-0 flex-1 overflow-y-auto p-2" data-testid="city-rail">
        {shown.map((c, i) => {
          const sel = c.city.id === selectedId;
          return (
            <li key={c.city.id}>
              <button
                type="button"
                onClick={() => onSelect(c.city.id)}
                aria-current={sel ? 'true' : undefined}
                className={`group mb-1 flex w-full items-center gap-3 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                  sel ? 'border-sky-400/50 bg-sky-500/10' : 'border-transparent hover:border-white/10 hover:bg-white/[0.03]'
                }`}
              >
                <span className="w-4 text-right font-mono text-[11px] text-slate-500">{i + 1}</span>
                <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded-full font-mono text-[12px] font-bold" style={{ background: `${LEVEL_COLORS[c.risk.level]}26`, color: LEVEL_COLORS[c.risk.level], boxShadow: `inset 0 0 0 2px ${LEVEL_COLORS[c.risk.level]}` }}>
                  {Math.round(c.risk.score)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-sm font-semibold text-slate-100">{c.city.name}</span>
                    {c.stale && <span title="Stale data" className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-label="stale data" />}
                  </span>
                  <span className="block truncate text-[11px] text-slate-400">
                    {c.city.state}
                    {c.peak_time && ` · peak ${fmtTime(c.peak_time)}`}
                  </span>
                </span>
                <LevelChip level={c.risk.level} size="xs" label={c.risk.level} />
              </button>
            </li>
          );
        })}
        {!shown.length && <li className="p-4 text-center text-sm text-slate-500">No city matches “{q}”.</li>}
      </ol>
    </aside>
  );
}

// ---------------------------------------------------------------- factor bars
const COMPONENT_LABELS: { key: keyof RiskScore['factors']['components']; label: string; icon: typeof CloudRain }[] = [
  { key: 'rain', label: 'Rainfall', icon: CloudRain },
  { key: 'river', label: 'River discharge', icon: Waves },
  { key: 'antecedent', label: 'Soil saturation (7-day rain)', icon: Droplets },
  { key: 'vulnerability', label: 'Ward vulnerability', icon: Users },
];

export function FactorBars({ risk }: { risk: RiskScore }) {
  return (
    <ul className="space-y-2.5">
      {COMPONENT_LABELS.map(({ key, label, icon: Icon }) => {
        const v = Math.max(0, Math.min(1, risk.factors.components[key]));
        const lvl: RiskLevel = v >= 0.75 ? 'red' : v >= 0.55 ? 'orange' : v >= 0.3 ? 'yellow' : 'green';
        return (
          <li key={key}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-slate-300">
                <Icon className="h-3.5 w-3.5 text-slate-500" aria-hidden />
                {label}
              </span>
              <span className="font-mono tabular-nums text-slate-200">{(v * 100).toFixed(0)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)} aria-label={label}>
              <div className="h-full rounded-full" style={{ width: `${v * 100}%`, background: LEVEL_COLORS[lvl] }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Stat({ label, value, unit, hint, sub }: { label: string; value: string; unit?: string; hint?: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-white/[0.06] bg-ink-900/70 px-2.5 py-2" title={hint}>
      <div className="truncate text-[10px] uppercase tracking-wider text-slate-400">{label}</div>
      <div className="mt-0.5 truncate font-mono text-base font-semibold tabular-nums text-slate-100">
        {value}
        {unit && <span className="ml-0.5 text-[11px] font-normal text-slate-400">{unit}</span>}
        {sub && <span className="ml-1 text-[10px] font-normal text-slate-400">{sub}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- ward drawer
function nearestShelters(ward: Ward, facilities: Facility[] | undefined) {
  return (facilities ?? [])
    .map((f) => ({ f, km: haversineKm(ward.lat, ward.lon, f.lat, f.lon) }))
    .sort((a, b) => a.km - b.km)
    .slice(0, 3);
}

function WardPanel({ ward, risk, facilities, onClose }: { ward: Ward; risk: RiskScore | undefined; facilities: Facility[] | undefined; onClose: () => void }) {
  return (
    <div data-testid="ward-panel" role="dialog" aria-label={`Ward ${ward.name}`} className="scroll-thin absolute inset-x-2 bottom-2 z-[600] max-h-[70%] overflow-y-auto rounded-xl border border-white/10 bg-ink-950/95 shadow-2xl backdrop-blur sm:inset-x-auto sm:right-3 sm:top-3 sm:bottom-auto sm:max-h-[calc(100%-24px)] sm:w-[340px]">
      <div className="flex items-start justify-between gap-2 border-b border-white/[0.07] p-4">
        <div>
          <div className="kicker">Ward drill-down</div>
          <h3 className="text-lg font-semibold text-white">{ward.name}</h3>
          <div className="text-[11px] text-slate-400">
            {ward.id} · pop. {fmtCompact(ward.population)} · {ward.elevation_m} m elev.
          </div>
        </div>
        <button type="button" onClick={onClose} className="btn-icon text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close ward panel">
          <X className="h-4 w-4" />
        </button>
      </div>
      {risk ? (
        <div className="space-y-4 p-4">
          <div className="flex items-center gap-3">
            <div className="font-mono text-4xl font-bold tabular-nums" style={{ color: LEVEL_COLORS[risk.level] }} data-testid="ward-score">
              {risk.score.toFixed(1)}
            </div>
            <div className="space-y-1">
              <LevelChip level={risk.level} />
              {risk.ml_probability != null && <div className="text-[11px] text-slate-400">ML P(flood-day): {(risk.ml_probability * 100).toFixed(0)}%</div>}
            </div>
          </div>
          <p className="text-sm leading-relaxed text-slate-300">{risk.explanation}</p>
          <FactorBars risk={risk} />
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Rain 24 h" value={risk.factors.rain_24h_mm.toFixed(0)} unit="mm" />
            <Stat label="Rain 72 h" value={risk.factors.rain_72h_mm.toFixed(0)} unit="mm" />
            <Stat label="Peak intensity" value={risk.factors.max_intensity_mmph.toFixed(1)} unit="mm/h" />
            <Stat label="River / danger" value={`${(risk.factors.discharge_ratio * 100).toFixed(0)}`} unit="%" />
          </div>
        </div>
      ) : (
        <p className="p-4 text-sm text-slate-400">No ward score in this update.</p>
      )}
      <div className="border-t border-white/[0.07] p-4">
        <h4 className="kicker mb-2">Nearest shelters & facilities</h4>
        <ul className="space-y-2">
          {nearestShelters(ward, facilities).map(({ f, km }) => {
            const s = FACILITY_STYLE[f.type];
            const occ = f.capacity ? f.occupancy / f.capacity : 0;
            return (
              <li key={f.id} className="rounded-lg border border-white/[0.06] bg-ink-900 p-2.5">
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 h-3 w-3 shrink-0 rounded-[3px]" style={{ background: s.color }} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-slate-100">{f.name}</div>
                    <div className="text-[11px] text-slate-400">
                      {s.label} · {km.toFixed(1)} km · {f.elevation_m} m · {fmtInt(f.capacity - f.occupancy)} places free
                    </div>
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/10">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, occ * 100)}%`, background: occ > 0.85 ? LEVEL_COLORS.red : occ > 0.6 ? LEVEL_COLORS.orange : '#38bdf8' }} />
                    </div>
                  </div>
                  <a href={osmDirectionsUrl(ward, f)} target="_blank" rel="noreferrer" className="shrink-0 text-[11px] text-sky-300 hover:underline">
                    Route
                  </a>
                </div>
              </li>
            );
          })}
          {!facilities?.length && <li className="text-sm text-slate-500">No facilities loaded.</li>}
        </ul>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- right panel
function GaugeCard({ reading, today }: { reading: GaugeReading; today: string }) {
  const lvl = GAUGE_STATUS_LEVEL[reading.status];
  return (
    <div className="rounded-lg border border-white/[0.06] bg-ink-900/70 p-3" data-testid="gauge-card">
      <div className="mb-1 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-100">
            <Waves className="h-4 w-4 text-sky-400" aria-hidden />
            {reading.gauge.river}
          </div>
          <div className="text-[11px] text-slate-400">
            now {fmtInt(reading.current_m3s)} m³/s · peak {fmtInt(reading.peak_m3s)} on {reading.peak_date}
          </div>
        </div>
        <LevelChip level={lvl} size="xs" label={reading.status} />
      </div>
      <Suspense fallback={<Skeleton className="h-[130px]" />}>
        <DischargeChart reading={reading} today={today} />
      </Suspense>
    </div>
  );
}

function CityPanel({ detail, onRun, running, onWard, selectedWardId }: { detail: CityRisk; onRun: () => void; running: boolean; onWard: (id: string) => void; selectedWardId: string | null }) {
  const { city, overall } = detail;
  const today = detail.generated_at.slice(0, 10);
  const topWards = [...detail.wards].sort((a, b) => b.risk.score - a.risk.score).slice(0, 6);
  const wardName = new Map(city.wards.map((w) => [w.id, w.name]));
  const peak = detail.horizon.reduce((m, p) => (p.score > m.score ? p : m), detail.horizon[0] ?? { t: '', score: 0, level: 'green' as const });
  return (
    <div className="space-y-3" data-testid="city-panel">
      <Panel bodyClassName="p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="kicker flex items-center gap-1">
              <MapPin className="h-3 w-3" aria-hidden /> {city.state}
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-white" data-testid="city-name">
              {city.name}
            </h2>
            <div className="text-[11px] text-slate-400">
              Pop. {fmtCompact(city.population)} · {city.wards.length} wards · updated {fmtTime(detail.generated_at)} IST
            </div>
          </div>
          {detail.stale && <StaleBadge ageMinutes={detail.data_age_minutes} />}
        </div>
        <div className="mt-2 flex justify-center">
          <RiskGauge score={overall.score} level={overall.level} size={230} caption="Overall = highest ward score" />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Stat label="Rain 24 h" value={overall.factors.rain_24h_mm.toFixed(0)} unit="mm" hint="Max rolling 24 h sum in the 72 h window" />
          <Stat label="Rain 72 h" value={overall.factors.rain_72h_mm.toFixed(0)} unit="mm" />
          <Stat label="River/danger" value={(overall.factors.discharge_ratio * 100).toFixed(0)} unit="%" hint="Forecast peak discharge ÷ danger threshold" />
          <Stat label="7-day rain" value={overall.factors.antecedent_7d_mm.toFixed(0)} unit="mm" hint="Observed rain over the past 7 days (soil saturation)" />
          <Stat label="Peak risk" value={peak.score.toFixed(0)} hint={`Highest horizon score at ${fmtTime(peak.t)} IST`} sub={fmtTime(peak.t)} />
          {overall.ml_probability != null ? (
            <Stat label="ML flood prob." value={(overall.ml_probability * 100).toFixed(0)} unit="%" hint="LightGBM P(flood-day), trained on historical rain/discharge" />
          ) : (
            <Stat label="Max intensity" value={overall.factors.max_intensity_mmph.toFixed(1)} unit="mm/h" />
          )}
        </div>
        <p className="mt-3 rounded-lg border-l-4 bg-white/[0.03] px-3 py-2 text-sm leading-relaxed text-slate-200" style={{ borderColor: LEVEL_COLORS[overall.level] }} data-testid="risk-explanation">
          {overall.explanation}
        </p>
        <button type="button" onClick={onRun} disabled={running} className="btn-primary mt-3 w-full py-2.5 text-[15px]" data-testid="run-agents">
          {running ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Bot className="h-4 w-4" aria-hidden />}
          {running ? 'Starting response agents…' : 'Run response agents'}
        </button>
        <p className="mt-1.5 text-center text-[11px] text-slate-500">Agents only draft. Nothing is sent without a named human approver.</p>
      </Panel>

      <Panel title="72-hour risk horizon" icon={<Activity className="h-3.5 w-3.5" />}>
        <Suspense fallback={<Skeleton className="h-[170px]" />}>
          <HorizonChart points={detail.horizon} />
        </Suspense>
      </Panel>

      <Panel title="Hourly rainfall · next 72 h" icon={<CloudRain className="h-3.5 w-3.5" />} actions={<span className="font-mono text-[11px] text-slate-400">{detail.rainfall.reduce((s, p) => s + p.mm, 0).toFixed(0)} mm total</span>}>
        <Suspense fallback={<Skeleton className="h-[150px]" />}>
          <RainfallChart points={detail.rainfall} />
        </Suspense>
      </Panel>

      <Panel title="River gauges (GloFAS)" icon={<Waves className="h-3.5 w-3.5" />} bodyClassName="space-y-2 p-3">
        {detail.gauges.length ? detail.gauges.map((g) => <GaugeCard key={g.gauge.id} reading={g} today={today} />) : <p className="text-sm text-slate-400">No river gauge mapped for this city (pluvial risk only).</p>}
      </Panel>

      <Panel title="Wards at highest risk" icon={<ShieldAlert className="h-3.5 w-3.5" />} bodyClassName="p-2">
        <ul>
          {topWards.map((w) => (
            <li key={w.ward_id}>
              <button
                type="button"
                onClick={() => onWard(w.ward_id)}
                data-testid="ward-row"
                className={`flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-white/[0.04] ${selectedWardId === w.ward_id ? 'bg-white/[0.06]' : ''}`}
              >
                <LevelDot level={w.risk.level} />
                <span className="flex-1 truncate text-slate-200">{wardName.get(w.ward_id) ?? w.ward_id}</span>
                <span className="font-mono text-xs tabular-nums text-slate-300">{w.risk.score.toFixed(1)}</span>
                <ChevronRight className="h-3.5 w-3.5 text-slate-500" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Data sources" icon={<Database className="h-3.5 w-3.5" />} bodyClassName="p-3">
        <ul className="space-y-1.5" data-testid="sources">
          {detail.sources.map((s) => (
            <li key={s.name} className="flex items-center gap-2 text-xs">
              {s.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" aria-label="ok" /> : <XCircle className="h-3.5 w-3.5 shrink-0 text-amber-400" aria-label="stale" />}
              <a href={s.url} target="_blank" rel="noreferrer" className="flex-1 truncate text-slate-300 hover:text-sky-300 hover:underline">
                {s.name}
              </a>
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${s.ok ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>{s.ok ? 'ok' : 'stale'}</span>
              <span className="w-[88px] text-right font-mono text-[10px] text-slate-500">{fmtTime(s.fetched_at)}</span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function NationalPanel({ cities, onSelect }: { cities: CitySummary[]; onSelect: (id: string) => void }) {
  const top = sortByRisk(cities).slice(0, 5);
  const atRisk = cities.filter((c) => LEVEL_ORDER[c.risk.level] >= 2);
  const people = atRisk.reduce((s, c) => s + c.city.population, 0);
  const stale = cities.filter((c) => c.stale).length;
  const latest = cities.reduce((m, c) => (c.updated_at > m ? c.updated_at : m), '');
  return (
    <div className="space-y-3" data-testid="national-panel">
      <Panel bodyClassName="p-4">
        <div className="kicker">National overview</div>
        <h2 className="text-2xl font-semibold tracking-tight text-white">India · {cities.length} monitored cities</h2>
        <p className="mt-1 text-[11px] text-slate-400">Updated {fmtTime(latest)} IST · 72-hour look-ahead</p>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Stat label="Cities orange / red" value={String(atRisk.length)} />
          <Stat label="Population in those cities" value={fmtCompact(people)} />
        </div>
        {stale > 0 && <StaleBadge className="mt-3" />}
      </Panel>
      <Panel title="Highest risk now" icon={<AlertTriangle className="h-3.5 w-3.5" />} bodyClassName="p-2">
        <ul>
          {top.map((c) => (
            <li key={c.city.id}>
              <button type="button" onClick={() => onSelect(c.city.id)} className="flex w-full items-start gap-3 rounded-md px-2 py-2 text-left hover:bg-white/[0.04]">
                <span className="mt-0.5 font-mono text-lg font-bold tabular-nums" style={{ color: LEVEL_COLORS[c.risk.level] }}>
                  {c.risk.score.toFixed(0)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                    {c.city.name} <LevelChip level={c.risk.level} size="xs" label={c.risk.level} />
                  </span>
                  <span className="line-clamp-2 text-xs text-slate-400">{c.risk.explanation}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="How to use" bodyClassName="p-4 text-sm leading-relaxed text-slate-300">
        <ol className="list-decimal space-y-1 pl-4">
          <li>Pick a city on the map, in the list, or with “Jump to city”.</li>
          <li>Click a ward zone to see why it scores high and where the nearest shelters are.</li>
          <li>Run the response agents to draft multilingual alerts, evacuation routes and a SitRep.</li>
          <li>Approve or reject the draft in Admin — only a named human can send.</li>
        </ol>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- page
export default function Dashboard() {
  const { client, version } = useApi();
  const runs = useRuns();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get('city');
  const selectedWardId = params.get('ward');

  const cities = useAsync(() => client.cities(), [client, version], { pollMs: client.mode === 'live' ? 5 * 60_000 : undefined });
  const detail = useAsync(() => (selectedId ? client.cityRisk(selectedId) : Promise.resolve(undefined)), [client, selectedId, version]);
  const facilities = useAsync(() => (selectedId ? client.facilities(selectedId) : Promise.resolve(undefined)), [client, selectedId]);

  const select = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set('city', id);
    else next.delete('city');
    next.delete('ward');
    setParams(next, { replace: false });
  };
  const selectWard = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set('ward', id);
    else next.delete('ward');
    setParams(next, { replace: true });
  };

  const list = cities.data ?? [];
  const cityDetail = detail.data && detail.data.city.id === selectedId ? detail.data : undefined;
  const ward = cityDetail?.city.wards.find((w) => w.id === selectedWardId);
  const wardRisk = cityDetail?.wards.find((w) => w.ward_id === selectedWardId)?.risk;
  const anyStale = list.some((c) => c.stale);

  const run = async () => {
    if (!selectedId) return;
    const r = await runs.start(selectedId);
    if (r) navigate(`/agents?run=${encodeURIComponent(r.id)}`);
  };

  return (
    <div className="grid flex-1 grid-cols-1 lg:h-full lg:min-h-0 lg:grid-cols-[288px_minmax(0,1fr)_440px] 2xl:grid-cols-[300px_minmax(0,1fr)_480px]">
      <div className="order-2 max-h-[420px] min-h-0 lg:order-1 lg:max-h-none">
        {cities.error && !cities.data ? <div className="p-3"><ErrorNote error={cities.error} onRetry={cities.reload} /></div> : <CityRail cities={list} selectedId={selectedId} onSelect={select} />}
      </div>

      <section aria-label="Map" className="relative order-1 h-[56vh] min-h-[340px] lg:order-2 lg:h-auto">
        <div className="absolute left-3 right-3 top-3 z-[700] flex flex-wrap items-center gap-2 sm:right-auto">
          <label className="flex items-center gap-2 rounded-lg border border-white/10 bg-ink-950/90 px-2 py-1 shadow-panel backdrop-blur">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Jump to city</span>
            <select
              data-testid="city-select"
              aria-label="Select city"
              value={selectedId ?? ''}
              onChange={(e) => select(e.target.value || null)}
              className="max-w-[180px] rounded-md border border-white/10 bg-ink-850 py-1 pl-2 pr-6 text-sm text-slate-100"
            >
              <option value="">All India</option>
              {[...list].sort((a, b) => a.city.name.localeCompare(b.city.name)).map((c) => (
                <option key={c.city.id} value={c.city.id}>
                  {c.city.name}
                </option>
              ))}
            </select>
          </label>
          {anyStale && !selectedId && <StaleBadge className="bg-ink-950/90" />}
          {detail.loading && selectedId && !cityDetail && (
            <span className="flex items-center gap-1.5 rounded-lg bg-ink-950/90 px-2 py-1 text-xs text-slate-300">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Loading wards…
            </span>
          )}
        </div>
        <Suspense fallback={<Skeleton className="h-full rounded-none" />}>
          <CommandMap
            cities={list}
            selectedId={selectedId}
            detail={cityDetail}
            facilities={facilities.data}
            selectedWardId={selectedWardId}
            onSelectCity={select}
            onSelectWard={selectWard}
          />
        </Suspense>
        {ward && <WardPanel ward={ward} risk={wardRisk} facilities={facilities.data} onClose={() => selectWard(null)} />}
      </section>

      <div className="scroll-thin order-3 min-h-0 border-white/[0.06] bg-ink-950/40 p-3 lg:overflow-y-auto lg:border-l">
        {runs.error && (
          <div className="mb-3">
            <ErrorNote error={runs.error} onRetry={runs.clearError} />
          </div>
        )}
        {!selectedId ? (
          cities.data ? <NationalPanel cities={list} onSelect={select} /> : <Skeleton className="h-96" />
        ) : detail.error && !cityDetail ? (
          <ErrorNote error={detail.error} onRetry={detail.reload} />
        ) : cityDetail ? (
          <CityPanel detail={cityDetail} onRun={run} running={runs.starting === selectedId} onWard={(id) => selectWard(id)} selectedWardId={selectedWardId} />
        ) : (
          <div className="space-y-3">
            <Skeleton className="h-72" />
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
          </div>
        )}
        {!list.length && cities.data && <EmptyState title="No cities returned" />}
      </div>
    </div>
  );
}
