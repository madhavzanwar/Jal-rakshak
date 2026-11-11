import { z } from 'zod';
import type { ApiClient, RunAgentsResult } from './client';
import { ApiError } from './errors';
import {
  AgentRunSchema,
  AgentStepSchema,
  AlertSchema,
  CityRiskSchema,
  CitySummarySchema,
  EvacuationPlanSchema,
  FacilitySchema,
  GeocodeResultSchema,
  HealthSchema,
  PointRiskSchema,
  type AlertStatus,
  type AlertVersion,
} from './schema';

export class HttpClient implements ApiClient {
  readonly mode = 'live' as const;
  private readonly base: string;
  private readonly fetchImpl: typeof fetch;

  constructor(base = '/api', fetchImpl: typeof fetch = (...a) => fetch(...a)) {
    this.base = base.replace(/\/$/, '');
    this.fetchImpl = fetchImpl;
  }

  private async request<S extends z.ZodTypeAny>(
    schema: S,
    path: string,
    init?: RequestInit & { timeoutMs?: number },
  ): Promise<z.infer<S>> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 60_000);
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.base}${path}`, {
        ...init,
        signal: ctrl.signal,
        headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
      });
    } catch (e) {
      throw new ApiError(0, `Network error: ${(e as Error).message}`);
    } finally {
      clearTimeout(timer);
    }
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (body?.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, msg);
    }
    const json: unknown = await res.json();
    const parsed = schema.safeParse(json);
    if (!parsed.success) {
      console.error(`Contract mismatch for ${path}`, parsed.error.issues);
      throw new ApiError(502, `Contract mismatch for ${path}: ${parsed.error.issues.slice(0, 3).map((i) => `${i.path.join('.')}: ${i.message}`).join('; ')}`);
    }
    return parsed.data;
  }

  private post<S extends z.ZodTypeAny>(schema: S, path: string, body: unknown, method = 'POST') {
    return this.request(schema, path, { method, body: JSON.stringify(body), timeoutMs: 180_000 });
  }

  health() {
    return this.request(HealthSchema, '/health', { timeoutMs: 3500 });
  }
  cities() {
    return this.request(z.array(CitySummarySchema), '/cities');
  }
  cityRisk(cityId: string) {
    return this.request(CityRiskSchema, `/cities/${encodeURIComponent(cityId)}/risk`);
  }
  facilities(cityId: string) {
    return this.request(z.array(FacilitySchema), `/cities/${encodeURIComponent(cityId)}/facilities`);
  }
  pointRisk(lat: number, lon: number) {
    return this.request(PointRiskSchema, `/risk/point?lat=${lat}&lon=${lon}`);
  }
  geocode(q: string) {
    return this.request(z.array(GeocodeResultSchema), `/geocode?q=${encodeURIComponent(q)}`);
  }
  evacuationPlan(body: { lat: number; lon: number; city_id?: string }) {
    return this.post(EvacuationPlanSchema, '/evacuation/plan', body);
  }
  async runAgents(cityId: string): Promise<RunAgentsResult> {
    const run = await this.post(AgentRunSchema, '/agents/run', { city_id: cityId, trigger: 'manual' });
    return { run };
  }
  runs(cityId?: string) {
    return this.request(z.array(AgentRunSchema), `/agents/runs${cityId ? `?city_id=${encodeURIComponent(cityId)}` : ''}`);
  }
  run(runId: string) {
    return this.request(AgentRunSchema, `/agents/runs/${encodeURIComponent(runId)}`);
  }
  timeline(limit = 200) {
    return this.request(z.array(AgentStepSchema), `/timeline?limit=${limit}`);
  }
  alerts(status?: AlertStatus) {
    return this.request(z.array(AlertSchema), `/alerts${status ? `?status=${status}` : ''}`);
  }
  updateAlert(id: string, versions: AlertVersion[], reviewer: string) {
    return this.post(AlertSchema, `/alerts/${encodeURIComponent(id)}`, { versions, reviewer }, 'PUT');
  }
  approveAlert(id: string, reviewer: string) {
    return this.post(AlertSchema, `/alerts/${encodeURIComponent(id)}/approve`, { reviewer });
  }
  rejectAlert(id: string, reviewer: string, reason: string) {
    return this.post(AlertSchema, `/alerts/${encodeURIComponent(id)}/reject`, { reviewer, reason });
  }
  sitrepPdfUrl(runId: string) {
    return `${this.base}/sitrep/${encodeURIComponent(runId)}.pdf`;
  }
}
