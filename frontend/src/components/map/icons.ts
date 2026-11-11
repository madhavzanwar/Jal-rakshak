import L from 'leaflet';
import type { FacilityType, RiskLevel } from '../../api/schema';
import { LEVEL_COLORS, LEVEL_ON_COLORS } from '../../lib/levels';

export const FACILITY_STYLE: Record<FacilityType, { color: string; label: string; svg: string }> = {
  shelter: {
    color: '#0284c7',
    label: 'Shelter',
    svg: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></svg>',
  },
  hospital: {
    color: '#e11d48',
    label: 'Hospital',
    svg: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  },
  relief_camp: {
    color: '#7c3aed',
    label: 'Relief camp',
    svg: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 3 20h18L12 4z"/><path d="M12 12l-3 8M12 12l3 8"/></svg>',
  },
};

const facCache = new Map<string, L.DivIcon>();
export function facilityIcon(type: FacilityType, highlight = false): L.DivIcon {
  const key = `${type}:${highlight}`;
  let icon = facCache.get(key);
  if (!icon) {
    const s = FACILITY_STYLE[type];
    const size = highlight ? 30 : 24;
    icon = L.divIcon({
      className: '',
      html: `<div class="jr-fac" style="width:${size}px;height:${size}px;background:${s.color}">${s.svg}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
    facCache.set(key, icon);
  }
  return icon;
}

export function cityIcon(name: string, score: number, level: RiskLevel, selected: boolean, showLabel: boolean): L.DivIcon {
  const size = Math.round(26 + (score / 100) * 14);
  const pulse = level === 'red' || level === 'orange' ? `<span class="pulse" style="background:${LEVEL_COLORS[level]}55"></span>` : '';
  const label = showLabel ? `<span class="label">${name}</span>` : '';
  return L.divIcon({
    className: '',
    html: `<div class="jr-city-marker${selected ? ' selected' : ''}" style="width:${size}px;height:${size}px">${pulse}<span class="dot" style="background:${LEVEL_COLORS[level]};color:${LEVEL_ON_COLORS[level]}">${Math.round(score)}</span>${label}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export function pinIcon(color = '#38bdf8'): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div style="width:16px;height:16px;border-radius:9999px;background:${color};border:3px solid #fff;box-shadow:0 0 0 4px ${color}55"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}
