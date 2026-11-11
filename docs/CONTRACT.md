# JalRakshak API & Data Contract (source of truth)

All JSON is **snake_case**. Timestamps are ISO‑8601 UTC strings (`2026-07-02T06:00:00Z`).
Backend (FastAPI + Pydantic v2) MUST serialise exactly these shapes; the frontend parses them with
zod schemas in `frontend/src/api/schema.ts`. The demo scenario file uses the same shapes.

Base URL: `/api` (dev: backend on `http://localhost:8000`, Vite proxies `/api`).

## Enumerations

```ts
type RiskLevel = "green" | "yellow" | "orange" | "red";
// Fixed cut-offs on the 0–100 score: green <30, yellow 30–54.99, orange 55–74.99, red >=75
type Lang = "en" | "hi" | "mr" | "ta" | "bn";
type AgentName = "monitor" | "alert_drafter" | "evacuation_planner" | "sitrep";
type StepKind = "thought" | "tool_call" | "tool_result" | "decision" | "guard" | "final" | "error";
type AlertStatus = "pending_approval" | "approved" | "rejected" | "sent";
type FacilityType = "shelter" | "hospital" | "relief_camp";
type RouteMethod = "osrm" | "straight_line";
type GaugeStatus = "normal" | "warning" | "danger" | "extreme";
```

## Core entities

```ts
interface Ward {            // synthetic but plausible ward/zone (documented as such)
  id: string;               // "guwahati-w03"
  name: string;             // "Anil Nagar"
  lat: number; lon: number;
  radius_m: number;         // drawn as a circle zone on the map
  population: number;       // synthetic estimate
  elevation_m: number;
  vulnerability: number;    // 0..1 (low-lying, drainage, informal housing) – synthetic
}

interface RiverGauge {      // a GloFAS grid cell representing the main river near the city
  id: string;               // "guwahati-brahmaputra"
  river: string;            // "Brahmaputra"
  lat: number; lon: number;
  warning_m3s: number;      // thresholds derived from GloFAS reanalysis percentiles (see README)
  danger_m3s: number;
  extreme_m3s: number;
}

interface City {
  id: string;               // "guwahati"
  name: string;             // "Guwahati"
  state: string;            // "Assam"
  lat: number; lon: number;
  population: number;
  wards: Ward[];
  gauges: RiverGauge[];
  emergency: { label: string; number: string }[];  // 112, NDRF, SDMA, etc.
}

interface RiskFactors {     // inputs (raw) + normalised components (0..1)
  rain_24h_mm: number;      // max rolling 24h sum in the 72h window
  rain_72h_mm: number;
  max_intensity_mmph: number;
  antecedent_7d_mm: number; // observed rain of the past 7 days
  discharge_ratio: number;  // forecast peak discharge / danger threshold (0 if no gauge)
  vulnerability: number;    // 0..1
  components: { rain: number; river: number; antecedent: number; vulnerability: number };
}

interface RiskScore {
  score: number;            // 0..100, 1 decimal
  level: RiskLevel;
  factors: RiskFactors;
  explanation: string;      // one human-readable sentence, deterministic (not LLM)
  ml_probability: number | null;  // optional LightGBM P(flood-day) if model available
}

interface CitySummary {     // GET /api/cities item
  city: City;
  risk: RiskScore;          // overall = max over wards
  peak_time: string | null; // time of the highest horizon score
  stale: boolean;
  updated_at: string;
}

interface HorizonPoint { t: string; score: number; level: RiskLevel }
interface RainPoint    { t: string; mm: number }          // hourly precipitation
interface DischargePoint { date: string; m3s: number }    // daily, YYYY-MM-DD

interface GaugeReading {
  gauge: RiverGauge;
  series: DischargePoint[]; // past 7 days + 7 forecast days
  current_m3s: number;
  peak_m3s: number;         // max over the next 72h (3 forecast days)
  peak_date: string;
  status: GaugeStatus;
}

interface WardRisk { ward_id: string; risk: RiskScore }

interface CityRisk {        // GET /api/cities/{id}/risk
  city: City;
  generated_at: string;
  stale: boolean;           // true if any source fell back to last-known cached data
  data_age_minutes: number;
  sources: { name: string; url: string; ok: boolean; fetched_at: string | null }[];
  overall: RiskScore;
  horizon: HorizonPoint[];  // 3-hourly, 72h → 24 points
  rainfall: RainPoint[];    // hourly, 72 points
  gauges: GaugeReading[];
  wards: WardRisk[];
}

interface Facility {        // shelters / hospitals / relief camps (synthetic seed)
  id: string; city_id: string; ward_id: string;
  name: string; type: FacilityType;
  lat: number; lon: number;
  capacity: number; occupancy: number;
  phone: string;            // synthetic, clearly fake e.g. "+91-00000-12345"
  elevation_m: number;
}

interface Route {
  method: RouteMethod;
  distance_m: number; duration_s: number;
  geometry: [number, number][];  // [lat, lon] pairs
}

interface EvacuationPlan {  // POST /api/evacuation/plan
  origin: { lat: number; lon: number };
  facility: Facility;
  route: Route;
  alternatives: { facility: Facility; route: Route }[];  // up to 2
  notes: string[];
}

interface PointRisk {       // GET /api/risk/point?lat=&lon=
  lat: number; lon: number;
  city: City; ward: Ward; distance_to_city_km: number;
  risk: RiskScore;
  advice: { now: string[]; prepare: string[]; avoid: string[] };   // deterministic, level-based
  evacuation: EvacuationPlan;
  emergency: { label: string; number: string }[];
  stale: boolean;
}

interface GeocodeResult { display_name: string; lat: number; lon: number }  // GET /api/geocode?q=
```

