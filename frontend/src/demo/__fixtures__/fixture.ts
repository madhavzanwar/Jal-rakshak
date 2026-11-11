/**
 * Small hand-written DemoScenario fixture (2 cities, 4 frames, 1 agent run, 1 alert).
 * Used by unit tests and as a dev fallback until the backend generates public/demo/scenario.json.
 * Values are synthetic.
 */
import type {
  AgentRun,
  AgentStep,
  Alert,
  City,
  CityRisk,
  CitySummary,
  DemoFrame,
  DemoScenario,
  Facility,
  RiskScore,
} from '../../api/schema';
import { levelForScore } from '../../lib/levels';

const T0 = Date.parse('2026-07-01T00:00:00Z');
const iso = (ms: number) => new Date(ms).toISOString().replace('.000Z', 'Z');
const H = 3_600_000;

const EMERGENCY = [
  { label: 'Emergency (all services)', number: '112' },
  { label: 'NDMA helpline', number: '1078' },
  { label: 'Ambulance', number: '108' },
  { label: 'NDRF control room', number: '011-24363260' },
];

const guwahati: City = {
  id: 'guwahati',
  name: 'Guwahati',
  state: 'Assam',
  lat: 26.1445,
  lon: 91.7362,
  population: 1_260_000,
  wards: [
    { id: 'guwahati-w01', name: 'Anil Nagar', lat: 26.1676, lon: 91.7699, radius_m: 900, population: 48_000, elevation_m: 49, vulnerability: 0.86 },
    { id: 'guwahati-w02', name: 'Zoo Road', lat: 26.1702, lon: 91.7781, radius_m: 1000, population: 61_000, elevation_m: 52, vulnerability: 0.71 },
    { id: 'guwahati-w03', name: 'Pan Bazaar', lat: 26.1862, lon: 91.7467, radius_m: 800, population: 39_000, elevation_m: 55, vulnerability: 0.48 },
  ],
  gauges: [
    { id: 'guwahati-brahmaputra', river: 'Brahmaputra', lat: 26.19, lon: 91.74, warning_m3s: 28_000, danger_m3s: 36_000, extreme_m3s: 45_000 },
  ],
  emergency: [...EMERGENCY, { label: 'ASDMA control room', number: '1079' }],
};

const mumbai: City = {
  id: 'mumbai',
  name: 'Mumbai',
  state: 'Maharashtra',
  lat: 19.076,
  lon: 72.8777,
  population: 12_440_000,
  wards: [
    { id: 'mumbai-w01', name: 'Kurla', lat: 19.0726, lon: 72.8845, radius_m: 1200, population: 210_000, elevation_m: 6, vulnerability: 0.78 },
    { id: 'mumbai-w02', name: 'Andheri East', lat: 19.1136, lon: 72.8697, radius_m: 1400, population: 260_000, elevation_m: 12, vulnerability: 0.55 },
  ],
  gauges: [{ id: 'mumbai-mithi', river: 'Mithi', lat: 19.07, lon: 72.88, warning_m3s: 180, danger_m3s: 260, extreme_m3s: 340 }],
  emergency: [...EMERGENCY, { label: 'BMC disaster control', number: '1916' }],
};

function score(s: number, vulnerability: number, rain24: number, ratio: number): RiskScore {
  const level = levelForScore(s);
  return {
    score: Math.round(s * 10) / 10,
    level,
    factors: {
      rain_24h_mm: rain24,
      rain_72h_mm: Math.round(rain24 * 2.1),
      max_intensity_mmph: Math.round(rain24 / 6),
      antecedent_7d_mm: 140,
      discharge_ratio: ratio,
      vulnerability,
      components: {
        rain: Math.min(1, rain24 / 200),
        river: Math.min(1, ratio),
        antecedent: 0.6,
        vulnerability,
      },
    },
    explanation: `${level === 'red' ? 'Severe' : level === 'orange' ? 'High' : level === 'yellow' ? 'Moderate' : 'Low'} risk: ${rain24} mm forecast in 24 h and river at ${Math.round(ratio * 100)}% of danger level.`,
    ml_probability: Math.round((s / 110) * 100) / 100,
  };
}

