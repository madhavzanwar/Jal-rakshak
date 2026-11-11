/**
 * zod schemas for every type in docs/CONTRACT.md (the source of truth).
 * Keep these strict: if the backend drifts from the contract we want a loud parse error,
 * not a silently-wrong UI. Object schemas are non-strict about *extra* keys (forward compatible)
 * but every documented key is required with its documented type.
 */
import { z } from 'zod';

// ---------- Enumerations ----------
export const RiskLevelSchema = z.enum(['green', 'yellow', 'orange', 'red']);
export const LangSchema = z.enum(['en', 'hi', 'mr', 'ta', 'bn']);
export const AgentNameSchema = z.enum(['monitor', 'alert_drafter', 'evacuation_planner', 'sitrep']);
export const StepKindSchema = z.enum(['thought', 'tool_call', 'tool_result', 'decision', 'guard', 'final', 'error']);
export const AlertStatusSchema = z.enum(['pending_approval', 'approved', 'rejected', 'sent']);
export const FacilityTypeSchema = z.enum(['shelter', 'hospital', 'relief_camp']);
export const RouteMethodSchema = z.enum(['osrm', 'straight_line']);
export const GaugeStatusSchema = z.enum(['normal', 'warning', 'danger', 'extreme']);

export type RiskLevel = z.infer<typeof RiskLevelSchema>;
export type Lang = z.infer<typeof LangSchema>;
export type AgentName = z.infer<typeof AgentNameSchema>;
export type StepKind = z.infer<typeof StepKindSchema>;
export type AlertStatus = z.infer<typeof AlertStatusSchema>;
export type FacilityType = z.infer<typeof FacilityTypeSchema>;
export type RouteMethod = z.infer<typeof RouteMethodSchema>;
export type GaugeStatus = z.infer<typeof GaugeStatusSchema>;

const isoDateTime = z.string().min(1);
const latLon = { lat: z.number(), lon: z.number() };

// ---------- Core entities ----------
export const WardSchema = z.object({
  id: z.string(),
  name: z.string(),
  ...latLon,
  radius_m: z.number(),
  population: z.number(),
  elevation_m: z.number(),
  vulnerability: z.number().min(0).max(1),
});

export const RiverGaugeSchema = z.object({
  id: z.string(),
  river: z.string(),
  ...latLon,
  warning_m3s: z.number(),
  danger_m3s: z.number(),
  extreme_m3s: z.number(),
});

export const EmergencyContactSchema = z.object({ label: z.string(), number: z.string() });

export const CitySchema = z.object({
  id: z.string(),
  name: z.string(),
  state: z.string(),
  ...latLon,
  population: z.number(),
  wards: z.array(WardSchema),
  gauges: z.array(RiverGaugeSchema),
  emergency: z.array(EmergencyContactSchema),
});

export const RiskFactorsSchema = z.object({
  rain_24h_mm: z.number(),
  rain_72h_mm: z.number(),
  max_intensity_mmph: z.number(),
  antecedent_7d_mm: z.number(),
  discharge_ratio: z.number(),
  vulnerability: z.number(),
  components: z.object({
    rain: z.number(),
    river: z.number(),
    antecedent: z.number(),
    vulnerability: z.number(),
  }),
});

export const RiskScoreSchema = z.object({
  score: z.number().min(0).max(100),
  level: RiskLevelSchema,
  factors: RiskFactorsSchema,
  explanation: z.string(),
  ml_probability: z.number().nullable(),
});

export const CitySummarySchema = z.object({
  city: CitySchema,
  risk: RiskScoreSchema,
  peak_time: isoDateTime.nullable(),
  stale: z.boolean(),
  updated_at: isoDateTime,
});

export const HorizonPointSchema = z.object({ t: isoDateTime, score: z.number(), level: RiskLevelSchema });
export const RainPointSchema = z.object({ t: isoDateTime, mm: z.number() });
export const DischargePointSchema = z.object({ date: z.string(), m3s: z.number() });

