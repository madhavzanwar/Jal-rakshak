/**
 * Validates the backend-generated demo scenario (public/demo/scenario.json) against the
 * frontend's zod contract, if the file exists. A failure here means the generator drifted
 * from docs/CONTRACT.md.
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { DemoScenarioSchema } from '../api/schema';
import { DemoClient } from '../api/demo';

const file = resolve(__dirname, '../../public/demo/scenario.json');
const present = existsSync(file);

describe.skipIf(!present)('public/demo/scenario.json', () => {
  const json: unknown = present ? JSON.parse(readFileSync(file, 'utf8')) : null;

  it('matches the DemoScenario contract', () => {
    const r = DemoScenarioSchema.safeParse(json);
    if (!r.success) {
      const issues = r.error.issues.slice(0, 20).map((i) => `${i.path.join('.')}: ${i.message}`);
      throw new Error(`scenario.json contract mismatch:\n${issues.join('\n')}`);
    }
    expect(r.success).toBe(true);
  });

  it('has 24 frames of 12 cities with details for each city', () => {
    const s = DemoScenarioSchema.parse(json);
    expect(s.id).toBe('assam-2026-replay');
    expect(s.frames).toHaveLength(24);
    for (const f of s.frames) {
      expect(f.cities).toHaveLength(12);
      for (const c of f.cities) expect(f.details[c.city.id]).toBeDefined();
    }
    expect(s.description.toLowerCase()).toContain('synthetic replay');
  });

  it('has a recorded Guwahati run whose alert is in the alerts list', async () => {
    const s = DemoScenarioSchema.parse(json);
    const g = s.agent_runs.find((r) => r.run.city_id === 'guwahati');
    expect(g).toBeDefined();
    expect(g!.run.alert_id).toBeTruthy();
    expect(s.alerts.some((a) => a.id === g!.run.alert_id && a.status === 'pending_approval')).toBe(true);
    const client = new DemoClient(s, { storage: null });
    const res = await client.runAgents('guwahati');
    expect(res.run.steps.some((st) => st.agent === 'alert_drafter')).toBe(true);
  });
});
