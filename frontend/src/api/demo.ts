/**
 * DemoClient — serves the recorded DemoScenario (public/demo/scenario.json) through the same
 * ApiClient interface as the live backend. GETs read the current replay frame; POSTs are
 * simulated in-browser and persisted to localStorage so a judge can approve/reject offline.
 */
import type { ApiClient, RunAgentsResult } from './client';
import { ApiError } from './errors';
import {
  DemoScenarioSchema,
  type AgentRun,
  type AgentStep,
  type Alert,
  type AlertStatus,
  type AlertVersion,
  type City,
  type CityRisk,
  type DemoFrame,
  type DemoScenario,
  type DispatchEntry,
  type EvacuationPlan,
  type Facility,
  type GeocodeResult,
  type Health,
  type Lang,
  type PointRisk,
  type Route,
} from './schema';
import { ADVICE } from '../lib/advice';
import { haversineKm } from '../lib/geo';
import { fmtTime } from '../lib/format';
import { CLIENT_GUARD_NAMES, runGuards } from '../lib/guards';

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface PersistedState {
  alerts: Record<string, Alert>;
  triggered: string[];
}

type Listener = () => void;

const LANG_SHARE: Record<Lang, number> = { en: 0.18, hi: 0.34, mr: 0.14, ta: 0.14, bn: 0.2 };
const WALK_MPS = 1.25;

function safeStorage(): KeyValueStore | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const k = '__jr_probe__';
    localStorage.setItem(k, '1');
    localStorage.removeItem(k);
    return localStorage;
  } catch {
    return null;
  }
}

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}

export class DemoClient implements ApiClient {
  readonly mode = 'demo' as const;
  readonly scenario: DemoScenario;
  private frameIdx = 0;
  private listeners = new Set<Listener>();
  private state: PersistedState = { alerts: {}, triggered: [] };
  private readonly storage: KeyValueStore | null;
  private readonly storageKey: string;
  /** Artificial latency so the UI behaves like a network client. */
  private readonly latencyMs: number;

  constructor(scenario: DemoScenario, opts: { storage?: KeyValueStore | null; latencyMs?: number; initialFrame?: number } = {}) {
    this.scenario = scenario;
    this.storage = opts.storage === undefined ? safeStorage() : opts.storage;
    this.latencyMs = opts.latencyMs ?? 0;
    this.storageKey = `jalrakshak.demo.v1.${scenario.id}.${scenario.recorded_with.recorded_at}`;
    this.frameIdx = Math.max(0, Math.min(opts.initialFrame ?? 0, scenario.frames.length - 1));
    this.restore();
  }

  /** Parse (and validate) an unknown JSON value as a DemoScenario. */
  static fromJson(json: unknown, opts?: ConstructorParameters<typeof DemoClient>[1]): DemoClient {
    const parsed = DemoScenarioSchema.safeParse(json);
    if (!parsed.success) {
      const issues = parsed.error.issues.slice(0, 5).map((i) => `${i.path.join('.')}: ${i.message}`);
      throw new Error(`Demo scenario does not match the contract:\n${issues.join('\n')}`);
    }
    return new DemoClient(parsed.data, opts);
  }

