import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  CheckCircle2,
  Download,
  FileText,
  Inbox,
  Loader2,
  MessageCircle,
  MessageSquare,
  Save,
  Send,
  ShieldAlert,
  ShieldCheck,
  Undo2,
  UserCheck,
  XCircle,
} from 'lucide-react';
import type { AgentRun, Alert, AlertStatus, AlertVersion, City, GuardResult, Lang } from '../api/schema';
import { useApi } from '../state/api-context';
import { useAsync } from '../state/useAsync';
import { LevelChip } from '../components/LevelChip';
import { EmptyState, ErrorNote, Panel, Skeleton } from '../components/Panel';
import { ALL_LANGS, LANG_NAMES, runGuards } from '../lib/guards';
import { SmsCounter } from '../components/SmsCounter';
import { fmtCompact, fmtInt, fmtTime, titleCase } from '../lib/format';

const STATUS_STYLE: Record<AlertStatus, { label: string; cls: string }> = {
  pending_approval: { label: 'Pending approval', cls: 'bg-amber-500/15 text-amber-200 border-amber-400/30' },
  approved: { label: 'Approved', cls: 'bg-sky-500/15 text-sky-200 border-sky-400/30' },
  rejected: { label: 'Rejected', cls: 'bg-red-500/15 text-red-200 border-red-400/30' },
  sent: { label: 'Sent', cls: 'bg-emerald-500/15 text-emerald-200 border-emerald-400/30' },
};

