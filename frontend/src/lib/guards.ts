/**
 * Client-side port of the backend's simple, deterministic alert guards.
 * Used by the demo client when a reviewer edits an alert (there is no backend to re-run them).
 * The authoritative guards run server-side in live mode.
 */
import type { AlertVersion, GuardResult, Lang } from '../api/schema';
import { isGsm7, smsInfo } from './sms';

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

const SCRIPT_RE: Record<Exclude<Lang, 'en'>, RegExp> = {
  hi: /[ऀ-ॿ]/,
  mr: /[ऀ-ॿ]/,
  ta: /[஀-௿]/,
  bn: /[ঀ-৿]/,
};

/** Names of the guards this module computes (other server guards are preserved as recorded). */
export const CLIENT_GUARD_NAMES = ['all_languages_present', 'sms_length', 'whatsapp_length', 'contains_112', 'script_check'] as const;

export function smsLimit(lang: Lang): number {
  return lang === 'en' ? SMS_MAX_EN : SMS_MAX_UNICODE;
}

export function checkVersion(v: AlertVersion): { name: string; ok: boolean; detail: string }[] {
  const out: { name: string; ok: boolean; detail: string }[] = [];
  const len = v.sms.length;
  const limit = smsLimit(v.lang);
  const lengthOk = v.lang === 'en' ? isGsm7(v.sms) && smsInfo(v.sms).units <= SMS_MAX_EN : len <= SMS_MAX_UNICODE;
  out.push({
    name: 'sms_length',
    ok: lengthOk && len > 0,
    detail: len === 0 ? `${v.lang}: SMS is empty` : `${v.lang}: ${len}/${limit} chars${v.lang === 'en' && !isGsm7(v.sms) ? ' (non GSM-7 characters)' : ''}`,
  });
  out.push({
    name: 'whatsapp_length',
    ok: v.whatsapp.length > 0 && v.whatsapp.length <= WHATSAPP_MAX,
    detail: `${v.lang}: ${v.whatsapp.length}/${WHATSAPP_MAX} chars`,
  });
  const has112 = /(^|\D)112(\D|$)/;
  out.push({
    name: 'contains_112',
    ok: has112.test(v.sms) && has112.test(v.whatsapp),
    detail: `${v.lang}: ${has112.test(v.sms) ? 'SMS ✓' : 'SMS missing 112'}, ${has112.test(v.whatsapp) ? 'WhatsApp ✓' : 'WhatsApp missing 112'}`,
  });
  if (v.lang !== 'en') {
    const re = SCRIPT_RE[v.lang];
    const ok = re.test(v.sms) && re.test(v.whatsapp);
    out.push({ name: 'script_check', ok, detail: `${v.lang}: ${ok ? 'native script present' : 'expected native script not found'}` });
  } else {
    out.push({ name: 'script_check', ok: true, detail: 'en: Latin script' });
  }
  return out;
}

/** Aggregates per-language checks into one GuardResult per guard name. */
export function runGuards(versions: AlertVersion[]): GuardResult[] {
  const present = new Set(versions.map((v) => v.lang));
  const missing = ALL_LANGS.filter((l) => !present.has(l));
  const results: GuardResult[] = [
    {
      name: 'all_languages_present',
      passed: missing.length === 0,
      detail: missing.length === 0 ? 'en, hi, mr, ta, bn present' : `missing: ${missing.join(', ')}`,
    },
  ];
  const byName = new Map<string, { ok: boolean; details: string[] }>();
  for (const v of versions) {
    for (const c of checkVersion(v)) {
      const agg = byName.get(c.name) ?? { ok: true, details: [] };
      agg.ok = agg.ok && c.ok;
      if (!c.ok) agg.details.push(c.detail);
      byName.set(c.name, agg);
    }
  }
  for (const [name, agg] of byName) {
    results.push({ name, passed: agg.ok, detail: agg.ok ? 'all languages pass' : agg.details.join('; ') });
  }
  return results;
}