  static async load(url: string, opts?: ConstructorParameters<typeof DemoClient>[1]): Promise<DemoClient> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Could not load demo scenario (${res.status})`);
    return DemoClient.fromJson(await res.json(), { latencyMs: 120, ...opts });
  }

  // ---------- replay control ----------
  get frameCount(): number {
    return this.scenario.frames.length;
  }
  get frameIndex(): number {
    return this.frameIdx;
  }
  get frame(): DemoFrame {
    return this.scenario.frames[this.frameIdx]!;
  }
  setFrame(i: number): void {
    const next = Math.max(0, Math.min(Math.round(i), this.frameCount - 1));
    if (next === this.frameIdx) return;
    this.frameIdx = next;
    this.emit();
  }
  nextFrame(loop = false): void {
    if (this.frameIdx >= this.frameCount - 1) {
      if (loop) this.setFrame(0);
      return;
    }
    this.setFrame(this.frameIdx + 1);
  }
  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
  /** Clears simulated reviewer actions and triggered runs. */
  reset(): void {
    this.state = { alerts: {}, triggered: [] };
    this.storage?.removeItem(this.storageKey);
    this.frameIdx = 0;
    this.emit();
  }

  private emit() {
    for (const l of this.listeners) l();
  }
  private persist() {
    try {
      this.storage?.setItem(this.storageKey, JSON.stringify(this.state));
    } catch {
      /* quota / private mode — keep in memory */
    }
  }
  private restore() {
    try {
      const raw = this.storage?.getItem(this.storageKey);
      if (!raw) return;
      const s = JSON.parse(raw) as Partial<PersistedState>;
      this.state = { alerts: s.alerts ?? {}, triggered: Array.isArray(s.triggered) ? s.triggered : [] };
    } catch {
      this.state = { alerts: {}, triggered: [] };
    }
  }
  private async delay<T>(v: T): Promise<T> {
    if (this.latencyMs > 0) await new Promise((r) => setTimeout(r, this.latencyMs));
    return clone(v);
  }

  // ---------- helpers ----------
  private findCity(cityId: string): City {
    const s = this.frame.cities.find((c) => c.city.id === cityId);
    if (!s) throw new ApiError(404, `Unknown city ${cityId}`);
    return s.city;
  }
  private runFrame(runId: string): number {
    return this.scenario.agent_runs.find((r) => r.run.id === runId)?.frame ?? Number.POSITIVE_INFINITY;
  }
  private isRunVisible(runId: string): boolean {
    return this.runFrame(runId) <= this.frameIdx || this.state.triggered.includes(runId);
  }
  private visibleRuns(): AgentRun[] {
    return this.scenario.agent_runs
      .filter((r) => this.isRunVisible(r.run.id))
      .map((r) => r.run)
      .sort((a, b) => b.started_at.localeCompare(a.started_at));
  }
  private currentAlert(id: string): Alert | undefined {
    return this.state.alerts[id] ?? this.scenario.alerts.find((a) => a.id === id);
  }
  private mustAlert(id: string): Alert {
    const a = this.currentAlert(id);
    if (!a || !this.isRunVisible(a.run_id)) throw new ApiError(404, `Alert ${id} not found`);
    return a;
  }
  private saveAlert(a: Alert): Alert {
    this.state.alerts[a.id] = a;
    this.persist();
    this.emit();
    return a;
  }

  // ---------- GET ----------
  health(): Promise<Health> {
    const r = this.scenario.recorded_with;
    return this.delay({ status: 'ok' as const, version: `demo:${this.scenario.id}`, llm: { provider: r.provider, model: r.model, available: false }, demo: true });
  }
  cities() {
    return this.delay(this.frame.cities);
  }
  cityRisk(cityId: string): Promise<CityRisk> {
    const d = this.frame.details[cityId];
    if (!d) return Promise.reject(new ApiError(404, `No risk data for ${cityId} in this frame`));
    return this.delay(d);
  }
  facilities(cityId: string): Promise<Facility[]> {
    return this.delay(this.scenario.facilities[cityId] ?? []);
  }
  geocode(q: string): Promise<GeocodeResult[]> {
    const key = q.trim().toLowerCase();
    if (!key) return this.delay([]);
    const exact = this.scenario.geocode[key];
    if (exact) return this.delay(exact);
    const partial = Object.entries(this.scenario.geocode).find(([k]) => k.includes(key) || key.includes(k));
    if (partial) return this.delay(partial[1]);
    // Fall back to matching city / ward names from the scenario itself.
    const out: GeocodeResult[] = [];
    for (const s of this.frame.cities) {
      const c = s.city;
      if (c.name.toLowerCase().includes(key)) out.push({ display_name: `${c.name}, ${c.state}, India`, lat: c.lat, lon: c.lon });
      for (const w of c.wards) {
        if (w.name.toLowerCase().includes(key)) out.push({ display_name: `${w.name}, ${c.name}, ${c.state}, India`, lat: w.lat, lon: w.lon });
      }
    }
    return this.delay(out.slice(0, 8));
  }

  private planFrom(lat: number, lon: number, cityId: string): EvacuationPlan {
    const facilities = (this.scenario.facilities[cityId] ?? []).filter((f) => f.type !== 'hospital');
    const pool = facilities.length ? facilities : this.scenario.facilities[cityId] ?? [];
    if (!pool.length) throw new ApiError(404, `No facilities for ${cityId}`);
    const ranked = pool
      .map((f) => ({ f, km: haversineKm(lat, lon, f.lat, f.lon) }))
      .sort((a, b) => a.km - b.km);
    const route = (f: Facility, km: number): Route => {
      const distance_m = Math.round(km * 1000 * 1.3); // detour factor for straight-line estimates
      return { method: 'straight_line', distance_m, duration_s: Math.round(distance_m / WALK_MPS), geometry: [[lat, lon], [f.lat, f.lon]] };
    };
    const [first, ...rest] = ranked;
    return {
      origin: { lat, lon },
      facility: first!.f,
      route: route(first!.f, first!.km),
      alternatives: rest.slice(0, 2).map((r) => ({ facility: r.f, route: route(r.f, r.km) })),
      notes: [
        'Demo mode: straight-line estimate ×1.3 detour factor (no road routing offline).',
        'Walking time assumes 1.25 m/s; allow extra time in rain and flood water.',
      ],
    };
  }

  pointRisk(lat: number, lon: number): Promise<PointRisk> {
    const nearest = this.frame.cities
      .map((s) => ({ s, km: haversineKm(lat, lon, s.city.lat, s.city.lon) }))
      .sort((a, b) => a.km - b.km)[0];
    if (!nearest) return Promise.reject(new ApiError(404, 'No cities in scenario'));
    const city = nearest.s.city;
    const detail = this.frame.details[city.id];
    const ward = city.wards
      .map((w) => ({ w, km: haversineKm(lat, lon, w.lat, w.lon) }))
      .sort((a, b) => a.km - b.km)[0]?.w;
    if (!ward) return Promise.reject(new ApiError(404, `No wards for ${city.id}`));
    const risk = detail?.wards.find((w) => w.ward_id === ward.id)?.risk ?? nearest.s.risk;
    return this.delay({
      lat,
      lon,
      city,
      ward,
      distance_to_city_km: Math.round(nearest.km * 10) / 10,
      risk,
      advice: ADVICE[risk.level],
      evacuation: this.planFrom(lat, lon, city.id),
      emergency: city.emergency,
      stale: detail?.stale ?? nearest.s.stale,
    });
  }

  evacuationPlan(body: { lat: number; lon: number; city_id?: string }): Promise<EvacuationPlan> {
    const cityId =
      body.city_id ??
      this.frame.cities.map((s) => ({ id: s.city.id, km: haversineKm(body.lat, body.lon, s.city.lat, s.city.lon) })).sort((a, b) => a.km - b.km)[0]?.id;
    if (!cityId) return Promise.reject(new ApiError(404, 'No city'));
    return this.delay(this.planFrom(body.lat, body.lon, cityId));
  }

  runs(cityId?: string) {
    return this.delay(this.visibleRuns().filter((r) => !cityId || r.city_id === cityId));
  }
  run(runId: string): Promise<AgentRun> {
    const r = this.scenario.agent_runs.find((x) => x.run.id === runId);
    if (!r || !this.isRunVisible(runId)) return Promise.reject(new ApiError(404, `Run ${runId} not found`));
    return this.delay(r.run);
  }
  timeline(limit = 200): Promise<AgentStep[]> {
    const steps = this.visibleRuns().flatMap((r) => r.steps);
    steps.sort((a, b) => b.ts.localeCompare(a.ts) || b.seq - a.seq);
    return this.delay(steps.slice(0, limit));
  }
  alerts(status?: AlertStatus): Promise<Alert[]> {
    const list = this.scenario.alerts
      .filter((a) => this.isRunVisible(a.run_id))
      .map((a) => this.currentAlert(a.id)!)
      .filter((a) => !status || a.status === status)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    return this.delay(list);
  }

  // ---------- simulated POSTs ----------
  /**
   * Reveals the recorded run for the city. Prefers the latest run recorded at or before the
   * current frame; otherwise jumps the replay forward to the first recorded run.
   */
  async runAgents(cityId: string): Promise<RunAgentsResult> {
    const city = this.findCity(cityId);
    const candidates = this.scenario.agent_runs.filter((r) => r.run.city_id === cityId).sort((a, b) => a.frame - b.frame);
    if (!candidates.length) {
      throw new ApiError(404, `No recorded agent run for ${city.name} in this demo replay. Try a city at orange/red level (e.g. Guwahati).`);
    }
    const atOrBefore = candidates.filter((r) => r.frame <= this.frameIdx);
    const chosen = atOrBefore[atOrBefore.length - 1] ?? candidates[0]!;
    let jumpedToFrame: number | undefined;
    if (chosen.frame > this.frameIdx) {
      jumpedToFrame = chosen.frame;
      this.frameIdx = chosen.frame;
    }
    if (!this.state.triggered.includes(chosen.run.id)) this.state.triggered.push(chosen.run.id);
    this.persist();
    this.emit();
    const result: RunAgentsResult = { run: chosen.run };
    if (jumpedToFrame !== undefined) {
      result.jumpedToFrame = jumpedToFrame;
      result.note = `Demo replay jumped to frame ${jumpedToFrame + 1} (${fmtTime(this.scenario.frames[jumpedToFrame]?.t)} IST), when this agent run was recorded.`;
    }
    return this.delay(result);
  }

  async updateAlert(id: string, versions: AlertVersion[], reviewer: string): Promise<Alert> {
    const a = this.mustAlert(id);
    if (a.status !== 'pending_approval') throw new ApiError(409, `Alert is ${a.status}; only pending alerts can be edited`);
    const clientGuards = runGuards(versions);
    const kept = a.guards.filter((g) => !(CLIENT_GUARD_NAMES as readonly string[]).includes(g.name) && !clientGuards.some((c) => c.name === g.name));
    const next: Alert = { ...clone(a), versions: clone(versions), guards: [...clientGuards, ...kept], edited: true, reviewed_by: reviewer || a.reviewed_by };
    return this.delay(this.saveAlert(next));
  }

  async approveAlert(id: string, reviewer: string): Promise<Alert> {
    const a = this.mustAlert(id);
    if (!reviewer.trim()) throw new ApiError(422, 'Reviewer name is required');
    if (a.status !== 'pending_approval') throw new ApiError(409, `Alert is already ${a.status}`);
    const failed = a.guards.filter((g) => !g.passed);
    if (failed.length) throw new ApiError(409, `Guards failed: ${failed.map((g) => g.name).join(', ')}`);
    const now = new Date();
    const city = this.findCityAny(a.city_id);
    const pop = city ? city.wards.filter((w) => a.target_wards.includes(w.id)).reduce((s, w) => s + w.population, 0) : 0;
    const base = pop || 50_000;
    const log: DispatchEntry[] = [];
    let i = 0;
    for (const v of a.versions) {
      for (const channel of ['sms', 'whatsapp'] as const) {
        log.push({
          ts: new Date(now.getTime() + i++ * 400).toISOString(),
          channel,
          lang: v.lang,
          recipients_estimate: Math.round(base * LANG_SHARE[v.lang] * (channel === 'sms' ? 0.72 : 0.41)),
          simulated: true,
        });
      }
    }
    const next: Alert = { ...clone(a), status: 'sent', reviewed_by: reviewer.trim(), reviewed_at: now.toISOString(), dispatch_log: log };
    return this.delay(this.saveAlert(next));
  }

  async rejectAlert(id: string, reviewer: string, reason: string): Promise<Alert> {
    const a = this.mustAlert(id);
    if (!reviewer.trim()) throw new ApiError(422, 'Reviewer name is required');
    if (a.status !== 'pending_approval') throw new ApiError(409, `Alert is already ${a.status}`);
    const next: Alert = {
      ...clone(a),
      status: 'rejected',
      reviewed_by: reviewer.trim(),
      reviewed_at: new Date().toISOString(),
      guards: reason ? [...a.guards, { name: 'reviewer_rejection', passed: false, detail: reason }] : a.guards,
    };
    return this.delay(this.saveAlert(next));
  }

  sitrepPdfUrl(): string | null {
    return null;
  }

  private findCityAny(cityId: string): City | undefined {
    for (const f of [this.frame, ...this.scenario.frames]) {
      const c = f.cities.find((s) => s.city.id === cityId);
      if (c) return c.city;
    }
    return undefined;
  }
}
