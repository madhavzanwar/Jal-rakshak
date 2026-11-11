import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  AlertOctagon,
  ArrowRight,
  Bot,
  Brain,
  CheckCircle2,
  ChevronDown,
  Cpu,
  FileText,
  Flag,
  Gauge,
  GitBranch,
  Info,
  Loader2,
  MessageSquareWarning,
  Navigation,
  PackageOpen,
  Route as RouteIcon,
  ShieldCheck,
  SkipForward,
  Wrench,
  XCircle,
} from 'lucide-react';
import type { AgentName, AgentRun, AgentStep, Alert, GuardResult, StepKind } from '../api/schema';
import { useApi } from '../state/api-context';
import { useAsync } from '../state/useAsync';
import { useRuns } from '../state/run-context';
import { LevelChip } from '../components/LevelChip';
import { EmptyState, ErrorNote, Panel, Skeleton } from '../components/Panel';
import { fmtDistance, fmtDuration, fmtMs, fmtTime, titleCase } from '../lib/format';
import { LANG_NAMES } from '../lib/guards';

const RouteMap = lazy(() => import('../components/map/RouteMap'));

const AGENTS: { id: AgentName; label: string; icon: typeof Bot; blurb: string }[] = [
  { id: 'monitor', label: 'Monitor', icon: Gauge, blurb: 'Reads risk, rivers and rain; decides if an alert is warranted.' },
  { id: 'alert_drafter', label: 'Alert drafter', icon: MessageSquareWarning, blurb: 'Drafts SMS + WhatsApp alerts in 5 languages, checked by guards.' },
  { id: 'evacuation_planner', label: 'Evacuation planner', icon: Navigation, blurb: 'Routes top-risk wards to the nearest safe shelters.' },
  { id: 'sitrep', label: 'SitRep', icon: FileText, blurb: 'Writes the situation report for district officials.' },
];

const KIND: Record<StepKind, { icon: typeof Bot; label: string; cls: string }> = {
  thought: { icon: Brain, label: 'Thought', cls: 'text-violet-300 bg-violet-500/15' },
  tool_call: { icon: Wrench, label: 'Tool call', cls: 'text-sky-300 bg-sky-500/15' },
  tool_result: { icon: PackageOpen, label: 'Tool result', cls: 'text-cyan-300 bg-cyan-500/15' },
  decision: { icon: GitBranch, label: 'Decision', cls: 'text-amber-300 bg-amber-500/15' },
  guard: { icon: ShieldCheck, label: 'Guard', cls: 'text-emerald-300 bg-emerald-500/15' },
  final: { icon: Flag, label: 'Final', cls: 'text-slate-100 bg-white/10' },
  error: { icon: AlertOctagon, label: 'Error', cls: 'text-red-300 bg-red-500/15' },
};

function asGuardList(v: unknown): GuardResult[] | null {
  const arr = Array.isArray(v) ? v : v && typeof v === 'object' && Array.isArray((v as { guards?: unknown }).guards) ? (v as { guards: unknown[] }).guards : null;
  if (!arr || !arr.length) return null;
  if (!arr.every((g) => g && typeof g === 'object' && 'name' in g && 'passed' in g)) return null;
  return arr as GuardResult[];
}

