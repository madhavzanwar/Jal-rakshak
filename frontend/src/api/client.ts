/**
 * ApiClient — the single interface the UI talks to.
 * Implementations: HttpClient (live FastAPI backend) and DemoClient (offline replay of
 * public/demo/scenario.json with simulated POSTs).
 */
import type {
  AgentRun,
  AgentStep,
  Alert,
  AlertStatus,
  AlertVersion,
  CityRisk,
  CitySummary,
  EvacuationPlan,
  Facility,
  GeocodeResult,
  Health,
  PointRisk,
} from './schema';

export type ApiMode = 'live' | 'demo';

export interface RunAgentsResult {
  run: AgentRun;
  /** Demo only: the replay jumped to this frame to show the recorded run. */
  jumpedToFrame?: number;
  note?: string;
}

export interface ApiClient {
  readonly mode: ApiMode;
  health(): Promise<Health>;
  cities(): Promise<CitySummary[]>;
  cityRisk(cityId: string): Promise<CityRisk>;
  facilities(cityId: string): Promise<Facility[]>;
  pointRisk(lat: number, lon: number): Promise<PointRisk>;
  geocode(q: string): Promise<GeocodeResult[]>;
  evacuationPlan(body: { lat: number; lon: number; city_id?: string }): Promise<EvacuationPlan>;
  runAgents(cityId: string): Promise<RunAgentsResult>;
  runs(cityId?: string): Promise<AgentRun[]>;
  run(runId: string): Promise<AgentRun>;
  timeline(limit?: number): Promise<AgentStep[]>;
  alerts(status?: AlertStatus): Promise<Alert[]>;
  updateAlert(id: string, versions: AlertVersion[], reviewer: string): Promise<Alert>;
  approveAlert(id: string, reviewer: string): Promise<Alert>;
  rejectAlert(id: string, reviewer: string, reason: string): Promise<Alert>;
  /** Server PDF URL (live) or null when the PDF must be generated client-side (demo). */
  sitrepPdfUrl(runId: string): string | null;
}

export { HttpClient } from './http';
export { DemoClient } from './demo';
export { ApiError } from './errors';