function detail(city: City, frame: number, base: number): CityRisk {
  const t = T0 + frame * 3 * H;
  const overallScore = Math.min(97, base);
  const ratio = city.id === 'guwahati' ? 0.7 + frame * 0.12 : 0.4 + frame * 0.05;
  const rain24 = city.id === 'guwahati' ? 60 + frame * 35 : 30 + frame * 8;
  const wards = city.wards.map((w) => ({ ward_id: w.id, risk: score(Math.max(5, overallScore - (1 - w.vulnerability) * 30), w.vulnerability, rain24, ratio) }));
  const overall = wards.reduce((m, w) => (w.risk.score > m.score ? w.risk : m), wards[0]!.risk);
  const series = Array.from({ length: 14 }, (_, d) => {
    const g = city.gauges[0]!;
    const shape = Math.sin(((d + frame * 0.4) / 14) * Math.PI);
    return { date: new Date(T0 + (d - 7) * 24 * H).toISOString().slice(0, 10), m3s: Math.round(g.warning_m3s * (0.55 + shape * ratio * 0.75)) };
  });
  const g = city.gauges[0]!;
  const future = series.slice(7, 10);
  const peak = future.reduce((m, p) => (p.m3s > m.m3s ? p : m), future[0]!);
  const current = series[7]!.m3s;
  const status = peak.m3s >= g.extreme_m3s ? 'extreme' : peak.m3s >= g.danger_m3s ? 'danger' : peak.m3s >= g.warning_m3s ? 'warning' : 'normal';
  return {
    city,
    generated_at: iso(t),
    stale: city.id === 'mumbai' && frame === 1,
    data_age_minutes: city.id === 'mumbai' && frame === 1 ? 95 : 4,
    sources: [
      { name: 'Open-Meteo Forecast (ECMWF/ICON)', url: 'https://api.open-meteo.com/v1/forecast', ok: true, fetched_at: iso(t) },
      { name: 'Open-Meteo Flood (GloFAS v4)', url: 'https://flood-api.open-meteo.com/v1/flood', ok: !(city.id === 'mumbai' && frame === 1), fetched_at: iso(t - (city.id === 'mumbai' && frame === 1 ? 95 : 4) * 60_000) },
    ],
    overall,
    horizon: Array.from({ length: 24 }, (_, i) => {
      const s = Math.max(4, Math.min(99, overallScore * (0.75 + 0.35 * Math.sin((i / 23) * Math.PI))));
      return { t: iso(t + i * 3 * H), score: Math.round(s * 10) / 10, level: levelForScore(s) };
    }),
    rainfall: Array.from({ length: 72 }, (_, i) => ({ t: iso(t + i * H), mm: Math.round(Math.max(0, (rain24 / 14) * Math.sin((i / 71) * Math.PI * 2.5) ** 2) * 10) / 10 })),
    gauges: [{ gauge: g, series, current_m3s: current, peak_m3s: peak.m3s, peak_date: peak.date, status }],
    wards,
  };
}

const BASES: Record<string, number[]> = { guwahati: [41, 58, 77, 86], mumbai: [22, 28, 33, 31] };

function frame(i: number): DemoFrame {
  const details: Record<string, CityRisk> = {};
  const cities: CitySummary[] = [];
  for (const c of [guwahati, mumbai]) {
    const d = detail(c, i, BASES[c.id]![i]!);
    details[c.id] = d;
    const peak = d.horizon.reduce((m, p) => (p.score > m.score ? p : m), d.horizon[0]!);
    cities.push({ city: c, risk: d.overall, peak_time: peak.t, stale: d.stale, updated_at: d.generated_at });
  }
  const captions = [
    'Day 1, 05:30 IST — monsoon trough strengthens over the north-east.',
    'Day 1, 08:30 IST — heavy rain begins over Kamrup Metro; Brahmaputra rising.',
    'Day 1, 11:30 IST — Brahmaputra crosses warning level at Guwahati.',
    'Day 1, 14:30 IST — severe flood risk in low-lying wards of Guwahati.',
  ];
  return { index: i, t: iso(T0 + i * 3 * H), caption: captions[i]!, cities, details };
}

