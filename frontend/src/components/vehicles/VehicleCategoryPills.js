/**
 * iter202 Phase A — Vehicle Category Pill Strip
 * ==============================================
 * Horizontal scrollable pill bar with all 15 BidVex vehicle categories.
 * Consumes /api/vehicles/categories (cached on page).
 *
 * UX:
 *   • "All" pill at the start (clears the filter)
 *   • Click a pill → instant client-side filter (constraint: <100ms)
 *   • Selected pill = solid blue with white text + check icon
 *   • Subcategory chips slide in below when a category is selected
 *   • parts_accessories pill shows green "OPEN" dot (no licence required)
 *
 * Constraint #3: reuses the same API as VehicleCategoryGrid.
 */
import React, { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';

const VehicleCategoryPills = ({
  categories = [],
  loading = false,
  selectedCategoryId = null,
  selectedSubcategoryId = null,
  onChange,
}) => {
  const { i18n, t } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const scrollRef = useRef(null);
  const [showLeft, setShowLeft] = useState(false);
  const [showRight, setShowRight] = useState(false);

  const updateScrollIndicators = () => {
    const el = scrollRef.current;
    if (!el) return;
    setShowLeft(el.scrollLeft > 8);
    setShowRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 8);
  };

  useEffect(() => {
    updateScrollIndicators();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener('scroll', updateScrollIndicators, { passive: true });
    window.addEventListener('resize', updateScrollIndicators);
    return () => {
      el.removeEventListener('scroll', updateScrollIndicators);
      window.removeEventListener('resize', updateScrollIndicators);
    };
  }, [categories.length]);

  const scroll = (dir) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.min(360, el.clientWidth * 0.7), behavior: 'smooth' });
  };

  const selected = categories.find((c) => c.id === selectedCategoryId) || null;

  return (
    <div className="bg-white dark:bg-slate-900 border-y border-slate-200 dark:border-slate-800" data-testid="vehicle-category-pills">
      <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8 relative">
        {/* Scroll buttons (desktop) */}
        {showLeft && (
          <button
            type="button"
            onClick={() => scroll(-1)}
            aria-label={t('vehicleCats.scrollLeft', 'Scroll left')}
            className="hidden sm:flex absolute left-1 top-1/2 -translate-y-1/2 z-20 w-8 h-8 rounded-full bg-white dark:bg-slate-800 shadow-md border border-slate-200 dark:border-slate-700 items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-700"
            data-testid="vehicle-cats-scroll-left"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
        {showRight && (
          <button
            type="button"
            onClick={() => scroll(1)}
            aria-label={t('vehicleCats.scrollRight', 'Scroll right')}
            className="hidden sm:flex absolute right-1 top-1/2 -translate-y-1/2 z-20 w-8 h-8 rounded-full bg-white dark:bg-slate-800 shadow-md border border-slate-200 dark:border-slate-700 items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-700"
            data-testid="vehicle-cats-scroll-right"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        )}
        {/* Edge fades */}
        <div className="absolute inset-y-0 left-0 w-8 bg-gradient-to-r from-white dark:from-slate-900 to-transparent pointer-events-none z-10" />
        <div className="absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-white dark:from-slate-900 to-transparent pointer-events-none z-10" />

        <div
          ref={scrollRef}
          className="flex items-center gap-2 py-3 overflow-x-auto scroll-smooth no-scrollbar"
          style={{ scrollbarWidth: 'none' }}
          data-testid="vehicle-cats-scroller"
        >
          {/* All pill */}
          <button
            type="button"
            onClick={() => onChange?.(null, null, null)}
            className={`flex-shrink-0 inline-flex items-center gap-1.5 rounded-full text-sm font-semibold px-4 py-2 border transition-all ${
              !selectedCategoryId
                ? 'bg-[#0B2545] dark:bg-cyan-500 text-white border-[#0B2545] dark:border-cyan-500 shadow-sm'
                : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700 hover:border-[#0B2545] hover:text-[#0B2545]'
            }`}
            data-testid="vehicle-cat-pill-all"
          >
            <Sparkles className="h-4 w-4" />
            {t('vehicleCats.all', 'All categories')}
          </button>
          {/* Category pills */}
          {loading
            ? Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="flex-shrink-0 h-9 w-32 rounded-full bg-slate-100 dark:bg-slate-800 animate-pulse"
                  aria-hidden
                />
              ))
            : categories.map((cat) => {
                const active = cat.id === selectedCategoryId;
                const label = isFr ? cat.label_fr : cat.label_en;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => onChange?.(active ? null : cat.id, null, active ? null : cat)}
                    className={`flex-shrink-0 inline-flex items-center gap-1.5 rounded-full text-sm font-semibold px-4 py-2 border transition-all ${
                      active
                        ? 'bg-[#0B2545] dark:bg-cyan-500 text-white border-[#0B2545] dark:border-cyan-500 shadow-sm'
                        : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700 hover:border-[#0B2545] hover:text-[#0B2545]'
                    }`}
                    data-testid={`vehicle-cat-pill-${cat.id}`}
                    aria-pressed={active}
                  >
                    <span className="text-base leading-none" aria-hidden>{cat.icon}</span>
                    <span>{label}</span>
                    {active && <Check className="h-3.5 w-3.5" />}
                    {!cat.requires_dealer_license && (
                      <span
                        className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-emerald-400"
                        title={isFr ? 'Ouvert à tous les vendeurs' : 'Open to all sellers'}
                        aria-label={isFr ? 'Ouvert à tous les vendeurs' : 'Open to all sellers'}
                      />
                    )}
                  </button>
                );
              })}
        </div>

        {/* Subcategory chips */}
        {selected && Array.isArray(selected.subcategories) && selected.subcategories.length > 0 && (
          <div
            className="flex flex-wrap items-center gap-2 pb-3 -mt-1"
            data-testid="vehicle-subcat-chips"
          >
            <span className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400 mr-1">
              {t('vehicleCats.refine', 'Refine')}:
            </span>
            <button
              type="button"
              onClick={() => onChange?.(selected.id, null, selected)}
              className={`text-xs font-semibold px-3 py-1 rounded-full border transition-colors ${
                !selectedSubcategoryId
                  ? 'bg-cyan-500 text-white border-cyan-500'
                  : 'bg-transparent text-slate-600 dark:text-slate-300 border-slate-300 dark:border-slate-700 hover:border-cyan-500 hover:text-cyan-600'
              }`}
              data-testid="vehicle-subcat-chip-all"
            >
              {t('vehicleCats.allSubcats', 'All subcategories')}
            </button>
            {selected.subcategories.map((sc) => {
              const active = sc.id === selectedSubcategoryId;
              return (
                <button
                  key={sc.id}
                  type="button"
                  onClick={() => onChange?.(selected.id, sc.id, selected)}
                  className={`text-xs font-semibold px-3 py-1 rounded-full border transition-colors ${
                    active
                      ? 'bg-cyan-500 text-white border-cyan-500'
                      : 'bg-transparent text-slate-600 dark:text-slate-300 border-slate-300 dark:border-slate-700 hover:border-cyan-500 hover:text-cyan-600'
                  }`}
                  data-testid={`vehicle-subcat-chip-${sc.id}`}
                  aria-pressed={active}
                >
                  {isFr ? sc.label_fr : sc.label_en}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default VehicleCategoryPills;