function StatusChip({ status, testId }: { status: AlertStatus; testId?: string }) {
  const s = STATUS_STYLE[status];
  return (
    <span data-testid={testId} data-status={status} className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${s.cls}`}>
      {status === 'sent' ? 'sent' : s.label}
    </span>
  );
}

const FILTERS: { id: 'all' | AlertStatus; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'pending_approval', label: 'Pending' },
  { id: 'sent', label: 'Sent' },
  { id: 'rejected', label: 'Rejected' },
];

function GuardList({ guards, title }: { guards: GuardResult[]; title: string }) {
  const failed = guards.filter((g) => !g.passed).length;
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="kicker flex items-center gap-1.5">
          {failed ? <ShieldAlert className="h-3.5 w-3.5 text-red-400" aria-hidden /> : <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" aria-hidden />}
          {title}
        </h3>
        <span className={`text-[11px] font-semibold ${failed ? 'text-red-300' : 'text-emerald-300'}`}>{failed ? `${failed} failed` : 'all passed'}</span>
      </div>
      <ul className="space-y-1" data-testid="guard-list">
        {guards.map((g) => (
          <li key={g.name} className="flex items-start gap-2 rounded-md bg-white/[0.02] px-2 py-1.5 text-xs">
            {g.passed ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" aria-label="passed" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" aria-label="failed" />}
            <span className="min-w-0">
              <code className="font-mono text-slate-200">{g.name}</code>
              <span className="block break-words text-slate-400">{g.detail}</span>
            </span>
          </li>
        ))}
        {!guards.length && <li className="text-xs text-slate-500">No guard results.</li>}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- editor
type Drafts = Record<Lang, { sms: string; whatsapp: string }>;
const toDrafts = (versions: AlertVersion[]): Drafts =>
  Object.fromEntries(ALL_LANGS.map((l) => [l, { sms: versions.find((v) => v.lang === l)?.sms ?? '', whatsapp: versions.find((v) => v.lang === l)?.whatsapp ?? '' }])) as Drafts;
const toVersions = (d: Drafts, langs: Lang[]): AlertVersion[] => langs.map((lang) => ({ lang, sms: d[lang].sms, whatsapp: d[lang].whatsapp }));

const REVIEWER_KEY = 'jalrakshak.reviewer';
function loadReviewerHint(): string {
  try {
    return sessionStorage.getItem(REVIEWER_KEY) ?? '';
  } catch {
    return '';
  }
}

function AlertEditor({ alert, city, onChanged }: { alert: Alert; city: City | undefined; onChanged: (a: Alert) => void }) {
  const { client } = useApi();
  const langs = useMemo(() => ALL_LANGS.filter((l) => alert.versions.some((v) => v.lang === l)), [alert]);
  const [lang, setLang] = useState<Lang>(langs[0] ?? 'en');
  const [drafts, setDrafts] = useState<Drafts>(() => toDrafts(alert.versions));
  const [reviewer, setReviewer] = useState<string>(loadReviewerHint);
  const [reviewerError, setReviewerError] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | 'save' | 'approve' | 'reject'>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  const reviewerRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDrafts(toDrafts(alert.versions));
    setError(null);
  }, [alert]);

  const pending = alert.status === 'pending_approval';
  const original = useMemo(() => toDrafts(alert.versions), [alert]);
  const dirty = langs.some((l) => drafts[l].sms !== original[l].sms || drafts[l].whatsapp !== original[l].whatsapp);
  const preview = useMemo(() => (dirty ? runGuards(toVersions(drafts, langs)) : null), [dirty, drafts, langs]);
  const wardName = new Map(city?.wards.map((w) => [w.id, w]) ?? []);
  const targetPop = alert.target_wards.reduce((s, id) => s + (wardName.get(id)?.population ?? 0), 0);

  const requireReviewer = (): string | null => {
    const name = reviewer.trim();
    if (name.length < 2) {
      setReviewerError('Enter your full name — a named human reviewer is required to send.');
      reviewerRef.current?.focus();
      return null;
    }
    setReviewerError(null);
    try {
      sessionStorage.setItem(REVIEWER_KEY, name);
    } catch {
      /* ignore */
    }
    return name;
  };

  const act = async (kind: 'save' | 'approve' | 'reject') => {
    const name = requireReviewer();
    if (!name) return;
    if (kind === 'reject' && !reason.trim()) {
      setError('Give a short reason for rejecting this alert.');
      return;
    }
    setBusy(kind);
    setError(null);
    try {
      let current = alert;
      if (dirty && kind !== 'reject') {
        current = await client.updateAlert(alert.id, toVersions(drafts, langs), name);
        onChanged(current);
        if (kind === 'approve' && current.guards.some((g) => !g.passed)) {
          throw new Error('Edits saved, but some guards fail — fix the highlighted issues before sending.');
        }
      }
      if (kind === 'approve') onChanged(await client.approveAlert(alert.id, name));
      if (kind === 'reject') {
        onChanged(await client.rejectAlert(alert.id, name, reason.trim()));
        setRejecting(false);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const d = drafts[lang];
  return (
    <div className="space-y-4" data-testid="alert-editor" data-alert-id={alert.id}>
      <Panel bodyClassName="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="kicker">Alert · {city ? `${city.name}, ${city.state}` : titleCase(alert.city_id)}</div>
            <h2 className="mt-0.5 flex flex-wrap items-center gap-2 text-lg font-semibold text-white">
              <span className="font-mono text-base">{alert.id}</span>
              <LevelChip level={alert.level} />
              {alert.edited && <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-violet-200">edited</span>}
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Drafted {fmtTime(alert.created_at)} IST · run{' '}
              <Link className="text-sky-300 hover:underline" to={`/agents?run=${encodeURIComponent(alert.run_id)}`}>
                {alert.run_id}
              </Link>
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-400">Status</span>
            <StatusChip status={alert.status} testId="alert-status" />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Target wards">
          {alert.target_wards.map((id) => (
            <span key={id} className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-xs text-slate-200">
              {wardName.get(id)?.name ?? id}
            </span>
          ))}
          {targetPop > 0 && <span className="px-1 text-xs text-slate-400">≈ {fmtCompact(targetPop)} residents</span>}
        </div>
      </Panel>

      <Panel bodyClassName="p-0">
        <div role="tablist" aria-label="Alert language" className="flex overflow-x-auto border-b border-white/[0.06] px-2">
          {langs.map((l) => (
            <button
              key={l}
              role="tab"
              type="button"
              id={`tab-${l}`}
              aria-selected={lang === l}
              aria-controls={`panel-${l}`}
              onClick={() => setLang(l)}
              className={`relative whitespace-nowrap px-3.5 py-2.5 text-sm font-medium transition-colors ${lang === l ? 'text-white' : 'text-slate-400 hover:text-slate-200'}`}
            >
              {LANG_NAMES[l]}
              {(drafts[l].sms !== original[l].sms || drafts[l].whatsapp !== original[l].whatsapp) && <span className="ml-1 text-violet-300" aria-label="edited">•</span>}
              {lang === l && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-sky-400" />}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`panel-${lang}`} aria-labelledby={`tab-${lang}`} className="grid gap-4 p-4 lg:grid-cols-2" lang={lang}>
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label htmlFor="sms-text" className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <MessageSquare className="h-3.5 w-3.5 text-sky-300" aria-hidden /> SMS
              </label>
              <SmsCounter text={d.sms} lang={lang} />
            </div>
            <textarea
              id="sms-text"
              data-testid="sms-text"
              value={d.sms}
              readOnly={!pending}
              onChange={(e) => setDrafts((p) => ({ ...p, [lang]: { ...p[lang], sms: e.target.value } }))}
              rows={5}
              className="input resize-y font-mono text-[13px] leading-relaxed read-only:opacity-80"
            />
          </div>
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label htmlFor="wa-text" className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <MessageCircle className="h-3.5 w-3.5 text-emerald-300" aria-hidden /> WhatsApp
              </label>
              <span className="font-mono text-[11px] text-slate-400">{d.whatsapp.length}/1024</span>
            </div>
            <textarea
              id="wa-text"
              value={d.whatsapp}
              readOnly={!pending}
              onChange={(e) => setDrafts((p) => ({ ...p, [lang]: { ...p[lang], whatsapp: e.target.value } }))}
              rows={5}
              className="input resize-y text-[13px] leading-relaxed read-only:opacity-80"
            />
          </div>
        </div>
        {dirty && pending && (
          <div className="flex flex-wrap items-center gap-2 border-t border-white/[0.06] px-4 py-2.5 text-xs text-violet-200">
            Unsaved edits — guards re-run on save.
            <button type="button" className="btn-ghost ml-auto px-2.5 py-1 text-xs" onClick={() => setDrafts(original)}>
              <Undo2 className="h-3.5 w-3.5" aria-hidden /> Discard
            </button>
            <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => act('save')} disabled={!!busy} data-testid="save-edits">
              {busy === 'save' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" aria-hidden />} Save edits
            </button>
          </div>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel bodyClassName="p-4">
          <GuardList guards={alert.guards} title="Guard results (server)" />
          {preview && (
            <div className="mt-4 border-t border-white/[0.06] pt-3">
              <GuardList guards={preview} title="Preview checks for your edits" />
            </div>
          )}
        </Panel>

        <Panel bodyClassName="p-4">
          {pending ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void act('approve');
              }}
              noValidate
            >
              <h3 className="kicker mb-2 flex items-center gap-1.5">
                <UserCheck className="h-3.5 w-3.5" aria-hidden /> Human approval
              </h3>
              <label htmlFor="reviewer" className="mb-1 block text-xs text-slate-300">
                Reviewer name <span className="text-red-300">*</span>
              </label>
              <input
                id="reviewer"
                ref={reviewerRef}
                data-testid="reviewer-name"
                value={reviewer}
                onChange={(e) => {
                  setReviewer(e.target.value);
                  if (reviewerError) setReviewerError(null);
                }}
                placeholder="e.g. Duty Officer, ASDMA"
                autoComplete="name"
                aria-invalid={!!reviewerError}
                aria-describedby={reviewerError ? 'reviewer-err' : 'reviewer-help'}
                className={`input ${reviewerError ? 'border-red-400 focus:border-red-400 focus:ring-red-400/30' : ''}`}
              />
              {reviewerError ? (
                <p id="reviewer-err" role="alert" className="mt-1 text-xs text-red-300" data-testid="reviewer-error">
                  {reviewerError}
                </p>
              ) : (
                <p id="reviewer-help" className="mt-1 text-[11px] text-slate-500">
                  Your name is recorded with the dispatch. Dispatch is simulated in this prototype.
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="submit" className="btn-success flex-1" disabled={!!busy} data-testid="approve-alert">
                  {busy === 'approve' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Send className="h-4 w-4" aria-hidden />}
                  Approve &amp; send
                </button>
                <button type="button" className="btn-danger" onClick={() => setRejecting((r) => !r)} disabled={!!busy} data-testid="reject-alert">
                  <XCircle className="h-4 w-4" aria-hidden /> Reject
                </button>
              </div>
              {rejecting && (
                <div className="mt-3 space-y-2 rounded-lg border border-red-500/30 bg-red-950/20 p-3">
                  <label htmlFor="reject-reason" className="block text-xs text-slate-300">
                    Reason for rejection
                  </label>
                  <input id="reject-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="input" placeholder="e.g. Ward list incomplete; re-draft" />
                  <button type="button" className="btn-danger w-full" onClick={() => act('reject')} disabled={!!busy} data-testid="confirm-reject">
                    {busy === 'reject' && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />} Confirm rejection
                  </button>
                </div>
              )}
              {error && (
                <p role="alert" className="mt-3 rounded-md border border-red-500/40 bg-red-950/40 p-2 text-xs text-red-200">
                  {error}
                </p>
              )}
            </form>
          ) : (
            <div>
              <h3 className="kicker mb-2 flex items-center gap-1.5">
                <UserCheck className="h-3.5 w-3.5" aria-hidden /> Review record
              </h3>
              <p className="text-sm text-slate-200">
                {alert.status === 'sent' ? 'Approved and sent' : titleCase(alert.status)} by <strong>{alert.reviewed_by ?? '—'}</strong>
              </p>
              <p className="text-xs text-slate-400">{fmtTime(alert.reviewed_at)} IST</p>
            </div>
          )}
        </Panel>
      </div>

      {alert.dispatch_log.length > 0 && (
        <Panel title="Dispatch log (simulated)" icon={<Send className="h-3.5 w-3.5" />} bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" data-testid="dispatch-log">
              <thead className="text-[10px] uppercase tracking-wider text-slate-400">
                <tr className="border-b border-white/[0.06]">
                  <th className="px-4 py-2 font-semibold">Time (IST)</th>
                  <th className="px-4 py-2 font-semibold">Channel</th>
                  <th className="px-4 py-2 font-semibold">Language</th>
                  <th className="px-4 py-2 text-right font-semibold">Recipients (est.)</th>
                  <th className="px-4 py-2 font-semibold">Mode</th>
                </tr>
              </thead>
              <tbody>
                {alert.dispatch_log.map((e, i) => (
                  <tr key={i} className="border-b border-white/[0.04] last:border-0">
                    <td className="px-4 py-1.5 font-mono text-slate-300">{fmtTime(e.ts)}</td>
                    <td className="px-4 py-1.5 text-slate-200">{e.channel === 'sms' ? 'SMS' : 'WhatsApp'}</td>
                    <td className="px-4 py-1.5 text-slate-200">{LANG_NAMES[e.lang]}</td>
                    <td className="px-4 py-1.5 text-right font-mono tabular-nums text-slate-200">{fmtInt(e.recipients_estimate)}</td>
                    <td className="px-4 py-1.5">
                      <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase text-slate-400">simulated</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- sitrep
function SitRepViewer({ runs, initialRunId, cities }: { runs: AgentRun[]; initialRunId: string | null; cities: Map<string, City> }) {
  const { client } = useApi();
  const withRep = runs.filter((r) => r.sitrep);
  const [runId, setRunId] = useState<string | null>(initialRunId);
  useEffect(() => setRunId(initialRunId), [initialRunId]);
  const run = withRep.find((r) => r.id === runId) ?? withRep[0];
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!run?.sitrep) {
    return (
      <Panel id="sitrep" title="Situation report" icon={<FileText className="h-3.5 w-3.5" />}>
        <p className="text-sm text-slate-400">No situation report yet — run the response agents for a city.</p>
      </Panel>
    );
  }
  const rep = run.sitrep;
  const city = cities.get(rep.city_id);
  const pdfUrl = client.sitrepPdfUrl(run.id);
  const exportPdf = async () => {
    setBusy(true);
    setErr(null);
    try {
      const { buildSitrepPdf } = await import('../lib/sitrepPdf');
      const doc = buildSitrepPdf(rep, { cityName: city?.name ?? rep.city_id, demo: client.mode === 'demo' });
      doc.save(`sitrep-${rep.city_id}-${run.id}.pdf`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel
      id="sitrep"
      title="Situation report"
      icon={<FileText className="h-3.5 w-3.5" />}
      actions={
        <div className="flex items-center gap-2">
          {withRep.length > 1 && (
            <select aria-label="Select situation report" value={run.id} onChange={(e) => setRunId(e.target.value)} className="max-w-[220px] rounded-md border border-white/10 bg-ink-900 px-1.5 py-1 text-xs text-slate-200">
              {withRep.map((r) => (
                <option key={r.id} value={r.id}>
                  {cities.get(r.city_id)?.name ?? r.city_id} · {fmtTime(r.started_at)}
                </option>
              ))}
            </select>
          )}
          {pdfUrl ? (
            <a href={pdfUrl} className="btn-ghost px-2.5 py-1 text-xs" data-testid="export-pdf" target="_blank" rel="noreferrer">
              <Download className="h-3.5 w-3.5" aria-hidden /> Export PDF
            </a>
          ) : (
            <button type="button" onClick={exportPdf} className="btn-ghost px-2.5 py-1 text-xs" data-testid="export-pdf" disabled={busy}>
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Download className="h-3.5 w-3.5" aria-hidden />} Export PDF
            </button>
          )}
        </div>
      }
    >
      <article className="mx-auto max-w-3xl" data-testid="sitrep">
        <p className="kicker">
          {city?.name ?? rep.city_id} · generated {fmtTime(rep.generated_at)} IST
        </p>
        <h3 className="mt-1 text-xl font-semibold text-white">{rep.title}</h3>
        <p className="mt-2 text-[15px] leading-relaxed text-slate-200">{rep.summary}</p>
        <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {rep.key_figures.map((k) => (
            <div key={k.label} className="rounded-lg border border-white/[0.06] bg-ink-900/70 px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-slate-400">{k.label}</dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-100">{k.value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 space-y-4">
          {rep.sections.map((s) => (
            <section key={s.heading}>
              <h4 className="text-sm font-semibold text-sky-300">{s.heading}</h4>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{s.body}</p>
            </section>
          ))}
        </div>
        {err && <p role="alert" className="mt-3 text-xs text-red-300">{err}</p>}
      </article>
    </Panel>
  );
}

// ---------------------------------------------------------------- page
export default function Admin() {
  const { client, version } = useApi();
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [filter, setFilter] = useState<'all' | AlertStatus>('all');
  const alerts = useAsync(() => client.alerts(), [client, version]);
  const runs = useAsync(() => client.runs(), [client, version]);
  const cities = useAsync(() => client.cities(), [client]);
  const [local, setLocal] = useState<Record<string, Alert>>({});

  // Server data wins once it has been refetched after a mutation.
  useEffect(() => setLocal({}), [alerts.data]);
  const cityMap = useMemo(() => new Map((cities.data ?? []).map((c) => [c.city.id, c.city])), [cities.data]);
  const list = useMemo(() => (alerts.data ?? []).map((a) => local[a.id] ?? a), [alerts.data, local]);
  const shown = list.filter((a) => filter === 'all' || a.status === filter);
  const wanted = params.get('alert');
  const selected = list.find((a) => a.id === wanted) ?? list.find((a) => a.status === 'pending_approval') ?? list[0];
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: list.length };
    for (const a of list) c[a.status] = (c[a.status] ?? 0) + 1;
    return c;
  }, [list]);
  const sitrepRun = params.get('run') ?? selected?.run_id ?? null;

  useEffect(() => {
    if (location.hash === '#sitrep') document.getElementById('sitrep')?.scrollIntoView({ behavior: 'smooth' });
  }, [location.hash, runs.data]);

  return (
    <div className="scroll-thin flex-1 p-3 sm:p-5 lg:h-full lg:overflow-y-auto">
      <div className="mx-auto grid max-w-[1720px] gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Panel title="Alert queue" icon={<Inbox className="h-3.5 w-3.5" />} bodyClassName="p-0" className="self-start xl:sticky xl:top-0">
          <div role="tablist" aria-label="Filter alerts by status" className="flex gap-1 border-b border-white/[0.06] p-2">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filter === f.id}
                onClick={() => setFilter(f.id)}
                className={`flex-1 rounded-md px-2 py-1 text-xs font-medium ${filter === f.id ? 'bg-sky-500/15 text-sky-200' : 'text-slate-400 hover:bg-white/5'}`}
              >
                {f.label} <span className="font-mono text-[10px] opacity-70">{counts[f.id] ?? 0}</span>
              </button>
            ))}
          </div>
          {alerts.error && !alerts.data ? (
            <div className="p-3"><ErrorNote error={alerts.error} onRetry={alerts.reload} /></div>
          ) : !alerts.data ? (
            <div className="space-y-2 p-3"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
          ) : shown.length ? (
            <ul className="scroll-thin max-h-[60vh] overflow-y-auto p-2" data-testid="alert-queue">
              {shown.map((a) => {
                const c = cityMap.get(a.city_id);
                const en = a.versions.find((v) => v.lang === 'en');
                const sel = a.id === selected?.id;
                return (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => setParams({ alert: a.id })}
                      aria-current={sel ? 'true' : undefined}
                      className={`mb-1 w-full rounded-lg border p-2.5 text-left transition-colors ${sel ? 'border-sky-400/50 bg-sky-500/10' : 'border-white/[0.05] hover:bg-white/[0.03]'}`}
                    >
                      <div className="flex items-center gap-2">
                        <LevelChip level={a.level} size="xs" label={a.level} />
                        <span className="flex-1 truncate text-sm font-semibold text-slate-100">{c?.name ?? titleCase(a.city_id)}</span>
                        <StatusChip status={a.status} />
                      </div>
                      {en && <p className="mt-1 line-clamp-2 text-xs text-slate-400">{en.sms}</p>}
                      <p className="mt-1 font-mono text-[10px] text-slate-500">
                        {fmtTime(a.created_at)} · {a.target_wards.length} wards · {a.guards.filter((g) => !g.passed).length ? 'guard failure' : 'guards ok'}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState icon={<Inbox className="h-7 w-7" />} title={list.length ? 'Nothing in this filter' : 'No alerts drafted yet'}>
              {!list.length && (
                <>
                  Run the response agents from the <Link to="/" className="text-sky-300 underline">dashboard</Link>
                  {client.mode === 'demo' ? ', or advance the replay.' : '.'}
                </>
              )}
            </EmptyState>
          )}
        </Panel>

        <div className="min-w-0 space-y-4">
          {selected ? (
            <AlertEditor key={selected.id} alert={selected} city={cityMap.get(selected.city_id)} onChanged={(a) => {
                setLocal((p) => ({ ...p, [a.id]: a }));
                alerts.reload();
              }} />
          ) : alerts.data ? (
            <Panel>
              <EmptyState icon={<ShieldCheck className="h-8 w-8" />} title="Safety gate">
                Agents can only draft. Every alert waits here until a named human approves it; dispatch is simulated and logged.
              </EmptyState>
            </Panel>
          ) : (
            <Skeleton className="h-96" />
          )}
          {runs.data && <SitRepViewer runs={runs.data} initialRunId={sitrepRun} cities={cityMap} />}
        </div>
      </div>
    </div>
  );
}
