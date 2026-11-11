/**
 * Client-side port of the backend's simple, deterministic alert guards.
 * Used by the demo client when a reviewer edits an alert (there is no backend to re-run them).
 * The authoritative guards run server-side in live mode.
 */
import type { AlertVersion, GuardResult, Lang } from '../api/schema';
import { isGsm7 } from './sms';

export const SMS_MAX_EN = 160;
export const SMS_MAX_UNICODE = 134; // 2 concatenated UCS-2 segments of 67
export const WHATSAPP_MAX = 1024;
export const LANG_NAMES: Record<Lang, string> = {
  en: 'English',
  hi: 'हिन्दी',
  mr: 'मराठी',
  ta: 'தமிழ்',
  bn: 'বাংলা',
};
export const ALL_LANGS: Lang[] = ['en', 'hi', 'mr', 'ta', 'bn'];

type Script = 'latin' | 'devanagari' | 'bengali' | 'tamil';
const SCRIPT_RANGES: Record<Script, [number, number]> = {
  latin: [0x0041, 0x024f],
  devanagari: [0x0900, 0x097f],
  bengali: [0x0980, 0x09ff],
  tamil: [0x0b80, 0x0bff],
};
const LANG_SCRIPT: Record<Lang, Script> = { en: 'latin', hi: 'devanagari', mr: 'devanagari', ta: 'tamil', bn: 'bengali' };
const MIN_SCRIPT_SHARE = 0.6;
const URL_RE = /(https?:\/\/|www\.|\b[\w-]+\.(com|in|org|net|ly|io|gov)\b)/i;
const NUM_RE = /\d+(?:[.,]\d+)*/g;

/**
 * Names mirror backend/jalrakshak/agents/guards.py. `numbers_verified` and `level_consistent`
 * need the server's verified fact sheet, so the demo keeps their recorded results.
 */
export const CLIENT_GUARD_NAMES = ['all_languages', 'sms_length', 'script', 'contains_112', 'no_urls'] as const;

function scriptOf(ch: string): Script | null {
  const cp = ch.codePointAt(0)!;
  for (const [name, [lo, hi]] of Object.entries(SCRIPT_RANGES) as [Script, [number, number]][]) if (cp >= lo && cp <= hi) return name;
  return null;
}

/** Share of letters (incl. combining marks) in `script`, and other Indic scripts present. */
export function scriptShare(text: string, script: Script): { share: number; others: Script[] } {
  const letters = [...text].filter((c) => /[\p{L}\p{M}]/u.test(c));
  if (!letters.length) return { share: 0, others: [] };
  const scripts = letters.map(scriptOf);
  const share = scripts.filter((s) => s === script).length / letters.length;
  const others = [...new Set(scripts.filter((s): s is Script => !!s && s !== script && s !== 'latin'))];
  return { share, others };
}

export function smsLimit(lang: Lang): number {
  return lang === 'en' ? SMS_MAX_EN : SMS_MAX_UNICODE;
}

/** Failures for one language version: {guardName: detail}. Empty object = all pass. */
export function checkVersion(v: AlertVersion): Record<string, string> {
  const fails: Record<string, string> = {};
  if (!v.sms.trim() || !v.whatsapp.trim()) fails.all_languages = `${v.lang}: empty text`;
  const limit = smsLimit(v.lang);
  if (v.sms.length > limit) fails.sms_length = `${v.lang}: SMS ${v.sms.length} > ${limit} chars`;
  else if (v.lang === 'en' && !isGsm7(v.sms)) fails.sms_length = 'en: non GSM-7 characters (would force Unicode)';
  if (v.whatsapp.length > WHATSAPP_MAX) fails.sms_length = `${v.lang}: WhatsApp ${v.whatsapp.length} > ${WHATSAPP_MAX} chars`;
  for (const [field, text] of [['sms', v.sms], ['whatsapp', v.whatsapp]] as const) {
    const { share, others } = scriptShare(text, LANG_SCRIPT[v.lang]);
    if (share < MIN_SCRIPT_SHARE || others.length) {
      fails.script = `${v.lang} ${field}: ${Math.round(share * 100)}% ${LANG_SCRIPT[v.lang]} letters${others.length ? `, foreign scripts ${others.join(', ')}` : ''}`;
    }
    if (!(text.match(NUM_RE) ?? ([] as string[])).includes('112')) fails.contains_112 = `${v.lang} ${field}: missing 112`;
    if (URL_RE.test(text)) fails.no_urls = `${v.lang} ${field}: contains a link`;
  }
  return fails;
}

const OK_DETAIL: Record<(typeof CLIENT_GUARD_NAMES)[number], string> = {
  all_languages: 'en, hi, mr, ta, bn present and non-empty',
  sms_length: 'SMS within 160 GSM-7 (en) / 134 Unicode chars',
  script: 'each version written in its own script',
  contains_112: '112 present in every message',
  no_urls: 'no links',
};

/** Aggregates per-language checks into one GuardResult per guard name (same order as the backend). */
export function runGuards(versions: AlertVersion[]): GuardResult[] {
  const failures: Record<string, string[]> = Object.fromEntries(CLIENT_GUARD_NAMES.map((g) => [g, []]));
  const present = new Set(versions.map((v) => v.lang));
  const missing = ALL_LANGS.filter((l) => !present.has(l));
  if (missing.length) failures.all_languages!.push(`missing languages ${missing.join(', ')}`);
  for (const v of versions) for (const [name, detail] of Object.entries(checkVersion(v))) failures[name]!.push(detail);
  return CLIENT_GUARD_NAMES.map((g) => ({ name: g, passed: failures[g]!.length === 0, detail: failures[g]!.length ? failures[g]!.join('; ') : OK_DETAIL[g] }));
}
