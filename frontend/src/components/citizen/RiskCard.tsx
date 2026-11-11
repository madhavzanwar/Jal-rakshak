import { AlertTriangle } from 'lucide-react';
import type { PointRisk } from '../../api/schema';
import { DICT, type UiLang } from '../../lib/i18n';
import { LEVEL_COLORS, LEVEL_ON_COLORS } from '../../lib/levels';

/** Personalised risk card for the citizen view (large type, level colour band). */
export function RiskCard({ data, lang }: { data: PointRisk; lang: UiLang }) {
  const t = DICT[lang];
  const { risk } = data;
  const color = LEVEL_COLORS[risk.level];
  const on = LEVEL_ON_COLORS[risk.level];
  return (
    <section aria-label={t.score} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" data-testid="citizen-risk-card" data-level={risk.level}>
      <div className="flex items-center justify-between gap-3 px-5 py-4" style={{ background: color, color: on }}>
        <div>
          <p className="text-sm font-semibold opacity-90">
            {t.riskFor} {data.ward.name}, {data.city.name}
          </p>
          <p className="text-2xl font-extrabold leading-tight" data-testid="citizen-level">
            {t.level[risk.level]}
          </p>
        </div>
        <div className="text-right">
          <p className="font-mono text-4xl font-black leading-none" data-testid="citizen-score">
            {Math.round(risk.score)}
          </p>
          <p className="text-xs font-semibold opacity-90">/ 100</p>
        </div>
      </div>
      <div className="space-y-3 px-5 py-4">
        <p className="text-lg leading-relaxed text-slate-800">{risk.explanation}</p>
        {data.distance_to_city_km > 30 && <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-700">{t.far(data.distance_to_city_km.toFixed(0), data.city.name)}</p>}
        {data.stale && (
          <p className="flex items-center gap-2 rounded-lg bg-amber-100 p-3 text-sm font-medium text-amber-900" role="status">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden /> {t.stale}
          </p>
        )}
      </div>
    </section>
  );
}

