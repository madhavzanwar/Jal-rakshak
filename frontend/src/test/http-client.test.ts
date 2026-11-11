import { describe, expect, it, vi } from 'vitest';
import { HttpClient } from '../api/http';
import { fixtureScenario } from '../demo/__fixtures__/fixture';

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });

describe('HttpClient', () => {
  it('parses responses with zod', async () => {
    const f = vi.fn(async () => ok(fixtureScenario.frames[0]!.cities));
    const c = new HttpClient('/api', f as unknown as typeof fetch);
    const cities = await c.cities();
    expect(cities).toHaveLength(2);
    expect(f).toHaveBeenCalledWith('/api/cities', expect.anything());
  });

  it('reports contract mismatches loudly', async () => {
    const bad = structuredClone(fixtureScenario.frames[0]!.cities);
    (bad[0] as { risk: { level: string } }).risk.level = 'purple';
    const c = new HttpClient('/api', (async () => ok(bad)) as unknown as typeof fetch);
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await expect(c.cities()).rejects.toThrow(/Contract mismatch for \/cities/);
  });

  it('surfaces FastAPI error detail and status (e.g. 409 guard failure)', async () => {
    const c = new HttpClient('/api', (async () => new Response(JSON.stringify({ detail: 'guards failed' }), { status: 409 })) as unknown as typeof fetch);
    await expect(c.approveAlert('a1', 'Officer')).rejects.toMatchObject({ status: 409, message: 'guards failed' });
  });

  it('builds the SitRep PDF URL', () => {
    expect(new HttpClient().sitrepPdfUrl('run 1')).toBe('/api/sitrep/run%201.pdf');
  });
});
