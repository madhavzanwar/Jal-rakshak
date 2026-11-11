export function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat);
  const dLon = toRad(bLon - aLon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function osmDirectionsUrl(from: { lat: number; lon: number }, to: { lat: number; lon: number }): string {
  const f = (n: number) => n.toFixed(5);
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${f(from.lat)}%2C${f(from.lon)}%3B${f(to.lat)}%2C${f(to.lon)}`;
}