export const GaugeReadingSchema = z.object({
  gauge: RiverGaugeSchema,
  series: z.array(DischargePointSchema),
  current_m3s: z.number(),
  peak_m3s: z.number(),
  peak_date: z.string(),
  status: GaugeStatusSchema,
});

export const WardRiskSchema = z.object({ ward_id: z.string(), risk: RiskScoreSchema });

export const DataSourceSchema = z.object({
  name: z.string(),
  url: z.string(),
  ok: z.boolean(),
  fetched_at: isoDateTime.nullable(),
});

export const CityRiskSchema = z.object({
  city: CitySchema,
  generated_at: isoDateTime,
  stale: z.boolean(),
  data_age_minutes: z.number(),
  sources: z.array(DataSourceSchema),
  overall: RiskScoreSchema,
  horizon: z.array(HorizonPointSchema),
  rainfall: z.array(RainPointSchema),
  gauges: z.array(GaugeReadingSchema),
  wards: z.array(WardRiskSchema),
});

export const FacilitySchema = z.object({
  id: z.string(),
  city_id: z.string(),
  ward_id: z.string(),
  name: z.string(),
  type: FacilityTypeSchema,
  ...latLon,
  capacity: z.number(),
  occupancy: z.number(),
  phone: z.string(),
  elevation_m: z.number(),
});

export const RouteSchema = z.object({
  method: RouteMethodSchema,
  distance_m: z.number(),
  duration_s: z.number(),
  geometry: z.array(z.tuple([z.number(), z.number()])),
});

export const EvacuationPlanSchema = z.object({
  origin: z.object(latLon),
  facility: FacilitySchema,
  route: RouteSchema,
  alternatives: z.array(z.object({ facility: FacilitySchema, route: RouteSchema })).max(2),
  notes: z.array(z.string()),
});

export const AdviceSchema = z.object({
  now: z.array(z.string()),
  prepare: z.array(z.string()),
  avoid: z.array(z.string()),
});

export const PointRiskSchema = z.object({
  ...latLon,
  city: CitySchema,
  ward: WardSchema,
  distance_to_city_km: z.number(),
  risk: RiskScoreSchema,
  advice: AdviceSchema,
  evacuation: EvacuationPlanSchema,
  emergency: z.array(EmergencyContactSchema),
  stale: z.boolean(),
});

export const GeocodeResultSchema = z.object({ display_name: z.string(), ...latLon });

// ---------- Agents ----------
export const AgentStepSchema = z.object({
  id: z.string(),
  run_id: z.string(),
  seq: z.number().int(),
  agent: AgentNameSchema,
  kind: StepKindSchema,
  ts: isoDateTime,
  content: z.string(),
  tool: z.string().nullable(),
  input: z.unknown().nullable(),
  output: z.unknown().nullable(),
  duration_ms: z.number(),
});

export const AlertVersionSchema = z.object({ lang: LangSchema, sms: z.string(), whatsapp: z.string() });
export const GuardResultSchema = z.object({ name: z.string(), passed: z.boolean(), detail: z.string() });

export const DispatchEntrySchema = z.object({
  ts: isoDateTime,
  channel: z.enum(['sms', 'whatsapp']),
  lang: LangSchema,
  recipients_estimate: z.number(),
  simulated: z.literal(true),
});

export const AlertSchema = z.object({
  id: z.string(),
  run_id: z.string(),
  city_id: z.string(),
  level: RiskLevelSchema,
  status: AlertStatusSchema,
  created_at: isoDateTime,
  target_wards: z.array(z.string()),
  versions: z.array(AlertVersionSchema),
  guards: z.array(GuardResultSchema),
  edited: z.boolean(),
  reviewed_by: z.string().nullable(),
  reviewed_at: isoDateTime.nullable(),
  dispatch_log: z.array(DispatchEntrySchema),
});

