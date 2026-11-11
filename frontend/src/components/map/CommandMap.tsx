import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';
import { Circle, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import type { CityRisk, CitySummary, EvacuationPlan, Facility } from '../../api/schema';
import { LEVEL_COLORS } from '../../lib/levels';
import { cityIcon, facilityIcon, FACILITY_STYLE, pinIcon } from './icons';

export const INDIA_BOUNDS: L.LatLngBoundsExpression = [
  [7.5, 68.5],
  [33.5, 97.5],
];
export const OSM_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
export const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function FlyTo({ detail, selectedId, focus }: { detail?: CityRisk | undefined; selectedId: string | null; focus?: [number, number] | null }) {
  const map = useMap();
  const wardsKey = detail?.city.id ?? '';
  useEffect(() => {
    if (focus) {
      map.flyTo(focus, Math.max(map.getZoom(), 14), { duration: 0.8 });
      return;
    }
    if (selectedId && detail && detail.city.id === selectedId) {
      const pts = detail.city.wards.map((w) => L.latLng(w.lat, w.lon));
      pts.push(L.latLng(detail.city.lat, detail.city.lon));
      const b = L.latLngBounds(pts).pad(0.25);
      map.flyToBounds(b, { duration: 1.1, maxZoom: 13 });
    } else if (!selectedId) {
      map.flyToBounds(INDIA_BOUNDS, { duration: 0.9 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, wardsKey, focus?.[0], focus?.[1]]);
  return null;
}

/** Invalidate size when the container resizes (panels opening, responsive layout). */
function AutoResize() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [map]);
  return null;
}

export interface CommandMapProps {
  cities: CitySummary[];
  selectedId: string | null;
  detail?: CityRisk | undefined;
  facilities?: Facility[] | undefined;
  selectedWardId?: string | null;
  plans?: EvacuationPlan[] | undefined;
  onSelectCity?: (id: string) => void;
  onSelectWard?: (id: string) => void;
  focus?: [number, number] | null;
  className?: string;
  showLegend?: boolean;
}

export default function CommandMap({ cities, selectedId, detail, facilities, selectedWardId, plans, onSelectCity, onSelectWard, focus, className = 'h-full w-full', showLegend = true }: CommandMapProps) {
  const wardRisk = useMemo(() => new Map(detail?.wards.map((w) => [w.ward_id, w.risk]) ?? []), [detail]);
  const showDetail = detail && detail.city.id === selectedId;

  return (
    <div className={`relative ${className}`}>
      <MapContainer
        bounds={INDIA_BOUNDS}
        className="jr-dark-tiles h-full w-full"
        zoomSnap={0.5}
        zoomControl={false}
        minZoom={4}
        maxZoom={17}
        worldCopyJump={false}
        attributionControl
        aria-label="Flood risk map of India"
      >
        <TileLayer url={OSM_URL} attribution={OSM_ATTRIBUTION} maxZoom={19} />
        <ZoomControl position="bottomright" />
        <FlyTo detail={detail} selectedId={selectedId} focus={focus ?? null} />
        <AutoResize />

        {showDetail &&
          detail.city.wards.map((w) => {
            const r = wardRisk.get(w.id);
            const color = r ? LEVEL_COLORS[r.level] : '#64748b';
            const sel = w.id === selectedWardId;
            return (
              <Circle
                key={w.id}
                center={[w.lat, w.lon]}
                radius={w.radius_m}
                pathOptions={{ color: sel ? '#ffffff' : color, weight: sel ? 3 : 1.5, fillColor: color, fillOpacity: sel ? 0.55 : 0.33 }}
                eventHandlers={{ click: () => onSelectWard?.(w.id) }}
              >
                <Tooltip className="jr-tip" direction="top" sticky>
                  <strong>{w.name}</strong>
                  {r && (
                    <>
                      {' '}
                      · {r.score.toFixed(1)} <span style={{ color }}>{r.level.toUpperCase()}</span>
                    </>
                  )}
                </Tooltip>
              </Circle>
            );
          })}

        {plans?.map((p, i) => (
          <Polyline
            key={`plan-${i}`}
            positions={p.route.geometry}
            pathOptions={{ color: '#38bdf8', weight: 4, opacity: 0.95, dashArray: p.route.method === 'straight_line' ? '8 8' : undefined }}
          />
        ))}
        {plans?.flatMap((p, i) =>
          p.alternatives.map((a, j) => (
            <Polyline key={`alt-${i}-${j}`} positions={a.route.geometry} pathOptions={{ color: '#a78bfa', weight: 2.5, opacity: 0.8, dashArray: '4 6' }} />
          )),
        )}
        {plans?.map((p, i) => (
          <Marker key={`o-${i}`} position={[p.origin.lat, p.origin.lon]} icon={pinIcon('#f97316')}>
            <Tooltip className="jr-tip" direction="top">Evacuation origin</Tooltip>
          </Marker>
        ))}

        {showDetail &&
          facilities?.map((f) => (
            <Marker key={f.id} position={[f.lat, f.lon]} icon={facilityIcon(f.type)} keyboard={false}>
              <Tooltip className="jr-tip" direction="top">
                <strong>{f.name}</strong>
                <br />
                {FACILITY_STYLE[f.type].label} · {f.occupancy}/{f.capacity} occupied · {f.elevation_m} m
              </Tooltip>
            </Marker>
          ))}

        {cities.map((c) => {
          const sel = c.city.id === selectedId;
          if (sel && showDetail) return null; // ward zones replace the city marker when drilled in
          return (
            <Marker
              key={c.city.id}
              position={[c.city.lat, c.city.lon]}
              icon={cityIcon(c.city.name, c.risk.score, c.risk.level, sel, true)}
              eventHandlers={{ click: () => onSelectCity?.(c.city.id) }}
              title={`${c.city.name}: ${c.risk.score.toFixed(1)} (${c.risk.level})`}
              alt={`${c.city.name} risk ${c.risk.level}`}
              zIndexOffset={Math.round(c.risk.score * 10)}
            />
          );
        })}
      </MapContainer>
      {showLegend && <MapLegend withFacilities={!!showDetail} />}
    </div>
  );
}

function MapLegend({ withFacilities }: { withFacilities: boolean }) {
  return (
    <div className="pointer-events-none absolute bottom-6 left-3 z-[500] rounded-lg border border-white/10 bg-ink-950/85 px-3 py-2 text-[11px] text-slate-300 shadow-panel backdrop-blur">
      <div className="mb-1 font-semibold uppercase tracking-wider text-slate-400">Risk level</div>
      <div className="flex gap-3">
        {(['green', 'yellow', 'orange', 'red'] as const).map((l) => (
          <span key={l} className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: LEVEL_COLORS[l] }} />
            {l}
          </span>
        ))}
      </div>
      {withFacilities && (
        <div className="mt-1.5 flex gap-3 border-t border-white/10 pt-1.5">
          {(Object.keys(FACILITY_STYLE) as (keyof typeof FACILITY_STYLE)[]).map((t) => (
            <span key={t} className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: FACILITY_STYLE[t].color }} />
              {FACILITY_STYLE[t].label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
