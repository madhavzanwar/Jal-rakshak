import { describe, expect, it } from 'vitest';
import { AlertSchema, CityRiskSchema, DemoScenarioSchema, RiskScoreSchema } from '../api/schema';
import { fixtureScenario } from '../demo/__fixtures__/fixture';

describe('contract schemas', () => {
  it('parses the hand-written demo fixture', () => {
    const parsed = DemoScenarioSchema.parse(JSON.parse(JSON.stringify(fixtureScenario)));
    expect(parsed.frames).toHaveLength(4);
    expect(parsed.frames[0]!.cities).toHaveLength(2);
    expect(parsed.agent_runs[0]!.run.steps.length).toBeGreaterThan(5);
  });

  it('parses a CityRisk with 24 horizon points and 72 rainfall points', () => {
    const d = fixtureScenario.frames[2]!.details.guwahati!;
    const parsed = CityRiskSchema.parse(d);
    expect(parsed.horizon).toHaveLength(24);
    expect(parsed.rainfall).toHaveLength(72);
  });

  it('rejects an unknown risk level', () => {
    const bad = { ...fixtureScenario.frames[0]!.cities[0]!.risk, level: 'purple' };
    expect(RiskScoreSchema.safeParse(bad).success).toBe(false);
  });

  it('rejects a dispatch entry that is not marked simulated', () => {
    const a = structuredClone(fixtureScenario.alerts[0]!);
    const bad = { ...a, dispatch_log: [{ ts: '2026-07-01T00:00:00Z', channel: 'sms', lang: 'en', recipients_estimate: 10, simulated: false }] };
    expect(AlertSchema.safeParse(bad).success).toBe(false);
  });

  it('requires nullable fields to be present (not undefined)', () => {
    const { ml_probability: _omit, ...rest } = fixtureScenario.frames[0]!.cities[0]!.risk;
    expect(RiskScoreSchema.safeParse(rest).success).toBe(false);
  });
});
