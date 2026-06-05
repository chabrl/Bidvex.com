/**
 * MapSearchPanel — Full-Screen Map Search.
 *
 * History:
 *   iter236 — original 320px inline panel (Marketplace + Lots).
 *   iter237 — auto-fit bounds to returned markers.
 *   iter241 — marker clustering when count > 10.
 *   iter282 — full-screen overlay upgrade per the user's IMG_4369
 *             reference. Item markers are now 40×40 image circles
 *             with rounded popups, and the panel takes 100vw/100vh
 *             with a floating radius slider + Back button.
 *
 * The component remains a drop-in: parents still pass
 * `open` / `onClose` / `onGeoChange` / `backendUrl` / `isFrench`
 * exactly as before. Whatever scroll position the parent page was at
 * when `open` flipped to `true` is preserved via sessionStorage and
 * restored when the user clicks Back.
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
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin, ArrowLeft } from 'lucide-react';

// Leaflet default marker icon paths break under Webpack — bind explicit URLs.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const MONTREAL_CENTER = [45.5017, -73.5673];
// sessionStorage key holding the scroll Y the parent page was at when the
// fullscreen overlay opened. We restore to it when the user clicks Back.
const SCROLL_RESTORE_KEY = 'bvx.mapSearch.scrollRestore.v1';
// BidVex logo used as the marker fallback when a listing has no image.
const BVX_FALLBACK_LOGO = (
  "data:image/svg+xml;utf8,"
  + "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'>"
  + "<rect width='40' height='40' fill='%231A1A2E'/>"
  + "<text x='50%25' y='55%25' text-anchor='middle' fill='%23ffffff' "
  + "font-family='Helvetica,Arial,sans-serif' font-size='14' font-weight='bold'>BV</text>"
  + "</svg>"
);

// ── Helpers ──────────────────────────────────────────────────────────

const fmtCurrency = (val, currency = 'CAD') => {
  const n = Number(val) || 0;
  try {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `$${n.toFixed(0)} ${currency}`;
  }
};

const primaryImage = (m) => {
  if (!m) return null;
  if (Array.isArray(m.images) && m.images.length > 0) {
    const first = m.images[0];
    if (typeof first === 'string') return first;
    if (first && typeof first === 'object') return first.url || first.src || null;
  }
  return m.image || m.thumbnail || null;
};

/**
 * Build a Leaflet divIcon that renders the listing's primary thumbnail
 * as a 40×40 circle with a white border and a soft shadow. Falls back
 * to the BidVex logo background when no image is available.
 */
