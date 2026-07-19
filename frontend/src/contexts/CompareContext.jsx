/**
 * iter364 — Compare Listings context.
 *
 * Global selection state for the side-by-side comparison feature.
 * Users can select up to 4 listings across the platform (marketplace,
 * lots, storage, vehicles); the sticky <CompareBar> appears at ≥2
 * selections; the /compare (/fr/comparer) route renders the full table.
 *
 * Persisted to sessionStorage so the selection survives an accidental
 * refresh but doesn't leak across browser sessions.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const CompareContext = createContext(null);

const MAX_ITEMS = 4;
const STORAGE_KEY = 'bidvex_compare_selection_v1';

const _load = () => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ITEMS) : [];
  } catch { return []; }
};

const _save = (list) => {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch { /* ignore quota */ }
};

/**
 * Normalise the various listing shapes into a stable "compare item"
 * shape so downstream table columns don't need to know the original
 * collection. Each collection stores its own key/field naming; we map
 * them all here so the table is uniform.
 */
export const toCompareItem = (raw, section = 'marketplace') => {
  if (!raw || typeof raw !== 'object') return null;
  const id = raw.id || raw._id;
  if (!id) return null;
  return {
    id,
    section,           // 'marketplace' | 'lots' | 'storage' | 'vehicle'
    title: raw.title || raw.name || raw.unit_number || '',
    image: raw.images?.[0] || raw.image_url || raw.photos?.[0] || raw.thumbnail_url || '',
    current_bid: raw.current_price ?? raw.current_bid ?? raw.starting_price ?? 0,
    starting_price: raw.starting_price ?? raw.min_bid ?? 0,
    auction_end_date: raw.auction_end_date || raw.end_date || raw.ends_at,
    condition: raw.condition || raw.item_condition || '',
    city: raw.city || raw.location || '',
    region: raw.region || raw.province || '',
    seller_name: raw.seller_name || raw.dealer_name || raw.facility_name || '',
    bid_count: raw.bid_count ?? raw.total_bids ?? 0,
    // Vehicle-specific
    vin: raw.vin || '',
    make: raw.make || '',
    model: raw.model || '',
    year: raw.year || null,
    mileage: raw.mileage ?? raw.odometer ?? null,
    // Store the section-appropriate detail path for the "Bid Now" CTA.
    detail_path: raw.detail_path || _detailPathFor(section, id),
  };
};

const _detailPathFor = (section, id) => {
  switch (section) {
    case 'lots':    return `/lots/${id}`;
    case 'storage': return `/storage-auctions/${id}`;
    case 'vehicle': return `/vehicle-auctions/${id}`;
    default:        return `/listing/${id}`;
  }
};

export function CompareProvider({ children }) {
  const [selected, setSelected] = useState(_load);

  useEffect(() => { _save(selected); }, [selected]);

  const isSelected = useCallback((id) => selected.some((l) => l.id === id), [selected]);

  const add = useCallback((raw, section) => {
    const item = toCompareItem(raw, section);
    if (!item) return { ok: false, reason: 'invalid' };
    setSelected((prev) => {
      if (prev.some((l) => l.id === item.id)) return prev;
      if (prev.length >= MAX_ITEMS) return prev;
      return [...prev, item];
    });
    return { ok: true };
  }, []);

  const remove = useCallback((id) => {
    setSelected((prev) => prev.filter((l) => l.id !== id));
  }, []);

  const toggle = useCallback((raw, section) => {
    const id = raw?.id || raw?._id;
    if (!id) return { ok: false, reason: 'invalid' };
    if (selected.some((l) => l.id === id)) {
      remove(id);
      return { ok: true, added: false };
    }
    if (selected.length >= MAX_ITEMS) {
      return { ok: false, reason: 'max_reached', max: MAX_ITEMS };
    }
    return add(raw, section);
  }, [selected, add, remove]);

  const clear = useCallback(() => setSelected([]), []);

  const value = useMemo(() => ({
    selected, isSelected, add, remove, toggle, clear, MAX_ITEMS,
    count: selected.length,
  }), [selected, isSelected, add, remove, toggle, clear]);

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare() {
  const ctx = useContext(CompareContext);
  if (!ctx) {
    // Safe fallback so components outside the provider render harmlessly.
    return { selected: [], count: 0, isSelected: () => false, toggle: () => ({}), remove: () => {}, clear: () => {}, MAX_ITEMS };
  }
  return ctx;
}

export default CompareContext;
