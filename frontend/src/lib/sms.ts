/**
 * SMS segment arithmetic.
 * GSM-7: 160 chars single / 153 per segment when concatenated; extension chars count double.
 * UCS-2 (any non-GSM char, e.g. Devanagari/Tamil/Bengali): 70 single / 67 per segment, counted in UTF-16 units.
 */
const GSM_BASIC =
  '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';
const GSM_EXT = '^{}\\[~]|€\f';
const BASIC = new Set(GSM_BASIC);
const EXT = new Set(GSM_EXT);

export type SmsEncoding = 'GSM-7' | 'UCS-2';

export interface SmsInfo {
  encoding: SmsEncoding;
  /** Units used (septets for GSM-7, UTF-16 code units for UCS-2). */
  units: number;
  segments: number;
  /** Units per segment for the current segment count. */
  perSegment: number;
  /** Units remaining in the current segment. */
  remaining: number;
}

export function isGsm7(text: string): boolean {
  for (const ch of text) if (!BASIC.has(ch) && !EXT.has(ch)) return false;
  return true;
}

export function smsInfo(text: string): SmsInfo {
  if (isGsm7(text)) {
    let units = 0;
    for (const ch of text) units += EXT.has(ch) ? 2 : 1;
    const segments = units === 0 ? 0 : units <= 160 ? 1 : Math.ceil(units / 153);
    const perSegment = segments <= 1 ? 160 : 153;
    const remaining = segments === 0 ? 160 : segments * perSegment - units;
    return { encoding: 'GSM-7', units, segments, perSegment, remaining };
  }
  const units = text.length; // UTF-16 code units
  const segments = units === 0 ? 0 : units <= 70 ? 1 : Math.ceil(units / 67);
  const perSegment = segments <= 1 ? 70 : 67;
  const remaining = segments === 0 ? 70 : segments * perSegment - units;
  return { encoding: 'UCS-2', units, segments, perSegment, remaining };
}