const buildImageMarkerIcon = (imageUrl) => {
  const safeUrl = (imageUrl || BVX_FALLBACK_LOGO).replace(/"/g, '&quot;');
  const html = (
    '<div class="bvx-map-marker" '
    + 'style="background-image:url(&quot;' + safeUrl + '&quot;);"></div>'
  );
  return L.divIcon({
    html,
    className: 'bvx-map-marker-wrap',
    iconSize:   [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -22],
  });
};

// ── Map sub-components ───────────────────────────────────────────────

function ClickToRecenter({ setCenter }) {
  useMapEvents({
    click(e) {
      setCenter([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

function FitToBounds({ markers, center }) {
  const map = useMap();
  useEffect(() => {
    if (!map) return;
    const coords = markers
      .filter((m) => m?.geo?.coordinates?.length === 2)
      .map((m) => [m.geo.coordinates[1], m.geo.coordinates[0]]); // [lat, lng]
    if (coords.length === 0) return;
    coords.push(center);
    try {
      map.fitBounds(coords, { padding: [40, 40], maxZoom: 12 });
    } catch {
      /* bounds can be invalid on first frame */
    }
  }, [markers, center, map]);
  return null;
}

/**
 * iter282 — When the parent flips `open` to true we lock the page
 * scroll + stash the current scrollY. On close we restore it.
 * Encapsulated here so parent pages don't need to know anything.
 */
function useScrollLockAndRestore(open) {
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    if (!open) return undefined;

    const previousY = window.scrollY || window.pageYOffset || 0;
    const previousOverflow = document.body.style.overflow;
    try { sessionStorage.setItem(SCROLL_RESTORE_KEY, String(previousY)); } catch { /* noop */ }
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
      try {
        const raw = sessionStorage.getItem(SCROLL_RESTORE_KEY);
        const y = raw ? parseInt(raw, 10) : NaN;
        if (Number.isFinite(y)) {
          // Restore on the next frame so any layout shift settles first.
          window.requestAnimationFrame(() => window.scrollTo(0, y));
        }
        sessionStorage.removeItem(SCROLL_RESTORE_KEY);
      } catch { /* noop */ }
    };
  }, [open]);
}

const MapSearchPanel = ({
  open = false,
  onClose,
  onGeoChange,
  backendUrl,
  isFrench = false,
  category = '',
  province = '',
}) => {
  const [center, setCenter] = useState(MONTREAL_CENTER);
  const [radiusKm, setRadiusKm] = useState(50);
  const [markers, setMarkers] = useState([]);
  const debouncedRef = useRef(null);

  // Lock body scroll while the fullscreen overlay is open + restore on close.
  useScrollLockAndRestore(open);

  // Best-effort geolocation on mount → fall back to Montreal silently.
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
      if (backendUrl) {
        const params = new URLSearchParams({
          lat:       String(filter.lat),
          lng:       String(filter.lng),
          radius_km: String(filter.radius_km),
          limit:     '60',
        });
        if (category) params.set('category', category);
        if (province) params.set('province', province);
        const url = `${backendUrl}/marketplace/items/geo?${params.toString()}`;
        fetch(url)
          .then((r) => r.ok ? r.json() : { items: [] })
          .then((d) => setMarkers(
            (d.items || []).filter((it) => it?.geo?.coordinates?.length === 2),
          ))
          .catch(() => setMarkers([]));
      }
    }, 400);
    return () => debouncedRef.current && clearTimeout(debouncedRef.current);
  }, [center, radiusKm, open, onGeoChange, backendUrl, category, province]);

  // Clear the geo filter when the panel closes.
  useEffect(() => {
    if (!open) {
      try { onGeoChange && onGeoChange(null); } catch { /* noop */ }
    }
  }, [open, onGeoChange]);

  const banner = useMemo(() => (
    isFrench
      ? `Affichage des annonces dans un rayon de ${radiusKm} km de l'emplacement sélectionné`
      : `Showing listings within ${radiusKm} km of your selected location`
  ), [radiusKm, isFrench]);

  // Plain text labels for the floating panel + Back button.
  const t = useMemo(() => ({
    back:        isFrench ? '← Retour'              : '← Back',
    title:       isFrench ? 'Recherche par carte'   : 'Search by Map',
    radiusLabel: isFrench ? 'Rayon de recherche'    : 'Search radius',
    center:      isFrench ? 'Centre de recherche'   : 'Search center',
    currentBid:  isFrench ? 'Offre actuelle'        : 'Current bid',
    viewListing: isFrench ? "Voir l'annonce"        : 'View Listing',
  }), [isFrench]);

  if (!open) return null;

  // ── Markers (image-circle divIcons, optionally clustered) ──
  const validMarkers = markers.filter(
    (m) => m?.geo?.coordinates?.length === 2 && m.geo.coordinates[0] !== null,
  );
  const renderListingMarker = (m) => {
    const icon = buildImageMarkerIcon(primaryImage(m));
    const price = m.current_price || m.current_bid || m.starting_price || 0;
    const img = primaryImage(m);
    return (
      <Marker
        key={m.id}
        position={[m.geo.coordinates[1], m.geo.coordinates[0]]}
        icon={icon}
      >
        <Popup className="bv-map-popup" closeButton={true} autoPan={true}>
          <div data-testid={`bvx-map-popup-${m.id}`} style={{ minWidth: 200 }}>
            {img ? (
              <img
                src={img}
                alt={m.title || ''}
                style={{
                  width: 120,
                  height: 90,
                  objectFit: 'cover',
                  borderRadius: 8,
                  display: 'block',
                  marginBottom: 8,
                }}
                loading="lazy"
              />
            ) : null}
            <div
              style={{
                fontWeight: 700,
                fontSize: 13,
                color: '#1A1A2E',
                lineHeight: 1.3,
                marginBottom: 4,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
              title={m.title}
            >
              {m.title}
            </div>
            <div style={{
              fontSize: 13,
              color: '#0D9F4F',
              fontWeight: 700,
              marginBottom: 8,
            }}>
              {t.currentBid}: {fmtCurrency(price, m.currency || 'CAD')}
            </div>
            <a
              href={`/listing/${m.id}`}
              data-testid={`bvx-map-view-listing-${m.id}`}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'center',
                padding: '8px 12px',
                background: '#2d6be4',
                color: '#fff',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              {t.viewListing} →
            </a>
          </div>
        </Popup>
      </Marker>
    );
  };

  return (
    <>
      {/* Inline style block — keeps the iter282 marker + popup CSS local
          to this component so we don't pollute global stylesheets. */}
      <style>{`
        .bvx-map-marker-wrap { background: transparent !important; border: none !important; }
        .bvx-map-marker {
          width: 40px; height: 40px;
          border-radius: 50%;
          background-color: #1A1A2E;
          background-size: cover;
          background-position: center;
          border: 2px solid #ffffff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.35);
          transition: transform 120ms ease;
        }
        .bvx-map-marker-wrap:hover .bvx-map-marker { transform: scale(1.08); }
        .leaflet-popup.bv-map-popup .leaflet-popup-content-wrapper {
          background: #ffffff;
          border-radius: 8px;
          padding: 12px;
          box-shadow: 0 6px 24px rgba(0,0,0,0.18);
        }
        .leaflet-popup.bv-map-popup .leaflet-popup-content { margin: 0; }
        .leaflet-popup.bv-map-popup .leaflet-popup-tip { display: none; }

        /* iter283-hotfix Mission 3 — High-visibility cluster counter
           pill. Overrides the default leaflet-cluster green blob with
           a prominent white circle + BidVex Blue ring + bold navy
           digits. The default theme is too subtle on satellite-style
           tiles and gets lost over busy backgrounds. */
        .leaflet-cluster-anim .leaflet-marker-icon,
        .leaflet-cluster-anim .leaflet-marker-shadow { transition: transform 0.3s ease-out; }
        .marker-cluster,
        .marker-cluster-small,
        .marker-cluster-medium,
        .marker-cluster-large {
          background-color: transparent !important;
        }
        .marker-cluster div,
        .marker-cluster-small div,
        .marker-cluster-medium div,
        .marker-cluster-large div {
          background-color: #ffffff !important;
          border: 3px solid #0055FF !important;
          color: #0a1628 !important;
          font-weight: 800 !important;
          border-radius: 50% !important;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          width: 100% !important;
          height: 100% !important;
          margin: 0 !important;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        }
        .marker-cluster span {
          line-height: 1 !important;
          font-size: 14px !important;
          color: #0a1628 !important;
          font-weight: 800 !important;
        }
        /* Slightly bigger digits for high-count clusters (visual hierarchy). */
        .marker-cluster-large span { font-size: 16px !important; }
      `}</style>

      {/* Fullscreen overlay */}
      <div
        className="bvx-map-fullscreen"
        data-testid="map-search-panel"
        style={{
          position: 'fixed',
          top: 0, left: 0,
          width: '100vw', height: '100vh',
          zIndex: 1000,
          background: '#000',
        }}
      >
        {/* Back button (top-left, z-index: 1002) */}
        <button
          type="button"
          onClick={onClose}
          aria-label={t.back}
          data-testid="map-search-back-btn"
          style={{
            position: 'fixed',
            top: 16, left: 16,
            zIndex: 1002,
            background: '#2d6be4',
            color: '#fff',
            border: 'none',
            borderRadius: 9999,
            padding: '10px 18px',
            fontSize: 14,
            fontWeight: 700,
            cursor: 'pointer',
            boxShadow: '0 4px 14px rgba(45,107,228,0.45)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <ArrowLeft size={16} />
          <span>{isFrench ? 'Retour' : 'Back'}</span>
        </button>

        {/* Floating radius slider (bottom-left, z-index: 1001) */}
        <div
          data-testid="map-search-radius-card"
          style={{
            position: 'fixed',
            left: 12,
            bottom: 12,
            zIndex: 1001,
            background: 'rgba(15, 23, 42, 0.86)',
            color: '#fff',
            padding: '12px 14px',
            borderRadius: 12,
            backdropFilter: 'blur(6px)',
            width: 'min(360px, calc(100vw - 24px))',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          }}
        >
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            fontWeight: 700,
            marginBottom: 6,
            opacity: 0.95,
          }}>
            <MapPin size={14} color="#2d6be4" />
            <span>{t.title}</span>
          </div>
          <label style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 12,
            fontWeight: 600,
            marginBottom: 6,
          }}>
            <span>{t.radiusLabel}</span>
            <span style={{ color: '#7ab2ff' }}>{radiusKm} km</span>
          </label>
          <input
            type="range"
            min={10}
            max={500}
            step={10}
            value={radiusKm}
            onChange={(e) => setRadiusKm(parseInt(e.target.value, 10))}
            style={{ width: '100%', accentColor: '#2d6be4' }}
            data-testid="map-search-radius-slider"
          />
          <div
            style={{ marginTop: 6, fontSize: 11, opacity: 0.85 }}
            data-testid="map-search-info-banner"
          >
            {banner}
          </div>
        </div>

        {/* Map fills the overlay */}
        <div
          style={{ position: 'absolute', inset: 0, zIndex: 0 }}
          data-testid="map-search-container"
        >
          <MapContainer
            center={center}
            zoom={9}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom
            zoomControl={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ClickToRecenter setCenter={setCenter} />
            <FitToBounds markers={validMarkers} center={center} />
            <Circle
              center={center}
              radius={radiusKm * 1000}
              pathOptions={{ color: '#2d6be4', fillColor: '#2d6be4', fillOpacity: 0.08 }}
            />
            <Marker position={center}>
              <Popup>
                {t.center}<br />
                {center[0].toFixed(4)}, {center[1].toFixed(4)}
              </Popup>
            </Marker>

            {validMarkers.length > 10 ? (
              <MarkerClusterGroup chunkedLoading maxClusterRadius={60}>
                {validMarkers.map(renderListingMarker)}
              </MarkerClusterGroup>
            ) : (
              validMarkers.map(renderListingMarker)
            )}
          </MapContainer>
        </div>
      </div>
    </>
  );
};

export default MapSearchPanel;
