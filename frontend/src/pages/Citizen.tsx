import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { CheckCircle2, Footprints, LocateFixed, Map as MapIcon, Navigation, Phone, Search, ShieldOff, Siren } from 'lucide-react';
import type { GeocodeResult, PointRisk } from '../api/schema';
import { useApi } from '../state/api-context';
import { DEFAULT_EMERGENCY, DICT, type UiLang } from '../lib/i18n';
import { RiskCard } from '../components/citizen/RiskCard';
import { osmDirectionsUrl } from '../lib/geo';
import { fmtDistance, fmtDuration } from '../lib/format';

const LANG_KEY = 'jalrakshak.citizen.lang';

function readLang(): UiLang {
  try {
    const v = localStorage.getItem(LANG_KEY);
    if (v === 'hi' || v === 'en') return v;
  } catch {
    /* ignore */
  }
  return typeof navigator !== 'undefined' && navigator.language?.startsWith('hi') ? 'hi' : 'en';
}

function telHref(n: string) {
  return `tel:${n.replace(/[^\d+]/g, '')}`;
}

function AdviceList({ title, items, tone, icon }: { title: string; items: string[]; tone: 'now' | 'prepare' | 'avoid'; icon: ReactNode }) {
  if (!items.length) return null;
  const cls = { now: 'border-l-red-600', prepare: 'border-l-sky-600', avoid: 'border-l-slate-700' }[tone];
  return (
    <section className={`rounded-2xl border border-slate-200 border-l-[6px] bg-white p-5 ${cls}`}>
      <h2 className="mb-2 flex items-center gap-2 text-xl font-bold text-slate-900">
        {icon}
        {title}
      </h2>
      <ul className="space-y-2 text-[17px] leading-relaxed text-slate-800">
        {items.map((s, i) => (
          <li key={i} className="flex gap-2">
            <span aria-hidden className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-500" />
            <span>{s}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ShelterCard({ data, lang }: { data: PointRisk; lang: UiLang }) {
  const t = DICT[lang];
  const [showMap, setShowMap] = useState(false);
  const plan = data.evacuation;
  const f = plan.facility;
  const free = Math.max(0, f.capacity - f.occupancy);
  const pad = 0.012;
  const minLat = Math.min(plan.origin.lat, f.lat) - pad;
  const maxLat = Math.max(plan.origin.lat, f.lat) + pad;
  const minLon = Math.min(plan.origin.lon, f.lon) - pad;
  const maxLon = Math.max(plan.origin.lon, f.lon) + pad;
  const embed = `https://www.openstreetmap.org/export/embed.html?bbox=${minLon}%2C${minLat}%2C${maxLon}%2C${maxLat}&layer=mapnik&marker=${f.lat}%2C${f.lon}`;
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="citizen-shelter">
      <h2 className="mb-1 flex items-center gap-2 text-xl font-bold text-slate-900">
        <Navigation className="h-5 w-5 text-sky-700" aria-hidden /> {t.shelter}
      </h2>
      <p className="text-lg font-semibold text-slate-900">{f.name}</p>
      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-base text-slate-700">
        <span>{fmtDistance(plan.route.distance_m)}</span>
        <span className="flex items-center gap-1">
          <Footprints className="h-4 w-4" aria-hidden /> {fmtDuration(plan.route.duration_s)} {t.walk}
        </span>
        <span>
          {free} {t.free}
        </span>
      </p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <a href={osmDirectionsUrl(plan.origin, f)} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2 rounded-xl bg-sky-700 px-4 py-3 text-base font-bold text-white hover:bg-sky-800" data-testid="directions-link">
          <Navigation className="h-5 w-5" aria-hidden /> {t.directions}
        </a>
        <a href={telHref(f.phone)} className="flex items-center justify-center gap-2 rounded-xl border-2 border-slate-300 px-4 py-3 text-base font-bold text-slate-900 hover:bg-slate-50">
          <Phone className="h-5 w-5" aria-hidden /> {t.call}
        </a>
      </div>
      <button type="button" onClick={() => setShowMap((s) => !s)} className="mt-3 flex items-center gap-2 text-base font-semibold text-sky-800 underline underline-offset-4">
        <MapIcon className="h-4 w-4" aria-hidden /> {showMap ? t.hideMap : t.showMap}
      </button>
      {showMap && <iframe title={f.name} src={embed} loading="lazy" className="mt-3 h-64 w-full rounded-xl border border-slate-200" />}
    </section>
  );
}

export default function Citizen() {
  const { client, demo } = useApi();
  const [lang, setLang] = useState<UiLang>(readLang);
  const t = DICT[lang];
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState<null | 'search' | 'locate'>(null);
  const [error, setError] = useState<string | null>(null);
  const [choices, setChoices] = useState<GeocodeResult[] | null>(null);
  const [result, setResult] = useState<PointRisk | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch {
      /* ignore */
    }
    document.documentElement.lang = lang === 'hi' ? 'hi' : 'en';
    return () => {
      document.documentElement.lang = 'en';
    };
  }, [lang]);

  const lookup = async (lat: number, lon: number) => {
    setChoices(null);
    setResult(await client.pointRisk(lat, lon));
  };

  const onSearch = async (e?: FormEvent, query = q) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setBusy('search');
    setError(null);
    setResult(null);
    try {
      const res = await client.geocode(query.trim());
      if (!res.length) setError(t.noResults);
      else if (res.length === 1) await lookup(res[0]!.lat, res[0]!.lon);
      else setChoices(res.slice(0, 5));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const onLocate = () => {
    if (!('geolocation' in navigator)) {
      setError(t.geoUnavailable);
      return;
    }
    setBusy('locate');
    setError(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await lookup(pos.coords.latitude, pos.coords.longitude);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(null);
        }
      },
      (err) => {
        setBusy(null);
        setError(err.code === err.PERMISSION_DENIED ? t.geoDenied : t.geoUnavailable);
      },
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 300_000 },
    );
  };

  const examples = demo ? Object.keys(demo.scenario.geocode).slice(0, 4) : [];
  const emergency = (() => {
    const list = DEFAULT_EMERGENCY.map((e) => ({ label: lang === 'hi' ? e.labelHi : e.label, number: e.number }));
    for (const e of result?.emergency ?? []) if (!list.some((x) => x.number === e.number)) list.push(e);
    return list;
  })();

  return (
    <div className="citizen flex-1 bg-slate-50 text-slate-900 lg:h-full lg:overflow-y-auto">
      <div className="mx-auto max-w-xl space-y-4 px-4 py-5 sm:py-8">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-3xl font-extrabold leading-tight tracking-tight text-slate-900">{t.title}</h1>
            <p className="mt-1 text-lg text-slate-700">{t.subtitle}</p>
          </div>
          <div role="group" aria-label={t.language} className="flex shrink-0 overflow-hidden rounded-lg border-2 border-slate-300 text-base font-bold">
            {(['en', 'hi'] as const).map((l) => (
              <button key={l} type="button" onClick={() => setLang(l)} aria-pressed={lang === l} className={`px-3 py-1.5 ${lang === l ? 'bg-slate-900 text-white' : 'bg-white text-slate-800'}`} lang={l}>
                {l === 'en' ? 'EN' : 'हिं'}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={onSearch} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <label htmlFor="place" className="mb-2 block text-base font-semibold text-slate-800">
            {t.placeLabel}
          </label>
          <div className="flex gap-2">
            <input
              id="place"
              data-testid="citizen-place"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t.placeholder}
              autoComplete="street-address"
              enterKeyHint="search"
              className="min-w-0 flex-1 rounded-xl border-2 border-slate-300 bg-white px-4 py-3 text-lg text-slate-900 placeholder:text-slate-500 focus:border-sky-600 focus:outline-none focus:ring-4 focus:ring-sky-200"
            />
            <button type="submit" disabled={!!busy} className="flex shrink-0 items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-lg font-bold text-white hover:bg-slate-800 disabled:opacity-60" data-testid="citizen-check">
              <Search className="h-5 w-5" aria-hidden />
              <span className="sr-only sm:not-sr-only">{busy === 'search' ? t.checking : t.check}</span>
            </button>
          </div>
          <button type="button" onClick={onLocate} disabled={!!busy} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-sky-700 px-4 py-3 text-lg font-bold text-sky-800 hover:bg-sky-50 disabled:opacity-60">
            <LocateFixed className="h-5 w-5" aria-hidden /> {busy === 'locate' ? t.locating : t.useLocation}
          </button>
          {examples.length > 0 && (
            <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
              {t.try}:
              {examples.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => {
                    setQ(ex);
                    void onSearch(undefined, ex);
                  }}
                  className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 font-medium capitalize text-slate-800 hover:bg-slate-100"
                >
                  {ex}
                </button>
              ))}
            </p>
          )}
        </form>

        <div aria-live="polite" className="space-y-4">
          {busy === 'search' && <p className="text-lg text-slate-700">{t.checking}</p>}
          {error && (
            <p role="alert" className="rounded-xl border-2 border-red-300 bg-red-50 p-4 text-base font-medium text-red-900">
              {error}
            </p>
          )}
          {choices && (
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="mb-2 text-lg font-bold">{t.choose}</h2>
              <ul className="space-y-2">
                {choices.map((c, i) => (
                  <li key={i}>
                    <button type="button" onClick={() => void lookup(c.lat, c.lon).catch((err: Error) => setError(err.message))} className="w-full rounded-xl border-2 border-slate-200 px-4 py-3 text-left text-base hover:border-sky-600">
                      {c.display_name}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {result && (
            <>
              <RiskCard data={result} lang={lang} />
              <AdviceList title={t.now} items={result.advice.now} tone="now" icon={<Siren className="h-5 w-5 text-red-700" aria-hidden />} />
              <ShelterCard data={result} lang={lang} />
              <AdviceList title={t.prepare} items={result.advice.prepare} tone="prepare" icon={<CheckCircle2 className="h-5 w-5 text-sky-700" aria-hidden />} />
              <AdviceList title={t.avoid} items={result.advice.avoid} tone="avoid" icon={<ShieldOff className="h-5 w-5 text-slate-700" aria-hidden />} />
            </>
          )}
        </div>

        <section aria-labelledby="em-title" className="rounded-2xl border-2 border-red-200 bg-white p-4">
          <h2 id="em-title" className="mb-3 flex items-center gap-2 text-xl font-bold text-red-800">
            <Phone className="h-5 w-5" aria-hidden /> {t.emergency}
          </h2>
          <ul className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2" data-testid="emergency-numbers">
            {emergency.map((e) => (
              <li key={`${e.number}-${e.label}`}>
                <a href={telHref(e.number)} className={`flex h-full items-center gap-3 rounded-xl px-4 py-3 ${e.number === '112' ? 'bg-red-700 text-white hover:bg-red-800' : 'border-2 border-slate-200 text-slate-900 hover:bg-slate-50'}`}>
                  <span className={`whitespace-nowrap font-mono font-black ${e.number.length > 5 ? 'text-lg' : 'text-2xl'}`}>{e.number}</span>
                  <span className="text-sm font-semibold leading-tight">{e.label}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
        <p className="text-sm leading-relaxed text-slate-600">{t.disclaimer}</p>
      </div>
    </div>
  );
}
