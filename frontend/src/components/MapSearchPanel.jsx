/**
 * iter236 Mission 2 — Map & Radius Location Search panel.
 *
 * Self-contained, fully optional. Drop into a browse page like:
 *
 *   <MapSearchPanel
 *     open={mapOpen}
 *     onToggle={() => setMapOpen(o => !o)}
 *     onGeoChange={(filter) => setGeoFilter(filter)}    // {lat,lng,radius_km} | null
 *   />
 *
 * UX (per the iter236 Mission 2 spec):
 *   • 320px collapsible panel above the grid.
 *   • Default center: navigator.geolocation → Montreal QC (45.5017, -73.5673).
 *   • Draggable circle showing the search radius.
 *   • Range slider 10 → 500 km (step 10), debounced 400ms.
 *   • Info banner: "Showing listings within {radius} km of your selected location".
 *
 * Calls /api/marketplace/items/geo internally to fetch + plot markers.
 * The grid stays the source of truth — the page passes the geo filter
 * down to its own listing-fetch path so cards reflect the same set.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Circle,
  Popup,
  useMapEvents,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin, X } from 'lucide-react';

// Leaflet default marker icon paths break under Webpack — bind explicit URLs.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const MONTREAL_CENTER = [45.5017, -73.5673];

function ClickToRecenter({ setCenter }) {
  useMapEvents({
    click(e) {
      setCenter([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

// iter237 Fix 5c — When the marker list changes, auto-fit the map to
// include every blue pin so users immediately see all returned listings.
function FitToBounds({ markers, center }) {
  const map = useMap();
  useEffect(() => {
    if (!map) return;
    const coords = markers
      .filter((m) => m?.geo?.coordinates?.length === 2)
      .map((m) => [m.geo.coordinates[1], m.geo.coordinates[0]]); // [lat, lng]
    if (coords.length === 0) return;
    // Also include the search center so the user's anchor stays in view.
    coords.push(center);
    try {
      map.fitBounds(coords, { padding: [40, 40], maxZoom: 12 });
    } catch {
      /* noop — bounds can be invalid on first frame */
    }
  }, [markers, center, map]);
  return null;
}

const MapSearchPanel = ({
  open = false,
  onClose,
  onGeoChange,
  backendUrl,
  isFrench = false,
}) => {
  const [center, setCenter] = useState(MONTREAL_CENTER);
  const [radiusKm, setRadiusKm] = useState(50);
  const [markers, setMarkers] = useState([]);
  const debouncedRef = useRef(null);

  // On mount → try geolocation, fall back to Montreal silently.
  useEffect(() => {
    if (!open) return;
    if (typeof navigator === 'undefined' || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setCenter([pos.coords.latitude, pos.coords.longitude]),
      () => undefined,
      { timeout: 4000, maximumAge: 60000 },
    );
  }, [open]);

  // Debounced geo filter propagation + marker refresh.
  useEffect(() => {
    if (!open) return undefined;
    if (debouncedRef.current) clearTimeout(debouncedRef.current);
    debouncedRef.current = setTimeout(() => {
      const filter = { lat: center[0], lng: center[1], radius_km: radiusKm };
      try { onGeoChange && onGeoChange(filter); } catch { /* noop */ }
      // Fetch markers for the map overlay (capped at 60).
      if (backendUrl) {
        const url = `${backendUrl}/marketplace/items/geo?lat=${filter.lat}&lng=${filter.lng}&radius_km=${filter.radius_km}&limit=60`;
        fetch(url)
          .then((r) => r.ok ? r.json() : { items: [] })
          // iter237 — markers now read from the GeoJSON `geo` field.
          .then((d) => setMarkers((d.items || []).filter((it) => it?.geo?.coordinates?.length === 2)))
          .catch(() => setMarkers([]));
      }
    }, 400);
    return () => debouncedRef.current && clearTimeout(debouncedRef.current);
  }, [center, radiusKm, open, onGeoChange, backendUrl]);

  // Cleanup geo filter when panel closes.
  useEffect(() => {
    if (!open) {
      try { onGeoChange && onGeoChange(null); } catch { /* noop */ }
    }
    // We intentionally only re-run when `open` toggles.
  }, [open, onGeoChange]);

  const banner = useMemo(() => (
    isFrench
      ? `Affichage des annonces dans un rayon de ${radiusKm} km de l'emplacement sélectionné`
      : `Showing listings within ${radiusKm} km of your selected location`
  ), [radiusKm, isFrench]);

  if (!open) return null;

  return (
    <div
      className="w-full mb-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-md overflow-hidden"
      data-testid="map-search-panel"
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          <MapPin className="h-4 w-4 text-[#2d6be4]" />
          {isFrench ? 'Recherche par carte' : 'Search by Map'}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500"
          aria-label="Close map panel"
          data-testid="map-search-close-btn"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="h-[320px] w-full" data-testid="map-search-container">
        <MapContainer
          center={center}
          zoom={9}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickToRecenter setCenter={setCenter} />
          <FitToBounds markers={markers} center={center} />
          <Circle
            center={center}
            radius={radiusKm * 1000}
            pathOptions={{ color: '#2d6be4', fillColor: '#2d6be4', fillOpacity: 0.08 }}
          />
          <Marker position={center}>
            <Popup>
              {isFrench ? 'Centre de recherche' : 'Search center'}<br />
              {center[0].toFixed(4)}, {center[1].toFixed(4)}
            </Popup>
          </Marker>
          {markers
            .filter((m) => m?.geo?.coordinates?.length === 2 && m.geo.coordinates[0] !== null)
            .map((m) => (
              <Marker
                key={m.id}
                // iter237 — GeoJSON is [lng, lat]; Leaflet expects [lat, lng].
                position={[m.geo.coordinates[1], m.geo.coordinates[0]]}
              >
                <Popup>
                  <strong>{m.title}</strong><br />
                  {isFrench ? 'Offre actuelle' : 'Current bid'}: {m.current_price || m.starting_price || 0} {m.currency || 'CAD'}<br />
                  <a href={`/listing/${m.id}`}>{isFrench ? "Voir l'annonce" : 'View Listing →'}</a>
                </Popup>
              </Marker>
            ))}
        </MapContainer>
      </div>

      <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40">
        <label className="flex items-center justify-between text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">
          <span>{isFrench ? 'Rayon de recherche' : 'Search radius'}: <span className="text-[#2d6be4]">{radiusKm} km</span></span>
        </label>
        <input
          type="range"
          min={10}
          max={500}
          step={10}
          value={radiusKm}
          onChange={(e) => setRadiusKm(parseInt(e.target.value, 10))}
          className="w-full accent-[#2d6be4]"
          data-testid="map-search-radius-slider"
        />
        <div className="mt-2 text-[12px] text-slate-600 dark:text-slate-300" data-testid="map-search-info-banner">
          {banner}
        </div>
      </div>
    </div>
  );
};

export default MapSearchPanel;