## Agents

```ts
interface AgentStep {
  id: string; run_id: string; seq: number;
  agent: AgentName; kind: StepKind;
  ts: string;
  content: string;          // reasoning text / summary shown in the timeline
  tool: string | null;      // tool name for tool_call / tool_result
  input: unknown | null;    // tool arguments / prompt summary
  output: unknown | null;   // tool result (trimmed)
  duration_ms: number;
}

interface AlertVersion { lang: Lang; sms: string; whatsapp: string }
// sms: <=160 chars for en (GSM-7); <=70 chars per segment for Unicode langs, max 2 segments (<=134 chars)

interface GuardResult { name: string; passed: boolean; detail: string }

interface Alert {
  id: string; run_id: string; city_id: string;
  level: RiskLevel;
  status: AlertStatus;
  created_at: string;
  target_wards: string[];   // ward ids
  versions: AlertVersion[]; // all five langs
  guards: GuardResult[];
  edited: boolean;
  reviewed_by: string | null; reviewed_at: string | null;
  dispatch_log: { ts: string; channel: "sms" | "whatsapp"; lang: Lang; recipients_estimate: number; simulated: true }[];
}

interface SitRep {
  run_id: string; city_id: string; generated_at: string;
  title: string;
  summary: string;
  sections: { heading: string; body: string }[];
  key_figures: { label: string; value: string }[];
}

interface AgentRun {
  id: string; city_id: string;
  trigger: "manual" | "scheduled" | "demo";
  started_at: string; finished_at: string | null;
  llm: { provider: string; model: string };   // e.g. {"provider":"ollama","model":"qwen2.5:3b"} or {"provider":"rules","model":"deterministic"}
  decision: { should_alert: boolean; level: RiskLevel; reason: string };
  steps: AgentStep[];
  alert_id: string | null;
  evacuation: EvacuationPlan[];  // plans from the top-risk wards' centroids
  sitrep: SitRep | null;
}
```

## Endpoints

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| GET | `/api/health` | – | `{status:"ok", version, llm:{provider, model, available:boolean}, demo:boolean}` |
| GET | `/api/cities` | – | `CitySummary[]` |
| GET | `/api/cities/{id}/risk` | – | `CityRisk` |
| GET | `/api/cities/{id}/facilities` | – | `Facility[]` |
| GET | `/api/risk/point` | `lat, lon` | `PointRisk` |
| GET | `/api/geocode` | `q` | `GeocodeResult[]` (Nominatim, cached, India only) |
| POST | `/api/evacuation/plan` | `{lat, lon, city_id?}` | `EvacuationPlan` |
| POST | `/api/agents/run` | `{city_id, trigger?}` | `AgentRun` |
| GET | `/api/agents/runs` | `city_id?` | `AgentRun[]` (newest first) |
| GET | `/api/agents/runs/{id}` | – | `AgentRun` |
| GET | `/api/timeline` | `limit?` | `AgentStep[]` (newest first, all runs) |
| GET | `/api/alerts` | `status?` | `Alert[]` |
| PUT | `/api/alerts/{id}` | `{versions: AlertVersion[], reviewer}` | `Alert` (re-runs guards, sets edited) |
| POST | `/api/alerts/{id}/approve` | `{reviewer}` | `Alert` (status → sent, simulated dispatch_log) — 409 if any guard failed |
| POST | `/api/alerts/{id}/reject` | `{reviewer, reason}` | `Alert` |
| GET | `/api/sitrep/{run_id}.pdf` | – | `application/pdf` |

**Safety gate:** nothing is "sent" except through `POST /approve` by a named human reviewer.
Agents can only *draft*. Dispatch is simulated (no SMS gateway) and logged.

## Demo scenario file — `frontend/public/demo/scenario.json`

```ts
interface DemoScenario {
  id: "assam-2026-replay";
  title: string; description: string;      // clearly says "synthetic replay inspired by Assam monsoon floods"
  recorded_with: { provider: string; model: string; recorded_at: string };
  frames: DemoFrame[];                       // 24 frames, 3h apart, covering a 72h flood build-up
  facilities: Record<string, Facility[]>;    // by city id
  agent_runs: { frame: number; run: AgentRun }[];   // runs recorded from the real agent pipeline
  alerts: Alert[];                           // alerts as drafted (status pending_approval)
  geocode: Record<string, GeocodeResult[]>;  // canned geocode answers for demo searches (lower-case query)
}
interface DemoFrame {
  index: number; t: string;
  caption: string;                           // narrative caption for the replay UI
  cities: CitySummary[];                     // all 12 cities
  details: Record<string, CityRisk>;         // all 12 cities
}
```
Demo mode (`VITE_DEMO=1` build, or `?demo=1`) implements the same client interface from this file;
POST endpoints are simulated in-browser (approve/reject/edit mutate local state, persisted in localStorage).
