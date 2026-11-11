import { describe, expect, it } from 'vitest';
import { LEVEL_COLORS, levelColor, levelForScore } from '../lib/levels';
import { isGsm7, smsInfo } from '../lib/sms';

describe('level colour mapping', () => {
  it('uses the contract cut-offs', () => {
    expect(levelForScore(0)).toBe('green');
    expect(levelForScore(29.99)).toBe('green');
    expect(levelForScore(30)).toBe('yellow');
    expect(levelForScore(54.99)).toBe('yellow');
    expect(levelForScore(55)).toBe('orange');
    expect(levelForScore(74.99)).toBe('orange');
    expect(levelForScore(75)).toBe('red');
    expect(levelForScore(100)).toBe('red');
  });
  it('maps levels to the brand tokens', () => {
    expect(levelColor('green')).toBe('#16a34a');
    expect(levelColor('yellow')).toBe('#eab308');
    expect(levelColor('orange')).toBe('#f97316');
    expect(levelColor('red')).toBe('#dc2626');
    expect(Object.keys(LEVEL_COLORS)).toHaveLength(4);
  });
});

describe('SMS segment counter', () => {
  it('counts GSM-7 single and concatenated segments', () => {
    expect(smsInfo('')).toMatchObject({ segments: 0, units: 0 });
    expect(smsInfo('a'.repeat(160))).toMatchObject({ encoding: 'GSM-7', segments: 1, remaining: 0 });
    expect(smsInfo('a'.repeat(161))).toMatchObject({ segments: 2, perSegment: 153 });
    expect(smsInfo('a'.repeat(306))).toMatchObject({ segments: 2, remaining: 0 });
    expect(smsInfo('a'.repeat(307)).segments).toBe(3);
  });
  it('counts GSM-7 extension characters twice', () => {
    expect(smsInfo('€[]').units).toBe(6);
    expect(isGsm7('Call 112 — now')).toBe(false); // em dash forces UCS-2
  });
  it('switches to UCS-2 for Indic scripts', () => {
    const hi = 'बाढ़'.repeat(10);
    expect(smsInfo(hi)).toMatchObject({ encoding: 'UCS-2', units: 40, segments: 1, perSegment: 70 });
    expect(smsInfo('অ'.repeat(71))).toMatchObject({ segments: 2, perSegment: 67 });
    expect(smsInfo('அ'.repeat(134)).segments).toBe(2);
    expect(smsInfo('அ'.repeat(135)).segments).toBe(3);
  });
});