export const SitRepSchema = z.object({
  run_id: z.string(),
  city_id: z.string(),
  generated_at: isoDateTime,
  title: z.string(),
  summary: z.string(),
  sections: z.array(z.object({ heading: z.string(), body: z.string() })),
  key_figures: z.array(z.object({ label: z.string(), value: z.string() })),
});

export const AgentRunSchema = z.object({
  id: z.string(),
  city_id: z.string(),
  trigger: z.enum(['manual', 'scheduled', 'demo']),
  started_at: isoDateTime,
  finished_at: isoDateTime.nullable(),
  llm: z.object({ provider: z.string(), model: z.string() }),
  decision: z.object({ should_alert: z.boolean(), level: RiskLevelSchema, reason: z.string() }),
  steps: z.array(AgentStepSchema),
  alert_id: z.string().nullable(),
  evacuation: z.array(EvacuationPlanSchema),
  sitrep: SitRepSchema.nullable(),
});

export const HealthSchema = z.object({
  status: z.literal('ok'),
  version: z.string(),
  llm: z.object({ provider: z.string(), model: z.string(), available: z.boolean() }),
  demo: z.boolean(),
});

// ---------- Demo scenario ----------
export const DemoFrameSchema = z.object({
  index: z.number().int(),
  t: isoDateTime,
  caption: z.string(),
  cities: z.array(CitySummarySchema),
  details: z.record(z.string(), CityRiskSchema),
});

export const DemoScenarioSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  recorded_with: z.object({ provider: z.string(), model: z.string(), recorded_at: isoDateTime }),
  frames: z.array(DemoFrameSchema).min(1),
  facilities: z.record(z.string(), z.array(FacilitySchema)),
  agent_runs: z.array(z.object({ frame: z.number().int(), run: AgentRunSchema })),
  alerts: z.array(AlertSchema),
  geocode: z.record(z.string(), z.array(GeocodeResultSchema)),
});

// ---------- Inferred types ----------
export type Ward = z.infer<typeof WardSchema>;
export type RiverGauge = z.infer<typeof RiverGaugeSchema>;
export type EmergencyContact = z.infer<typeof EmergencyContactSchema>;
export type City = z.infer<typeof CitySchema>;
export type RiskFactors = z.infer<typeof RiskFactorsSchema>;
export type RiskScore = z.infer<typeof RiskScoreSchema>;
export type CitySummary = z.infer<typeof CitySummarySchema>;
export type HorizonPoint = z.infer<typeof HorizonPointSchema>;
export type RainPoint = z.infer<typeof RainPointSchema>;
export type DischargePoint = z.infer<typeof DischargePointSchema>;
export type GaugeReading = z.infer<typeof GaugeReadingSchema>;
export type WardRisk = z.infer<typeof WardRiskSchema>;
export type DataSource = z.infer<typeof DataSourceSchema>;
export type CityRisk = z.infer<typeof CityRiskSchema>;
export type Facility = z.infer<typeof FacilitySchema>;
export type Route = z.infer<typeof RouteSchema>;
export type EvacuationPlan = z.infer<typeof EvacuationPlanSchema>;
export type Advice = z.infer<typeof AdviceSchema>;
export type PointRisk = z.infer<typeof PointRiskSchema>;
export type GeocodeResult = z.infer<typeof GeocodeResultSchema>;
export type AgentStep = z.infer<typeof AgentStepSchema>;
export type AlertVersion = z.infer<typeof AlertVersionSchema>;
export type GuardResult = z.infer<typeof GuardResultSchema>;
export type DispatchEntry = z.infer<typeof DispatchEntrySchema>;
export type Alert = z.infer<typeof AlertSchema>;
export type SitRep = z.infer<typeof SitRepSchema>;
export type AgentRun = z.infer<typeof AgentRunSchema>;
export type Health = z.infer<typeof HealthSchema>;
export type DemoFrame = z.infer<typeof DemoFrameSchema>;
export type DemoScenario = z.infer<typeof DemoScenarioSchema>;
