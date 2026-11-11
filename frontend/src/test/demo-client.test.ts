import { describe, expect, it, vi } from 'vitest';
import { DemoClient, type KeyValueStore } from '../api/demo';
import { ApiError } from '../api/errors';
import { fixtureScenario } from '../demo/__fixtures__/fixture';

function memoryStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: (k) => void data.delete(k) };
}
const make = (storage: KeyValueStore | null = memoryStore()) => new DemoClient(structuredClone(fixtureScenario), { storage });

describe('DemoClient replay', () => {
  it('serves the current frame and advances', async () => {
    const c = make();
    const listener = vi.fn();
    c.subscribe(listener);
    expect(c.frameIndex).toBe(0);
    const before = (await c.cities()).find((x) => x.city.id === 'guwahati')!.risk.score;
    c.nextFrame();
    expect(c.frameIndex).toBe(1);
    expect(listener).toHaveBeenCalledTimes(1);
    const after = (await c.cities()).find((x) => x.city.id === 'guwahati')!.risk.score;
    expect(after).toBeGreaterThan(before);
    c.setFrame(99);
    expect(c.frameIndex).toBe(3);
    c.nextFrame();
    expect(c.frameIndex).toBe(3);
    c.nextFrame(true);
    expect(c.frameIndex).toBe(0);
  });

  it('returns 404 for a city without detail', async () => {
    await expect(make().cityRisk('atlantis')).rejects.toBeInstanceOf(ApiError);
  });

  it('hides runs and alerts recorded at later frames until reached or triggered', async () => {
    const c = make();
    expect(await c.runs()).toHaveLength(0);
    expect(await c.alerts()).toHaveLength(0);
    c.setFrame(2);
    expect(await c.runs()).toHaveLength(1);
    expect(await c.alerts()).toHaveLength(1);
  });

  it('runAgents jumps the replay to the recorded frame', async () => {
    const c = make();
    const res = await c.runAgents('guwahati');
    expect(res.run.city_id).toBe('guwahati');
    expect(res.jumpedToFrame).toBe(2);
    expect(c.frameIndex).toBe(2);
    expect(res.note).toMatch(/jumped to frame 3/);
    c.setFrame(0);
    expect(await c.alerts()).toHaveLength(1); // stays visible once triggered
  });

  it('runAgents does not jump when already past the recorded frame', async () => {
    const c = make();
    c.setFrame(3);
    const res = await c.runAgents('guwahati');
    expect(res.jumpedToFrame).toBeUndefined();
    expect(c.frameIndex).toBe(3);
  });

  it('runAgents errors for a city with no recorded run', async () => {
    await expect(make().runAgents('mumbai')).rejects.toThrow(/No recorded agent run/);
  });
});

describe('DemoClient alert workflow', () => {
  it('approve requires a reviewer, then marks the alert sent with a simulated dispatch log', async () => {
    const store = memoryStore();
    const c = make(store);
    const { run } = await c.runAgents('guwahati');
    await expect(c.approveAlert(run.alert_id!, '  ')).rejects.toThrow(/Reviewer/);
    const sent = await c.approveAlert(run.alert_id!, 'Priya Sharma');
    expect(sent.status).toBe('sent');
    expect(sent.reviewed_by).toBe('Priya Sharma');
    expect(sent.dispatch_log.length).toBe(10); // 5 langs × (sms + whatsapp)
    expect(sent.dispatch_log.every((d) => d.simulated)).toBe(true);
    expect((await c.alerts('sent')).map((a) => a.id)).toEqual([run.alert_id]);
    await expect(c.approveAlert(run.alert_id!, 'Priya Sharma')).rejects.toMatchObject({ status: 409 });

    // persisted: a fresh client with the same storage sees the sent status
    const c2 = make(store);
    expect((await c2.alerts())[0]!.status).toBe('sent');
    c2.reset();
    expect(store.data.size).toBe(0);
  });

  it('reject records reviewer and reason', async () => {
    const c = make();
    const { run } = await c.runAgents('guwahati');
    const r = await c.rejectAlert(run.alert_id!, 'Officer', 'wrong wards');
    expect(r.status).toBe('rejected');
    expect(r.guards.some((g) => g.detail === 'wrong wards')).toBe(true);
  });

  it('editing re-runs guards; a failing guard blocks approval', async () => {
    const c = make();
    const { run } = await c.runAgents('guwahati');
    const alert = (await c.alerts())[0]!;
    const versions = alert.versions.map((v) => (v.lang === 'en' ? { ...v, sms: 'Flood warning. Move to higher ground.' } : v));
    const edited = await c.updateAlert(alert.id, versions, 'Officer');
    expect(edited.edited).toBe(true);
    expect(edited.guards.find((g) => g.name === 'contains_112')!.passed).toBe(false);
    await expect(c.approveAlert(run.alert_id!, 'Officer')).rejects.toMatchObject({ status: 409 });
  });

  it('pointRisk finds the nearest ward and a shelter', async () => {
    const c = make();
    c.setFrame(3);
    const p = await c.pointRisk(26.1676, 91.7699);
    expect(p.ward.id).toBe('guwahati-w01');
    expect(p.risk.level).toBe('red');
    expect(p.advice.now.length).toBeGreaterThan(0);
    expect(p.evacuation.facility.type).not.toBe('hospital');
    expect(p.emergency.some((e) => e.number === '112')).toBe(true);
  });

  it('geocode uses canned answers, then falls back to ward names', async () => {
    const c = make();
    expect((await c.geocode('Anil Nagar'))[0]!.display_name).toMatch(/Anil Nagar/);
    expect((await c.geocode('kurla'))[0]!.display_name).toMatch(/Kurla, Mumbai/);
    expect(await c.geocode('   ')).toEqual([]);
  });
});
