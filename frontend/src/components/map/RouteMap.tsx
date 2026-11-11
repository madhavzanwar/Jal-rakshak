import 'leaflet/dist/leaflet.css';
import { Fragment, useEffect } from 'react';
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { EvacuationPlan } from '../../api/schema';
import { fmtDistance, fmtDuration } from '../../lib/format';
import { facilityIcon, FACILITY_STYLE, pinIcon } from './icons';
import { OSM_ATTRIBUTION, OSM_URL } from './constants';

function Fit({ plans }: { plans: EvacuationPlan[] }) {
  const map = useMap();
  const key = plans.map((p) => `${p.origin.lat},${p.origin.lon}`).join('|');
  useEffect(() => {
    const pts: L.LatLngExpression[] = [];
    for (const p of plans) {
      pts.push([p.origin.lat, p.origin.lon], ...p.route.geometry);
      for (const a of p.alternatives) pts.push(...a.route.geometry);
    }
    if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.2), { maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}

/** Mini map of evacuation routes: primary routes solid (OSRM) or dashed (straight-line), alternatives violet. */
export default function RouteMap({ plans, className = 'h-72' }: { plans: EvacuationPlan[]; className?: string }) {
  const first = plans[0];
  if (!first) return null;
  return (
    <div className={`overflow-hidden rounded-lg border border-white/10 ${className}`} data-testid="route-map">
      <MapContainer center={[first.origin.lat, first.origin.lon]} zoom={13} className="jr-dark-tiles h-full w-full" scrollWheelZoom={false} aria-label="Evacuation routes map">
        <TileLayer url={OSM_URL} attribution={OSM_ATTRIBUTION} />
        <Fit plans={plans} />
        {plans.map((p, i) => (
          <Fragment key={i}>
            {p.alternatives.map((a, j) => (
              <Polyline key={`a${j}`} positions={a.route.geometry} pathOptions={{ color: '#a78bfa', weight: 3, opacity: 0.85, dashArray: '4 6' }}>
                <Tooltip className="jr-tip" sticky>
                  Alternative: {a.facility.name} · {fmtDistance(a.route.distance_m)}
                </Tooltip>
              </Polyline>
            ))}
            <Polyline positions={p.route.geometry} pathOptions={{ color: '#38bdf8', weight: 5, opacity: 0.95, dashArray: p.route.method === 'straight_line' ? '8 8' : undefined }}>
              <Tooltip className="jr-tip" sticky>
                {p.facility.name} · {fmtDistance(p.route.distance_m)} · {fmtDuration(p.route.duration_s)} ({p.route.method === 'osrm' ? 'road route' : 'straight line'})
              </Tooltip>
            </Polyline>
            <Marker position={[p.origin.lat, p.origin.lon]} icon={pinIcon('#f97316')}>
              <Tooltip className="jr-tip" direction="top">Ward centroid (origin)</Tooltip>
            </Marker>
            {[p.facility, ...p.alternatives.map((a) => a.facility)].map((f, k) => (
              <Marker key={`${f.id}-${k}`} position={[f.lat, f.lon]} icon={facilityIcon(f.type, k === 0)}>
                <Tooltip className="jr-tip" direction="top">
                  {f.name} · {FACILITY_STYLE[f.type].label}
                </Tooltip>
              </Marker>
            ))}
          </Fragment>
        ))}
      </MapContainer>
    </div>
  );
}
