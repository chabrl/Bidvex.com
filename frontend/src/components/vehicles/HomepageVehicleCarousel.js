/**
 * iter202 Phase B — Homepage Vehicle Carousel
 * ============================================
 * Position: AFTER `<StorageAuctionsPromo>` and BEFORE `<HotItemsSection>`
 *           (Tendances/Trending). The carousel REPLACES the legacy
 *           `HomepageLiveVehicles` (iter172) component in the same slot.
 *
 * Visibility: BOTH must be true — otherwise component returns null:
 *   1. feature flag `vehicle_auctions_enabled` === true
 *   2. at least 1 active vehicle listing exists (data-driven)
 *
 * Layout per breakpoint:
 *   • Desktop ≥1024px : 4 cards side-by-side, ← / → arrow buttons
 *   • Tablet 768-1023 : 2.5 cards visible, swipe via CSS scroll-snap
 *   • Mobile  ≤767px  : 1.2 cards visible, swipe + "View all X →" link
 *
 * Implementation: pure CSS scroll-snap (no carousel library, sprint constraint).
 *
 * Reuse: VehicleListingCard with `compact={true}`, useVehicleCountdown hook.
 *
 * Data fetch: GET /api/vehicles?status=active&sort_by=end_time&sort_order=asc
 *             &limit=10&promoted_first=true — single fetch on mount.
 *             Result cached in component state for the session — does NOT
 *             refetch on language switch.
 */
import API_BASE from '../../config';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Car, ChevronLeft, ChevronRight, ArrowRight, Star,
  PlusCircle, Building2, BadgeCheck,
} from 'lucide-react';
import VehicleListingCard from './VehicleListingCard';
import useVehicleCountdown from '../../hooks/useVehicleCountdown';
import useFeatureFlag from '../../hooks/useFeatureFlag';

const API = API_BASE;

