import type { Lang } from '../api/schema';
import { smsLimit } from '../lib/guards';
import { smsInfo } from '../lib/sms';

export function SmsCounter({ text, lang }: { text: string; lang: Lang }) {
  const info = smsInfo(text);
  const limit = smsLimit(lang);
  const over = lang === 'en' ? info.encoding !== 'GSM-7' || info.units > limit : info.units > limit;
  return (
    <span data-testid="sms-counter" className={`font-mono text-[11px] tabular-nums ${over ? 'text-red-300' : 'text-slate-400'}`} aria-live="polite">
      {info.units}/{limit} · {info.segments} segment{info.segments === 1 ? '' : 's'} · {info.encoding}
      {over && ' · over limit'}
    </span>
  );
}