function Json({ label, value }: { label: string; value: unknown }) {
  const [open, setOpen] = useState(false);
  if (value === null || value === undefined) return null;
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return (
    <div className="mt-2">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-slate-200">
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? '' : '-rotate-90'}`} aria-hidden />
        {label}
        <span className="text-slate-600">· {text.length > 1000 ? `${(text.length / 1000).toFixed(1)}k chars` : `${text.length} chars`}</span>
      </button>
      {open && <pre className="scroll-thin mt-1 max-h-64 overflow-auto rounded-md border border-white/[0.06] bg-ink-950 p-2.5 font-mono text-[11px] leading-relaxed text-slate-300">{text}</pre>}
    </div>
  );
}

function StepCard({ step, live }: { step: AgentStep; live: boolean }) {
  const k = KIND[step.kind];
  const Icon = k.icon;
  const guards = step.kind === 'guard' ? asGuardList(step.output) : null;
  return (
    <li className="relative pl-9" data-testid="agent-step" data-agent={step.agent} data-kind={step.kind}>
      <span className={`absolute left-0 top-0.5 grid h-7 w-7 place-items-center rounded-lg ${k.cls}`} aria-hidden>
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className={`rounded-lg border bg-ink-900/70 px-3 py-2.5 ${live ? 'border-sky-400/50 shadow-[0_0_0_3px_rgba(56,189,248,0.12)]' : 'border-white/[0.06]'}`}>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
          <span className={`rounded px-1.5 py-0.5 font-semibold ${k.cls}`}>{k.label}</span>
          {step.tool && <code className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-slate-300">{step.tool}</code>}
          <span className="ml-auto flex items-center gap-2 font-mono text-slate-500">
            <span>#{step.seq}</span>
            <span>{fmtMs(step.duration_ms)}</span>
            <span>{fmtTime(step.ts, { date: false })}</span>
          </span>
        </div>
        <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{step.content}</p>
        {guards && (
          <ul className="mt-2 grid gap-1 sm:grid-cols-2">
            {guards.map((g) => (
              <li key={g.name} className="flex items-start gap-1.5 text-xs" title={g.detail}>
                {g.passed ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" aria-label="passed" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" aria-label="failed" />}
                <span className="text-slate-300">
                  <code className="font-mono">{g.name}</code> <span className="text-slate-500">{g.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
        <Json label={step.kind === 'tool_call' ? 'Tool input' : 'Input'} value={step.input} />
        {!guards && <Json label={step.kind === 'tool_call' ? 'Tool output' : 'Output'} value={step.output} />}
      </div>
    </li>
  );
}

type LaneState = 'done' | 'active' | 'pending' | 'skipped';

function Pipeline({ states }: { states: Record<AgentName, LaneState> }) {
  return (
    <ol className="grid grid-cols-2 gap-2 md:grid-cols-4" aria-label="Agent pipeline">
      {AGENTS.map((a, i) => {
        const st = states[a.id];
        const Icon = a.icon;
        const tone =
          st === 'done' ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-200' : st === 'active' ? 'border-sky-400/60 bg-sky-500/10 text-sky-200' : 'border-white/[0.07] bg-ink-900/60 text-slate-500';
        return (
          <li key={a.id} className={`relative flex items-center gap-2.5 rounded-lg border px-3 py-2 ${tone}`}>
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-black/20">
              {st === 'active' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : st === 'done' ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : <Icon className="h-4 w-4" aria-hidden />}
            </span>
            <span className="min-w-0">
              <span className="block text-[10px] uppercase tracking-wider opacity-70">Step {i + 1}</span>
              <span className="block truncate text-sm font-semibold">{a.label}</span>
            </span>
            <span className="sr-only">{st}</span>
          </li>
        );
      })}
    </ol>
  );
}

function DraftedAlert({ alert, cityWards }: { alert: Alert; cityWards: Map<string, string> }) {
  const en = alert.versions.find((v) => v.lang === 'en') ?? alert.versions[0];
  const passed = alert.guards.filter((g) => g.passed).length;
  return (
    <Panel title="Drafted alert" icon={<MessageSquareWarning className="h-3.5 w-3.5" />} actions={<LevelChip level={alert.level} size="xs" />} className="border-sky-400/30">
      <div data-testid="drafted-alert" data-alert-id={alert.id}>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
          <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-slate-300">{alert.id}</span>
          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 font-semibold uppercase text-amber-200">{alert.status.replace('_', ' ')}</span>
          <span>
            {passed}/{alert.guards.length} guards passed
          </span>
        </div>
        {en && <p className="rounded-lg border border-white/[0.06] bg-ink-950 p-3 font-mono text-[13px] leading-relaxed text-slate-100">{en.sms}</p>}
        <div className="mt-2 flex flex-wrap gap-1">
          {alert.versions.map((v) => (
            <span key={v.lang} className="rounded border border-white/10 px-1.5 py-0.5 text-[11px] text-slate-300">
              {LANG_NAMES[v.lang]}
            </span>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-400">Target wards: {alert.target_wards.map((w) => cityWards.get(w) ?? w).join(', ') || '—'}</p>
        <Link to={`/admin?alert=${encodeURIComponent(alert.id)}`} className="btn-primary mt-3 w-full" data-testid="review-alert">
          Review &amp; approve in Admin <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>
    </Panel>
  );
}

function RunView({ run, revealed, streaming, note, onSkip }: { run: AgentRun; revealed: number; streaming: boolean; note?: string | undefined; onSkip?: () => void }) {
  const { client, version } = useApi();
  const steps = useMemo(() => [...run.steps].sort((a, b) => a.seq - b.seq), [run]);
  const shown = steps.slice(0, revealed);
  const lastShown = shown[shown.length - 1];
  const byAgent = useMemo(() => {
    const m = new Map<AgentName, AgentStep[]>();
    for (const s of shown) m.set(s.agent, [...(m.get(s.agent) ?? []), s]);
    return m;
  }, [shown]);
  const totalByAgent = useMemo(() => {
    const m = new Map<AgentName, number>();
    for (const s of steps) m.set(s.agent, (m.get(s.agent) ?? 0) + 1);
    return m;
  }, [steps]);
  const states = Object.fromEntries(
    AGENTS.map((a) => {
      const total = totalByAgent.get(a.id) ?? 0;
      const seen = byAgent.get(a.id)?.length ?? 0;
      const st: LaneState = total === 0 ? (streaming ? 'pending' : 'skipped') : seen >= total ? (streaming && lastShown?.agent === a.id ? 'active' : 'done') : seen > 0 ? 'active' : 'pending';
      return [a.id, st];
    }),
  ) as Record<AgentName, LaneState>;

  const drafterTotal = totalByAgent.get('alert_drafter') ?? 0;
  const drafterDone = (byAgent.get('alert_drafter')?.length ?? 0) >= drafterTotal && drafterTotal > 0;
  const showAlert = !!run.alert_id && (drafterDone || !streaming);
  const alerts = useAsync(() => (showAlert ? client.alerts() : Promise.resolve([] as Alert[])), [client, showAlert, version]);
  const alert = alerts.data?.find((a) => a.id === run.alert_id);
  const cities = useAsync(() => client.cities(), [client]);
  const city = cities.data?.find((c) => c.city.id === run.city_id)?.city;
  const wardNames = new Map(city?.wards.map((w) => [w.id, w.name]) ?? []);
  const evacDone = !streaming || states.evacuation_planner === 'done' || states.sitrep !== 'pending';
  const totalMs = steps.reduce((s, x) => s + x.duration_ms, 0);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_460px]">
      <div className="min-w-0 space-y-4">
        <Panel bodyClassName="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="kicker">Agent run · {run.trigger}</div>
              <h1 className="text-xl font-semibold text-white">
                Response pipeline — {city?.name ?? titleCase(run.city_id)}
              </h1>
              <p className="mt-0.5 font-mono text-[11px] text-slate-500">
                {run.id} · started {fmtTime(run.started_at)} IST · {steps.length} steps · {fmtMs(totalMs)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-violet-400/30 bg-violet-500/10 px-2 py-1 text-xs text-violet-200" data-testid="llm-badge">
                <Cpu className="h-3.5 w-3.5" aria-hidden /> {run.llm.provider} · {run.llm.model}
              </span>
              {streaming ? (
                <span className="inline-flex items-center gap-1.5 rounded-md bg-sky-500/15 px-2 py-1 text-xs text-sky-200" role="status">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Streaming {revealed}/{steps.length}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500/15 px-2 py-1 text-xs text-emerald-200" data-testid="run-complete">
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> Completed
                </span>
              )}
              {streaming && onSkip && (
                <button type="button" onClick={onSkip} className="btn-ghost px-2 py-1 text-xs">
                  <SkipForward className="h-3.5 w-3.5" aria-hidden /> Show all
                </button>
              )}
            </div>
          </div>
          {note && (
            <p className="mt-3 flex items-center gap-2 rounded-md border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-100" data-testid="run-note">
              <Info className="h-4 w-4 shrink-0" aria-hidden /> {note}
            </p>
          )}
          <div className="mt-4">
            <Pipeline states={states} />
          </div>
        </Panel>

        {AGENTS.map((a) => {
          const list = byAgent.get(a.id) ?? [];
          const total = totalByAgent.get(a.id) ?? 0;
          const Icon = a.icon;
          const dur = list.reduce((s, x) => s + x.duration_ms, 0);
          return (
            <section key={a.id} aria-label={`${a.label} steps`} data-testid={`lane-${a.id}`} className={`rounded-xl border border-white/[0.07] bg-ink-850/80 ${list.length ? '' : 'opacity-60'}`}>
              <header className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-2.5">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-sky-500/10 text-sky-300">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-sm font-semibold text-slate-100">{a.label}</h2>
                  <p className="truncate text-[11px] text-slate-400">{a.blurb}</p>
                </div>
                <span className="font-mono text-[11px] text-slate-400">
                  {list.length}/{total} · {fmtMs(dur)}
                </span>
              </header>
              {list.length ? (
                <ol className="space-y-2 p-3">
                  {list.map((s) => (
                    <StepCard key={s.id} step={s} live={streaming && s.id === lastShown?.id} />
                  ))}
                </ol>
              ) : (
                <p className="px-4 py-3 text-xs text-slate-500">{total ? 'Waiting…' : 'No steps for this agent in this run.'}</p>
              )}
            </section>
          );
        })}
      </div>

      <div className="space-y-4">
        <Panel title="Monitor decision" icon={<GitBranch className="h-3.5 w-3.5" />} actions={<LevelChip level={run.decision.level} size="xs" />}>
          <p className="text-sm font-semibold text-white">{run.decision.should_alert ? 'Alert warranted' : 'No alert needed'}</p>
          <p className="mt-1 text-sm leading-relaxed text-slate-300">{run.decision.reason}</p>
        </Panel>

        {showAlert && alert && <DraftedAlert alert={alert} cityWards={wardNames} />}
        {showAlert && !alert && alerts.loading && <Skeleton className="h-48" />}
        {!showAlert && run.alert_id && streaming && (
          <Panel title="Drafted alert" icon={<MessageSquareWarning className="h-3.5 w-3.5" />}>
            <p className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Alert drafter is working…
            </p>
          </Panel>
        )}

        <Panel title="Evacuation routes" icon={<RouteIcon className="h-3.5 w-3.5" />}>
          {run.evacuation.length && evacDone ? (
            <>
              <Suspense fallback={<Skeleton className="h-72" />}>
                <RouteMap plans={run.evacuation} />
              </Suspense>
              <ul className="mt-3 space-y-2">
                {run.evacuation.map((p, i) => (
                  <li key={i} className="rounded-lg border border-white/[0.06] bg-ink-900/70 p-2.5 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-100">→ {p.facility.name}</span>
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${p.route.method === 'osrm' ? 'bg-sky-500/15 text-sky-200' : 'bg-amber-500/15 text-amber-200'}`}>
                        {p.route.method === 'osrm' ? 'OSRM road route' : 'straight line'}
                      </span>
                    </div>
                    <div className="mt-0.5 text-slate-400">
                      {fmtDistance(p.route.distance_m)} · {fmtDuration(p.route.duration_s)} · {p.facility.capacity - p.facility.occupancy} places free
                      {p.alternatives.length > 0 && ` · ${p.alternatives.length} alternative${p.alternatives.length > 1 ? 's' : ''}`}
                    </div>
                    {p.notes.length > 0 && <ul className="mt-1 list-disc pl-4 text-slate-400">{p.notes.map((n, j) => <li key={j}>{n}</li>)}</ul>}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-slate-400">{streaming ? 'Waiting for the evacuation planner…' : 'No evacuation plans in this run.'}</p>
          )}
        </Panel>

        {run.sitrep && !streaming && (
          <Panel title="Situation report" icon={<FileText className="h-3.5 w-3.5" />}>
            <h3 className="text-sm font-semibold text-white">{run.sitrep.title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-slate-300">{run.sitrep.summary}</p>
            <dl className="mt-3 grid grid-cols-2 gap-2">
              {run.sitrep.key_figures.slice(0, 6).map((k) => (
                <div key={k.label} className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                  <dt className="text-[10px] uppercase tracking-wider text-slate-400">{k.label}</dt>
                  <dd className="text-sm font-semibold text-slate-100">{k.value}</dd>
                </div>
              ))}
            </dl>
            <Link to={`/admin?run=${encodeURIComponent(run.id)}#sitrep`} className="btn-ghost mt-3 w-full text-xs">
              Open full SitRep &amp; export PDF
            </Link>
          </Panel>
        )}
      </div>
    </div>
  );
}