const facilities: Record<string, Facility[]> = {
  guwahati: [
    { id: 'guwahati-f01', city_id: 'guwahati', ward_id: 'guwahati-w03', name: 'Govt. HS School Relief Shelter, Pan Bazaar', type: 'shelter', lat: 26.1851, lon: 91.7483, capacity: 800, occupancy: 120, phone: '+91-00000-11111', elevation_m: 58 },
    { id: 'guwahati-f02', city_id: 'guwahati', ward_id: 'guwahati-w02', name: 'GMCH (Gauhati Medical College)', type: 'hospital', lat: 26.1563, lon: 91.7688, capacity: 1200, occupancy: 870, phone: '+91-00000-22222', elevation_m: 61 },
    { id: 'guwahati-f03', city_id: 'guwahati', ward_id: 'guwahati-w02', name: 'Relief Camp, Zoo Road Community Hall', type: 'relief_camp', lat: 26.1744, lon: 91.7812, capacity: 450, occupancy: 40, phone: '+91-00000-33333', elevation_m: 57 },
  ],
  mumbai: [
    { id: 'mumbai-f01', city_id: 'mumbai', ward_id: 'mumbai-w02', name: 'Municipal School Shelter, Andheri East', type: 'shelter', lat: 19.1151, lon: 72.8721, capacity: 1000, occupancy: 90, phone: '+91-00000-44444', elevation_m: 18 },
  ],
};

const RUN_ID = 'run-fixture-guwahati-01';
const RUN_T = T0 + 6 * H;
let seq = 0;
function step(agent: AgentStep['agent'], kind: AgentStep['kind'], content: string, extra: Partial<AgentStep> = {}): AgentStep {
  seq += 1;
  return {
    id: `${RUN_ID}-s${String(seq).padStart(2, '0')}`,
    run_id: RUN_ID,
    seq,
    agent,
    kind,
    ts: iso(RUN_T + seq * 1500),
    content,
    tool: null,
    input: null,
    output: null,
    duration_ms: 300 + seq * 37,
    ...extra,
  };
}

const ALERT_ID = 'alert-fixture-guwahati-01';
const steps: AgentStep[] = [
  step('monitor', 'tool_call', 'Fetching current risk for Guwahati.', { tool: 'get_city_risk', input: { city_id: 'guwahati' } }),
  step('monitor', 'tool_result', 'Overall risk 77.0 (red); Brahmaputra peak 39,800 m³/s vs danger 36,000.', { tool: 'get_city_risk', output: { score: 77, level: 'red', discharge_ratio: 1.1 } }),
  step('monitor', 'decision', 'Risk is red and rising; alert required for 2 low-lying wards.', { output: { should_alert: true, level: 'red' } }),
  step('alert_drafter', 'thought', 'Drafting a concise SMS in 5 languages that names the wards, the action and 112.'),
  step('alert_drafter', 'tool_call', 'Calling LLM to draft multilingual alert.', { tool: 'llm.generate', input: { langs: ['en', 'hi', 'mr', 'ta', 'bn'], max_sms_chars: 160 } }),
  step('alert_drafter', 'guard', 'All guards passed (length, 112, script).', { output: { passed: 5, failed: 0 } }),
  step('alert_drafter', 'final', `Alert ${ALERT_ID} drafted and queued for human approval.`, { output: { alert_id: ALERT_ID } }),
  step('evacuation_planner', 'tool_call', 'Planning routes from Anil Nagar and Zoo Road to the nearest shelters.', { tool: 'plan_evacuation', input: { wards: ['guwahati-w01', 'guwahati-w02'] } }),
  step('evacuation_planner', 'final', '2 evacuation plans ready (OSRM foot routing).'),
  step('sitrep', 'final', 'Situation report generated.'),
];

const plan = {
  origin: { lat: 26.1676, lon: 91.7699 },
  facility: facilities.guwahati![0]!,
  route: { method: 'osrm' as const, distance_m: 2900, duration_s: 2300, geometry: [[26.1676, 91.7699], [26.172, 91.76], [26.18, 91.752], [26.1851, 91.7483]] as [number, number][] },
  alternatives: [{ facility: facilities.guwahati![2]!, route: { method: 'straight_line' as const, distance_m: 1400, duration_s: 1100, geometry: [[26.1676, 91.7699], [26.1744, 91.7812]] as [number, number][] } }],
  notes: ['Avoid GS Road underpass (waterlogging).'],
};

