/**
 * iter387 — Featured Listing Slot
 * ─────────────────────────────────
 * Replaces the removed Google AdSense units on every marketplace-style page.
 * Displays ONE active listing that an admin has flagged `is_featured` (or the
 * partner has boosted with a promotion tier) for the given section.
 *
 * Behavior contract:
 *   • Fetches `/api/carousel/featured?limit=12` — this endpoint already
 *     unions the five listing collections and returns pre-normalized items
 *     with `id`, `title`, `images[]`, `current_price`, `auction_end_date`,
 *     `detail_path`, and `_section` in {marketplace, lots, vehicle,
 *     vehicle_multi_lot, storage}.
 *   • Filters by the requested `section` prop; the `vehicle` section
 *     matches both `vehicle` and `vehicle_multi_lot` doc types.
 *   • Picks the first matching item (list is already sorted newest-first).
 *   • If no matching featured item exists → renders `null` so no empty
 *     container or broken layout remains where the ad zone was.
 *   • Cross-instance in-module promise cache so 8 slots × 4 pages don't
 *     each fire their own network request.
 *
 * Bilingual: reads `title_fr` when `i18n.language` starts with `fr`.
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Star } from 'lucide-react';
import API_BASE from '../config';

// ── Module-level cache — one shared request across every slot on a page ──
let _cachePromise = null;
let _cacheAt = 0;
const CACHE_TTL_MS = 60_000; // 1 minute — matches typical listing edit cadence

async function fetchFeaturedOnce() {
  const now = Date.now();
  if (_cachePromise && now - _cacheAt < CACHE_TTL_MS) return _cachePromise;
  _cacheAt = now;
  _cachePromise = fetch(`${API_BASE}/carousel/featured?limit=12`, {
    headers: { Accept: 'application/json' },
  })
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => []);
  return _cachePromise;
}

// Section aliases — the API returns granular section tags; the frontend
// asks for the broad page category.
const SECTION_MATCH = {
  marketplace: (s) => s === 'marketplace',
  lots:        (s) => s === 'lots',
  vehicle:     (s) => s === 'vehicle' || s === 'vehicle_multi_lot',
  storage:     (s) => s === 'storage',
};

function formatPrice(value, currency = 'CAD') {
  if (value == null || Number.isNaN(Number(value))) return null;
  try {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(Number(value));
  } catch {
    return `$${Number(value).toFixed(0)}`;
  }
}

/**
 * @param {object} props
 * @param {'marketplace'|'lots'|'vehicle'|'storage'} props.section
 * @param {'horizontal'|'banner'} [props.variant='banner'] visual layout
 * @param {string} [props.testId='featured-listing-slot']
 * @param {object} [props.style] outer container inline style overrides
 */
export default function FeaturedListingSlot({
  section,
  variant = 'banner',
  testId = 'featured-listing-slot',
  style = {},
}) {
  const { t, i18n } = useTranslation();
  const [item, setItem] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const rows = await fetchFeaturedOnce();
      if (cancelled) return;
      const matcher = SECTION_MATCH[section] || (() => false);
      const match = (rows || []).find((r) => matcher(r?._section));
      setItem(match || null);
      setReady(true);
    })();
    return () => { cancelled = true; };
  }, [section]);

  // Not loaded yet — render nothing so we never leave an empty container.
  if (!ready || !item) return null;

  const isFr = (i18n.language || 'en').startsWith('fr');
  const title = (isFr ? item.title_fr : item.title_en) || item.title || (isFr ? 'Enchère en vedette' : 'Featured Auction');
  const image = Array.isArray(item.images) && item.images.length > 0 ? item.images[0] : null;
  const price = formatPrice(item.current_price, item.currency);
  const href = item.detail_path || '#';

  const badgeText = isFr ? 'En vedette' : 'Featured';
  const ctaText = isFr ? 'Voir l’enchère' : 'View auction';
  const priceLabel = isFr ? 'Enchère actuelle' : 'Current bid';

  return (
    <a
      href={href}
      data-testid={testId}
      data-section={section}
      data-featured-id={item.id}
      className="block group my-4"
      style={style}
      aria-label={`${badgeText}: ${title}`}
    >
      <div
        className={
          'relative overflow-hidden rounded-2xl border border-blue-100 dark:border-blue-900/40 ' +
          'bg-gradient-to-br from-blue-50 via-white to-cyan-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800 ' +
          'shadow-sm hover:shadow-lg transition-all duration-200 ' +
          (variant === 'horizontal' ? 'flex flex-col sm:flex-row items-stretch' : 'flex flex-col sm:flex-row items-stretch')
        }
      >
        {image && (
          <div className="w-full sm:w-64 md:w-72 flex-shrink-0 aspect-[4/3] sm:aspect-auto bg-slate-100 dark:bg-slate-800 overflow-hidden">
            <img
              src={image}
              alt={title}
              loading="lazy"
              decoding="async"
              className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
            />
          </div>
        )}
        <div className="flex-1 p-5 sm:p-6 flex flex-col justify-between gap-3">
          <div>
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white"
              data-testid={`${testId}-badge`}
            >
              <Star className="w-3 h-3 fill-current" />
              {badgeText}
            </span>
            <h3
              className="mt-3 text-lg sm:text-xl font-bold text-slate-900 dark:text-slate-100 line-clamp-2 group-hover:text-blue-700 dark:group-hover:text-blue-400 transition-colors"
              data-testid={`${testId}-title`}
            >
              {title}
            </h3>
          </div>
          <div className="flex flex-wrap items-end justify-between gap-3">
            {price && (
              <div>
                <div className="text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold">
                  {priceLabel}
                </div>
                <div className="text-xl sm:text-2xl font-bold text-blue-700 dark:text-blue-400 tabular-nums" data-testid={`${testId}-price`}>
                  {price}
                </div>
              </div>
            )}
            <span
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 dark:bg-blue-600 text-white text-sm font-semibold group-hover:bg-blue-700 dark:group-hover:bg-blue-500 transition-colors"
              data-testid={`${testId}-cta`}
            >
              {ctaText}
              <span aria-hidden="true">→</span>
            </span>
          </div>
        </div>
      </div>
    </a>
  );
}