export default function Agents() {
  const { client, version } = useApi();
  const runsCtx = useRuns();
  const [params, setParams] = useSearchParams();
  const wanted = params.get('run');
  const runs = useAsync(() => client.runs(), [client, version]);
  const active = runsCtx.active;
  const useActive = active && (!wanted || wanted === active.run.id);
  const selectedId = useActive ? active.run.id : wanted ?? runs.data?.[0]?.id ?? null;
  const fetched = useAsync(() => (selectedId && !useActive ? client.run(selectedId) : Promise.resolve(undefined)), [client, selectedId, useActive]);

  // Keep the URL in sync with what is displayed so it can be shared.
  useEffect(() => {
    if (selectedId && selectedId !== wanted) setParams({ run: selectedId }, { replace: true });
  }, [selectedId, wanted, setParams]);

  const run = useActive ? active.run : fetched.data;

  return (
    <div className="scroll-thin flex-1 p-3 sm:p-5 lg:h-full lg:overflow-y-auto">
      <div className="mx-auto max-w-[1720px]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-sky-300" aria-hidden />
            <h1 className="text-lg font-semibold">Agent timeline</h1>
          </div>
          {!!runs.data?.length && (
            <label className="flex items-center gap-2 text-xs text-slate-400">
              Run
              <select
                value={selectedId ?? ''}
                onChange={(e) => setParams({ run: e.target.value })}
                className="max-w-[340px] rounded-md border border-white/10 bg-ink-850 px-2 py-1.5 text-sm text-slate-100"
                aria-label="Select agent run"
              >
                {active && !runs.data.some((r) => r.id === active.run.id) && <option value={active.run.id}>{active.run.city_id} · {fmtTime(active.run.started_at)} (current)</option>}
                {runs.data.map((r) => (
                  <option key={r.id} value={r.id}>
                    {titleCase(r.city_id)} · {fmtTime(r.started_at)} · {r.decision.level.toUpperCase()} · {r.trigger}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {runsCtx.error && <div className="mb-3"><ErrorNote error={runsCtx.error} onRetry={runsCtx.clearError} /></div>}
        {run ? (
          <RunView
            key={run.id}
            run={run}
            revealed={useActive ? active.revealed : run.steps.length}
            streaming={useActive ? active.streaming : false}
            note={useActive ? active.note : undefined}
            onSkip={runsCtx.skip}
          />
        ) : fetched.error ? (
          <ErrorNote error={fetched.error} onRetry={fetched.reload} />
        ) : runs.loading || fetched.loading ? (
          <Skeleton className="h-96" />
        ) : (
          <Panel>
            <EmptyState icon={<Bot className="h-8 w-8" />} title="No agent runs yet">
              Pick a city on the <Link to="/" className="text-sky-300 underline">dashboard</Link> and press <strong>Run response agents</strong>.
            </EmptyState>
          </Panel>
        )}
      </div>
    </div>
  );
}