const HomepageVehicleCarousel = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { enabled: flagEnabled, loading: flagLoading } = useFeatureFlag('vehicle_auctions_enabled');

  const [items, setItems] = useState(null); // null = loading, [] = none, [...] = data
  const scrollRef = useRef(null);
  const [showLeft, setShowLeft] = useState(false);
  const [showRight, setShowRight] = useState(false);
  const { format: formatCountdown } = useVehicleCountdown();

  // Single fetch on mount — does NOT refetch on language switch (sprint rule).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(
          `${API}/vehicles?status=active&sort_by=end_time&sort_order=asc&limit=10&promoted_first=true`
        );
        if (!cancelled) setItems(res.data?.vehicles || []);
      } catch {
        // Sprint rule: on error, hide section silently
        if (!cancelled) setItems([]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const updateArrows = () => {
    const el = scrollRef.current;
    if (!el) return;
    setShowLeft(el.scrollLeft > 8);
    setShowRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 8);
  };

  useEffect(() => {
    updateArrows();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener('scroll', updateArrows, { passive: true });
    window.addEventListener('resize', updateArrows);
    return () => {
      el.removeEventListener('scroll', updateArrows);
      window.removeEventListener('resize', updateArrows);
    };
  }, [items?.length]);

  const scroll = (dir) => {
    const el = scrollRef.current;
    if (!el) return;
    // Scroll by ~one card width (cards are ~300-340px depending on viewport)
    el.scrollBy({ left: dir * (el.clientWidth * 0.8), behavior: 'smooth' });
  };

  // Visibility gates per spec
  if (flagLoading) return null;
  if (!flagEnabled) return null;
  if (items === null) {
    // Skeleton — keeps layout from jumping during fetch
    return (
      <section
        className="py-12 sm:py-14 bg-[#0B2545]"
        data-testid="homepage-vehicle-carousel-loading"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div className="h-8 w-56 bg-white/10 rounded animate-pulse" />
            <div className="h-5 w-24 bg-white/10 rounded animate-pulse" />
          </div>
          <div className="flex gap-4 overflow-x-auto pb-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="min-w-[260px] h-72 bg-slate-800/60 animate-pulse rounded-xl flex-shrink-0" />
            ))}
          </div>
        </div>
      </section>
    );
  }
  if (items.length === 0) return null;

  return (
    <section
      className="py-12 sm:py-14 bg-[#0B2545] relative overflow-hidden"
      data-testid="homepage-vehicle-carousel"
    >
      {/* subtle background grid */}
      <div className="absolute inset-0 opacity-[0.04] pointer-events-none" aria-hidden>
        <div className="absolute inset-0" style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.7) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.7) 1px, transparent 1px)",
          backgroundSize: '40px 40px',
        }} />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-500/15 border border-cyan-400/30 text-cyan-200 text-[11px] font-semibold uppercase tracking-wider px-3 py-1 mb-2">
              <Car className="h-3.5 w-3.5" />
              {t('vehicleCarousel.eyebrow', 'Vehicle Auctions')}
            </span>
            <h2 className="text-2xl sm:text-3xl font-black text-white leading-tight">
              {t('vehicleCarousel.title', 'Live vehicle auctions')}
            </h2>
            <p className="text-sm text-slate-300/90 mt-1 max-w-xl">
              {t('vehicleCarousel.subtitle', 'Verified Canadian dealers · ending soon · provincial-compliant.')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate('/vehicle-auctions')}
              className="text-cyan-300 font-semibold hover:text-cyan-200 hover:underline text-sm inline-flex items-center gap-1"
              data-testid="homepage-vehicles-view-all"
            >
              {t('vehicleCarousel.viewAll', 'View all {{count}} vehicles', { count: items.length })}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Carousel container */}
        <div className="relative">
          {/* Desktop arrow buttons (hidden on mobile per spec) */}
          {showLeft && (
            <button
              type="button"
              onClick={() => scroll(-1)}
              aria-label={t('vehicleCarousel.prev', 'Previous')}
              className="hidden lg:flex absolute left-0 top-1/2 -translate-y-1/2 z-20 w-10 h-10 rounded-full bg-white shadow-lg items-center justify-center hover:bg-cyan-50 -ml-3"
              data-testid="homepage-vehicles-arrow-left"
            >
              <ChevronLeft className="h-5 w-5 text-slate-900" />
            </button>
          )}
          {showRight && (
            <button
              type="button"
              onClick={() => scroll(1)}
              aria-label={t('vehicleCarousel.next', 'Next')}
              className="hidden lg:flex absolute right-0 top-1/2 -translate-y-1/2 z-20 w-10 h-10 rounded-full bg-white shadow-lg items-center justify-center hover:bg-cyan-50 -mr-3"
              data-testid="homepage-vehicles-arrow-right"
            >
              <ChevronRight className="h-5 w-5 text-slate-900" />
            </button>
          )}

          <div
            ref={scrollRef}
            className="flex gap-4 overflow-x-auto pb-3 snap-x snap-mandatory scroll-smooth no-scrollbar"
            style={{ scrollbarWidth: 'none' }}
            data-testid="homepage-vehicles-list"
          >
            {items.map((v) => {
              const cd = formatCountdown(v.end_time, { endedLabel: t('vehicleCard.ended', 'Ended') });
              return (
                <div
                  key={v.id}
                  className="snap-start flex-shrink-0
                             w-[78%] sm:w-[40%] md:w-[38%] lg:w-[calc((100%-3rem)/4)]"
                  data-testid={`homepage-vehicle-card-${v.id}`}
                >
                  <VehicleListingCard
                    vehicle={v}
                    countdown={cd}
                    compact
                    onClick={() => navigate(`/vehicle-auctions/${v.id}`)}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Mobile-only "View All" link below carousel (spec) */}
        <div className="mt-4 sm:hidden text-center">
          <button
            type="button"
            onClick={() => navigate('/vehicle-auctions')}
            className="inline-flex items-center gap-1 text-cyan-300 font-semibold text-sm hover:underline"
            data-testid="homepage-vehicles-view-all-mobile"
          >
            {t('vehicleCarousel.viewAllMobile', 'View all {{count}} vehicles', { count: items.length })}
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>

        {/* Dealer CTA strip — always rendered when section is visible */}
        <div
          className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-3"
          data-testid="homepage-vehicles-cta-strip"
        >
          <button
            type="button"
            onClick={() => navigate('/vehicle-auctions/seller/register')}
            className="rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-cyan-400/40 backdrop-blur-sm p-4 text-left transition-all"
            data-testid="homepage-vehicles-cta-register"
          >
            <Star className="h-6 w-6 text-cyan-300 mb-2" />
            <h4 className="text-base font-bold text-white mb-1">
              {t('vehicleCarousel.cta.registerTitle', 'Become a verified seller')}
            </h4>
            <p className="text-xs text-slate-300/85">
              {t('vehicleCarousel.cta.registerBody', 'Private, dealer or auctioneer — list across Canada.')}
            </p>
          </button>
          <button
            type="button"
            onClick={() => navigate('/vehicle-auctions/create')}
            className="rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-cyan-400/40 backdrop-blur-sm p-4 text-left transition-all"
            data-testid="homepage-vehicles-cta-list"
          >
            <PlusCircle className="h-6 w-6 text-emerald-300 mb-2" />
            <h4 className="text-base font-bold text-white mb-1">
              {t('vehicleCarousel.cta.listTitle', 'List a vehicle')}
            </h4>
            <p className="text-xs text-slate-300/85">
              {t('vehicleCarousel.cta.listBody', 'Reach buyers from BC to Newfoundland in minutes.')}
            </p>
          </button>
          <button
            type="button"
            onClick={() => navigate('/vehicle-auctions/dealer-license')}
            className="rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-cyan-400/40 backdrop-blur-sm p-4 text-left transition-all"
            data-testid="homepage-vehicles-cta-license"
          >
            <BadgeCheck className="h-6 w-6 text-amber-300 mb-2" />
            <h4 className="text-base font-bold text-white mb-1">
              {t('vehicleCarousel.cta.licenseTitle', 'Verify your dealer licence')}
            </h4>
            <p className="text-xs text-slate-300/85">
              {t('vehicleCarousel.cta.licenseBody', 'OMVIC, AMVIC, VSA, SAAQ, FCAA all supported.')}
            </p>
          </button>
        </div>
      </div>
    </section>
  );
};

export default HomepageVehicleCarousel;
