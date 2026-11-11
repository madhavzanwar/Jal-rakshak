import { describe, expect, it } from 'vitest';
import type { AlertVersion } from '../api/schema';
import { runGuards } from '../lib/guards';
import { fixtureScenario } from '../demo/__fixtures__/fixture';

const good = (): AlertVersion[] => structuredClone(fixtureScenario.alerts[0]!.versions);
const guard = (versions: AlertVersion[], name: string) => runGuards(versions).find((g) => g.name === name)!;

describe('guard port', () => {
  it('passes the fixture alert', () => {
    expect(runGuards(good()).every((g) => g.passed)).toBe(true);
  });

  it('rejects an English SMS over 160 characters', () => {
    const v = good();
    v[0] = { ...v[0]!, sms: `Call 112. ${'x'.repeat(160)}` };
    const g = guard(v, 'sms_length');
    expect(g.passed).toBe(false);
    expect(g.detail).toMatch(/en: \d+\/160/);
  });

  it('rejects a Unicode SMS over 134 characters', () => {
    const v = good();
    v[1] = { ...v[1]!, sms: `112 ${'बाढ़'.repeat(40)}` };
    expect(guard(v, 'sms_length').passed).toBe(false);
  });

  it('rejects an SMS missing 112', () => {
    const v = good();
    v[2] = { ...v[2]!, sms: 'पूर इशारा: उंच ठिकाणी जा.' };
    const g = guard(v, 'contains_112');
    expect(g.passed).toBe(false);
    expect(g.detail).toMatch(/mr: SMS missing 112/);
  });

  it('does not accept 1120 as 112', () => {
    const v = good();
    v[0] = { ...v[0]!, sms: 'Flood alert. Call 1120 now.' };
    expect(guard(v, 'contains_112').passed).toBe(false);
  });

  it('rejects a Tamil version written in Latin script', () => {
    const v = good();
    v[3] = { ...v[3]!, sms: 'Vellam echcharikkai. Call 112', whatsapp: 'Vellam. 112' };
    expect(guard(v, 'script_check').passed).toBe(false);
  });

  it('flags missing languages', () => {
    expect(guard(good().slice(0, 3), 'all_languages_present').detail).toBe('missing: ta, bn');
  });
});
