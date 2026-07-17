/**
 * iter239 Mission 5 — Featured Listings horizontal snap-scroll banner.
 *
 * Renders the promoted listings returned by
 * `GET /api/promoted-listings?section={section}&limit=8` as a horizontal,
 * snap-scrollable carousel that sits ABOVE the marketplace/lots/storage/vehicles
 * results grid. Falls back to `null` silently when no items are returned.
 */
import React, { useEffect, useState, useRef } from 'react';

import { useTranslation } from 'react-i18next';
import { Sparkles, ChevronLeft, ChevronRight } from 'lucide-react';
import SafeImage from './SafeImage';
import { formatCurrency } from '../utils/currencyFormatter';
import API_BASE from '../config';
import { LangLink } from './LangLink';

const FeaturedListingsBanner = ({ section = 'marketplace', limit = 8 }) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').startsWith('fr');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const scrollerRef = useRef(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    fetch(`${API_BASE}/promoted-listings?section=${encodeURIComponent(section)}&limit=${limit}`, {
      signal: ctrl.signal,
    })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setItems(Array.isArray(d.items) ? d.items : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [section, limit]);

  const scrollBy = (delta) => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollBy({ left: delta, behavior: 'smooth' });
    }
  };

  if (loading) return null;
  if (!items.length) return null;

  const targetForId = (item) => {
    const lt = (item.listing_type || '').toLowerCase();
    if (lt === 'lot_auction' || lt === 'multi_item_listing') return `/lots/${item.id}`;
    if (lt === 'storage_locker' || lt === 'storage_auction') return `/storage-auctions/${item.id}`;
    if (lt === 'vehicle' || lt === 'vehicle_auction') return `/vehicles/${item.id}`;
    return `/listing/${item.id}`;
  };

  return (
    <section
      className="relative mb-6 rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50 via-white to-amber-50 p-3 sm:p-4 shadow-sm"
      data-testid="featured-listings-banner"
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="flex items-center gap-2 text-base sm:text-lg font-bold text-slate-900">
          <Sparkles className="h-4 w-4 text-amber-500" />
          {isFr ? 'Annonces en vedette' : 'Featured Listings'}
        </h2>
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => scrollBy(-320)}
            className="h-8 w-8 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-600 hover:border-amber-400 hover:text-amber-600"
            aria-label="Scroll left"
            data-testid="featured-scroll-left"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => scrollBy(320)}
            className="h-8 w-8 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-600 hover:border-amber-400 hover:text-amber-600"
            aria-label="Scroll right"
            data-testid="featured-scroll-right"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div
        ref={scrollerRef}
        className="flex gap-3 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2"
        style={{ scrollbarWidth: 'thin' }}
        data-testid="featured-scroller"
      >
        {items.map((item) => (
          <LangLink
            key={item.id}
            to={targetForId(item)}
            className="snap-start flex-shrink-0 w-[240px] sm:w-[260px] bg-white rounded-lg border border-slate-200 hover:border-amber-400 hover:shadow-md transition-all overflow-hidden"
            data-testid={`featured-card-${item.id}`}
          >
            <div className="relative h-[140px] bg-slate-100">
              {item.images?.[0] ? (
                <SafeImage
                  src={item.images[0]}
                  alt={item.title}
                  width={260}
                  height={140}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-300">
                  <Sparkles className="h-8 w-8" />
                </div>
              )}
              <span className="absolute top-2 left-2 inline-flex items-center gap-1 bg-amber-500 text-white text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded-full shadow">
                <Sparkles className="h-3 w-3" />
                {isFr ? 'Vedette' : 'Featured'}
              </span>
            </div>
            <div className="p-3">
              <p className="text-sm font-semibold text-slate-900 line-clamp-2 leading-snug">
                {item.title}
              </p>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-base font-extrabold text-slate-900">
                  {formatCurrency(item.current_price || item.starting_price || 0, item.currency || 'CAD')}
                </span>
                <span className="text-[10px] text-slate-500">
                  {item.city || item.region || ''}
                </span>
              </div>
            </div>
          </LangLink>
        ))}
      </div>
    </section>
  );
};

export default FeaturedListingsBanner;