const run: AgentRun = {
  id: RUN_ID,
  city_id: 'guwahati',
  trigger: 'demo',
  started_at: iso(RUN_T),
  finished_at: iso(RUN_T + 20_000),
  llm: { provider: 'ollama', model: 'qwen2.5:3b' },
  decision: { should_alert: true, level: 'red', reason: 'Overall score 77 (red) with Brahmaputra above danger level.' },
  steps,
  alert_id: ALERT_ID,
  evacuation: [plan],
  sitrep: {
    run_id: RUN_ID,
    city_id: 'guwahati',
    generated_at: iso(RUN_T + 20_000),
    title: 'Situation Report — Guwahati flood risk',
    summary: 'Severe flood risk in low-lying wards of Guwahati over the next 24–48 hours.',
    sections: [
      { heading: 'Hazard', body: 'Brahmaputra forecast to exceed danger level; 140 mm rain in 24 h.' },
      { heading: 'Actions', body: 'Alert drafted for Anil Nagar and Zoo Road; shelters identified.' },
    ],
    key_figures: [
      { label: 'Overall risk', value: '77 / 100 (red)' },
      { label: 'People in target wards', value: '1.09 lakh' },
    ],
  },
};

const alert: Alert = {
  id: ALERT_ID,
  run_id: RUN_ID,
  city_id: 'guwahati',
  level: 'red',
  status: 'pending_approval',
  created_at: iso(RUN_T + 9000),
  target_wards: ['guwahati-w01', 'guwahati-w02'],
  versions: [
    { lang: 'en', sms: 'FLOOD ALERT Guwahati: Severe flood risk in Anil Nagar, Zoo Road next 24h. Move to higher ground/shelter now. Emergency: call 112. -ASDMA', whatsapp: '*Flood alert — Guwahati*\nSevere flood risk in Anil Nagar and Zoo Road in the next 24 hours.\nMove to the nearest shelter or higher ground. Emergency: 112.' },
    { lang: 'hi', sms: 'बाढ़ चेतावनी गुवाहाटी: अनिल नगर, ज़ू रोड में गंभीर खतरा। ऊँचे स्थान/आश्रय में जाएँ। आपात: 112', whatsapp: '*बाढ़ चेतावनी — गुवाहाटी*\nअनिल नगर और ज़ू रोड में अगले 24 घंटे गंभीर बाढ़ का खतरा। आपात स्थिति में 112 पर कॉल करें।' },
    { lang: 'mr', sms: 'पूर इशारा गुवाहाटी: अनिल नगर, झू रोड येथे गंभीर धोका. उंच ठिकाणी जा. आपत्कालीन: 112', whatsapp: '*पूर इशारा — गुवाहाटी*\nअनिल नगर आणि झू रोड येथे पुढील 24 तासांत गंभीर धोका. आपत्कालीन: 112.' },
    { lang: 'ta', sms: 'வெள்ள எச்சரிக்கை குவஹாத்தி: உயரமான இடத்திற்கு செல்லவும். அவசரம்: 112', whatsapp: '*வெள்ள எச்சரிக்கை — குவஹாத்தி*\nஅனில் நகர், ஜூ ரோடு பகுதிகளில் கடும் ஆபத்து. அவசரம்: 112.' },
    { lang: 'bn', sms: 'বন্যা সতর্কতা গুয়াহাটি: অনিল নগর, জু রোডে গুরুতর ঝুঁকি। উঁচু স্থানে যান। জরুরি: 112', whatsapp: '*বন্যা সতর্কতা — গুয়াহাটি*\nঅনিল নগর ও জু রোডে আগামী ২৪ ঘণ্টা গুরুতর ঝুঁকি। জরুরি: 112।' },
  ],
  guards: [
    { name: 'sms_length', passed: true, detail: 'all languages pass' },
    { name: 'contains_112', passed: true, detail: 'all languages pass' },
    { name: 'script_check', passed: true, detail: 'all languages pass' },
  ],
  edited: false,
  reviewed_by: null,
  reviewed_at: null,
  dispatch_log: [],
};

export const fixtureScenario: DemoScenario = {
  id: 'assam-2026-replay',
  title: 'Assam monsoon flood replay (fixture)',
  description: 'DEMO · synthetic replay inspired by Assam monsoon floods (small test fixture).',
  recorded_with: { provider: 'ollama', model: 'qwen2.5:3b', recorded_at: '2026-07-01T06:00:00Z' },
  frames: [0, 1, 2, 3].map(frame),
  facilities,
  agent_runs: [{ frame: 2, run }],
  alerts: [alert],
  geocode: { 'anil nagar': [{ display_name: 'Anil Nagar, Guwahati, Assam, India', lat: 26.1676, lon: 91.7699 }] },
};

export default fixtureScenario;
