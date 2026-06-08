/**
 * iter202 Phase B — Vehicle Detail Page redesign components
 * ==========================================================
 * Self-contained detail-page primitives:
 *   • VehicleBreadcrumb       — Home › Vehicle Auctions › Category › YMM
 *   • VehiclePhotoGallery     — main + thumb strip + fullscreen lightbox
 *                                (← → keyboard nav, swipe, ESC, counter)
 *   • VehicleAcquisitionCost  — gross-up math card for the bid panel
 *   • RelatedVehicles         — bottom-of-page horizontal carousel
 *   • formatVin               — partial-mask helper (first 3 + *** + last 4)
 *
 * Reuses VehicleListingCard.compact for related-vehicles cards.
 */
import API_BASE from '../../config';
import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ChevronLeft, ChevronRight, X, ChevronRight as ChevronRightIcon, Camera,
  Car, Calculator, Loader2, ArrowRight, Info,
} from 'lucide-react';
import VehicleListingCard from './VehicleListingCard';
import useVehicleCountdown from '../../hooks/useVehicleCountdown';
import { formatListingPrice } from '../../utils/currencyFormatter';

const API = API_BASE;

// ---------------------------------------------------------------------------
// VIN partial-mask helper — first 3 + *** + last 4. Full VIN never shown
// to non-winning buyers (server enforces this for the post-auction reveal).
// ---------------------------------------------------------------------------
export const formatVin = (vin) => {
  const v = (vin || '').replace(/\s+/g, '').toUpperCase();
  if (!v || v.length < 7) return v || '—';
  return `${v.slice(0, 3)}***${v.slice(-4)}`;
};

// ---------------------------------------------------------------------------
// Provincial sales-tax rates used by the Acquisition Cost gross-up.
// Source: province_regulations seed (kept in sync with backend math).
// Combined effective rate on platform fees only (not on the vehicle itself).
// ---------------------------------------------------------------------------
const PROVINCE_TAX_ON_FEES = {
  BC: 0.05, AB: 0.05, SK: 0.05, MB: 0.05, NT: 0.05, NU: 0.05, YT: 0.05,
  ON: 0.13, NB: 0.15, NS: 0.15, PE: 0.15, NL: 0.15,
  QC: 0.14975, // GST 5% + QST 9.975% on commission
};

// ---------------------------------------------------------------------------
// Acquisition cost calculator — exposed for tests + bid panel.
// Math matches /api/vehicles/{id}/unlock-quote and CEO spec:
//   1. base_fee = bid * 0.025
//   2. tax_on_fee = base_fee * province_rate
//   3. subtotal = base_fee + tax_on_fee
//   4. total_charged = (subtotal + 0.30) / (1 - 0.029)
//   5. stripe_fee = total_charged - subtotal
//   6. platform_net = base_fee   (always 2.5% on the dot)
// ---------------------------------------------------------------------------
export const calculateAcquisitionCost = (bid, province = 'ON') => {
  const b = Number(bid) || 0;
  if (b <= 0) {
    return { bid: 0, baseFee: 0, taxOnFee: 0, subtotal: 0, stripeFee: 0, total: 0, platformNet: 0, totalAcquisition: 0 };
  }
  const taxRate = PROVINCE_TAX_ON_FEES[province] ?? 0.13;
  const baseFee = b * 0.025;
  const taxOnFee = baseFee * taxRate;
  const subtotal = baseFee + taxOnFee;
  const total = (subtotal + 0.30) / (1 - 0.029);
  const stripeFee = total - subtotal;
  const platformNet = baseFee;
  return {
    bid: b,
    baseFee: round2(baseFee),
    taxOnFee: round2(taxOnFee),
    subtotal: round2(subtotal),
    stripeFee: round2(stripeFee),
    total: round2(total),
    platformNet: round2(platformNet),
    totalAcquisition: round2(b + total),
    province,
    taxRate,
  };
};

const round2 = (n) => Math.round(n * 100) / 100;

// ===========================================================================
// VehicleBreadcrumb
// ===========================================================================
export const VehicleBreadcrumb = ({ category, vehicle }) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const navigate = useNavigate();

  const ymm = vehicle ? `${vehicle.year || ''} ${vehicle.make || ''} ${vehicle.model || ''}`.trim() : '';
  const catLabel = category ? (isFr ? category.label_fr : category.label_en) : null;

  const Item = ({ onClick, children, current, testId }) => (
    <li className="inline-flex items-center text-xs sm:text-sm">
      {onClick ? (
        <button
          type="button"
          onClick={onClick}
          className="text-slate-600 dark:text-slate-400 hover:text-[#0B2545] dark:hover:text-cyan-300 hover:underline"
          data-testid={testId}
        >
          {children}
        </button>
      ) : (
        <span
          aria-current={current ? 'page' : undefined}
          className={current ? 'text-slate-900 dark:text-white font-semibold' : 'text-slate-600 dark:text-slate-400'}
          data-testid={testId}
        >
          {children}
        </span>
      )}
    </li>
  );
  const Sep = () => (
    <li aria-hidden className="inline-flex items-center text-slate-400 dark:text-slate-600 mx-1.5">
      <ChevronRightIcon className="h-3.5 w-3.5" />
    </li>
  );

  return (
    <nav aria-label="Breadcrumb" data-testid="vehicle-breadcrumb">
      <ol className="flex flex-wrap items-center gap-y-1">
        <Item onClick={() => navigate('/')} testId="vehicle-breadcrumb-home">
          {t('breadcrumb.home', 'Home')}
        </Item>
        <Sep />
        <Item onClick={() => navigate('/vehicle-auctions')} testId="vehicle-breadcrumb-auctions">
          {t('breadcrumb.vehicleAuctions', 'Vehicle Auctions')}
        </Item>
        {catLabel && (
          <>
            <Sep />
            <Item onClick={() => navigate(`/vehicle-auctions?category_id=${category.id}`)} testId="vehicle-breadcrumb-category">
              {catLabel}
            </Item>
          </>
        )}
        {ymm && (
          <>
            <Sep />
            <Item current testId="vehicle-breadcrumb-ymm">
              {ymm}
            </Item>
          </>
        )}
      </ol>
    </nav>
  );
};

// ===========================================================================
// VehiclePhotoGallery (with fullscreen Lightbox)
// ===========================================================================
export const VehiclePhotoGallery = ({ media = [], title = 'Vehicle' }) => {
  const { t } = useTranslation();
  const photos = useMemo(
    () => (media || []).map((m) => (typeof m === 'string' ? m : m?.url)).filter(Boolean),
    [media]
  );
  const hasPhotos = photos.length > 0;
  const [index, setIndex] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const touchStartX = useRef(null);

  const goPrev = useCallback(() => setIndex((i) => (i - 1 + photos.length) % photos.length), [photos.length]);
  const goNext = useCallback(() => setIndex((i) => (i + 1) % photos.length), [photos.length]);

  // Keyboard nav (lightbox open only)
  useEffect(() => {
    if (!lightboxOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape') setLightboxOpen(false);
      else if (e.key === 'ArrowLeft') goPrev();
      else if (e.key === 'ArrowRight') goNext();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [lightboxOpen, goPrev, goNext]);

  // Lock body scroll while lightbox open
  useEffect(() => {
    if (!lightboxOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [lightboxOpen]);

  if (!hasPhotos) {
    return (
      <div
        className="w-full aspect-[16/10] rounded-2xl bg-slate-100 dark:bg-slate-800 flex flex-col items-center justify-center text-slate-400"
        data-testid="vehicle-gallery-empty"
      >
        <Car className="h-16 w-16 mb-2" aria-hidden />
        <p className="text-sm font-medium">{t('vehicleGallery.noPhotos', 'No photos provided')}</p>
      </div>
    );
  }

  const handleTouchStart = (e) => { touchStartX.current = e.touches[0].clientX; };
  const handleTouchEnd = (e) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 40) (dx < 0 ? goNext : goPrev)();
    touchStartX.current = null;
  };

  return (
    <div className="space-y-3" data-testid="vehicle-gallery">
      {/* Main photo */}
      <button
        type="button"
        onClick={() => setLightboxOpen(true)}
        className="relative block w-full aspect-[16/10] rounded-2xl overflow-hidden bg-slate-100 dark:bg-slate-800 group"
        aria-label={t('vehicleGallery.openLightbox', 'Open fullscreen viewer')}
        data-testid="vehicle-gallery-main"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <img
          src={photos[index]}
          alt={`${title} — ${index + 1}`}
          width="1280"
          height="800"
          loading="eager"
          decoding="async"
          className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
        />
        {/* Counter top-right */}
        <span
          className="absolute top-3 right-3 inline-flex items-center gap-1 rounded-md bg-black/60 backdrop-blur-sm text-white text-xs font-bold px-2 py-1"
          data-testid="vehicle-gallery-counter"
        >
          <Camera className="h-3 w-3" />
          {index + 1} / {photos.length}
        </span>
        {photos.length > 1 && (
          <>
            <button type="button" onClick={(e) => { e.stopPropagation(); goPrev(); }} className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/50 hover:bg-black/70 backdrop-blur text-white flex items-center justify-center" aria-label={t('vehicleGallery.prev', 'Previous photo')} data-testid="vehicle-gallery-prev">
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button type="button" onClick={(e) => { e.stopPropagation(); goNext(); }} className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/50 hover:bg-black/70 backdrop-blur text-white flex items-center justify-center" aria-label={t('vehicleGallery.next', 'Next photo')} data-testid="vehicle-gallery-next">
              <ChevronRight className="h-5 w-5" />
            </button>
          </>
        )}
      </button>

      {/* Thumb strip */}
      {photos.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar" style={{ scrollbarWidth: 'none' }} data-testid="vehicle-gallery-thumbs">
          {photos.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setIndex(i)}
              className={`flex-shrink-0 w-20 h-14 rounded-md overflow-hidden border-2 transition-colors ${i === index ? 'border-cyan-500' : 'border-transparent hover:border-slate-300'}`}
              aria-label={`${t('vehicleGallery.thumb', 'Photo')} ${i + 1}`}
              aria-pressed={i === index}
              data-testid={`vehicle-gallery-thumb-${i}`}
            >
              <img src={p} alt="" loading="lazy" decoding="async" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {/* Lightbox — iter291: z-[9998] keeps the overlay above the
          navbar (z-[70]) and banner (z-[80]); close button sits at
          z-[9999] so the × is always tappable on mobile. */}
      {lightboxOpen && (
        <div
          className="fixed inset-0 z-[9998] bg-black flex items-center justify-center"
          role="dialog"
          aria-modal="true"
          aria-label={t('vehicleGallery.lightboxLabel', 'Vehicle photo gallery')}
          data-testid="vehicle-gallery-lightbox"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          <button
            type="button"
            onClick={() => setLightboxOpen(false)}
            className="fixed top-4 right-4 z-[9999] w-11 h-11 rounded-full bg-black/70 hover:bg-black/90 text-white flex items-center justify-center shadow-lg ring-1 ring-white/20"
            style={{ top: 'max(1rem, env(safe-area-inset-top, 1rem))' }}
            aria-label={t('common.close', 'Close')}
            data-testid="vehicle-gallery-lightbox-close"
          >
            <X className="h-6 w-6" />
          </button>
          <span className="absolute top-5 left-4 text-white text-sm font-semibold bg-white/15 backdrop-blur rounded-full px-3 py-1">
            {index + 1} / {photos.length}
          </span>
          {photos.length > 1 && (
            <>
              <button type="button" onClick={goPrev} className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/15 hover:bg-white/25 text-white flex items-center justify-center" aria-label={t('vehicleGallery.prev', 'Previous photo')}>
                <ChevronLeft className="h-6 w-6" />
              </button>
              <button type="button" onClick={goNext} className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/15 hover:bg-white/25 text-white flex items-center justify-center" aria-label={t('vehicleGallery.next', 'Next photo')}>
                <ChevronRight className="h-6 w-6" />
              </button>
            </>
          )}
          <img
            src={photos[index]}
            alt={`${title} — ${index + 1}`}
            className="max-w-[92vw] max-h-[88vh] object-contain"
          />
        </div>
      )}
    </div>
  );
};

// ===========================================================================
// VehicleAcquisitionCost — transparent gross-up breakdown for the bid panel
// ===========================================================================
export const VehicleAcquisitionCost = ({ bid, currency = 'CAD', province = 'ON' }) => {
  const { t } = useTranslation();
  const calc = useMemo(() => calculateAcquisitionCost(bid, province), [bid, province]);
  if (!calc.bid) return null;
  return (
    <div className="rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3 text-xs space-y-1.5" data-testid="vehicle-acquisition-cost">
      <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-200 font-semibold mb-1">
        <Calculator className="h-3.5 w-3.5 text-cyan-600" />
        {t('vehicleBidPanel.acquisitionTitle', 'Total Acquisition Cost (estimate)')}
      </div>
      <Row label={t('vehicleBidPanel.yourBid', 'Your bid')} value={formatListingPrice(calc.bid, currency)} testId="vehicle-acq-bid" />
      <Row label={t('vehicleBidPanel.platformFee', 'Platform fee (2.5%)')} value={formatListingPrice(calc.baseFee, currency)} testId="vehicle-acq-base" />
      <Row label={t('vehicleBidPanel.taxOnFee', 'Sales tax on fee')} value={formatListingPrice(calc.taxOnFee, currency)} testId="vehicle-acq-tax" />
      <Row label={t('vehicleBidPanel.processingFee', 'Processing & technology')} value={formatListingPrice(calc.stripeFee, currency)} testId="vehicle-acq-stripe" />
      <div className="my-1 border-t border-slate-200 dark:border-slate-700" />
      <Row
        label={t('vehicleBidPanel.unlockTotal', 'Unlock fee total')}
        value={formatListingPrice(calc.total, currency)}
        bold
        testId="vehicle-acq-total-fee"
      />
      <Row
        label={t('vehicleBidPanel.estTotalCost', 'Est. total to acquire')}
        value={formatListingPrice(calc.totalAcquisition, currency)}
        bold
        emphasis
        testId="vehicle-acq-total"
      />
      {/* iter283-vehicle-fee-cleanup — Stable, bilingual legal
          disclaimer footer required for Quebec / Canadian auto-dealer
          regulatory compliance. Always visible in the pricing card,
          regardless of locale/expansion/tier. Wording is FROZEN —
          coordinate with legal before changing. */}
      <p
        className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed mt-2 pt-2 border-t border-slate-200 dark:border-slate-700"
        data-testid="vehicle-pricing-legal-disclaimer"
      >
        <Info className="inline h-3 w-3 mr-0.5" />
        {t(
          'vehicleBidPanel.legalDisclaimer',
          'Vehicle hammer price is paid directly to the seller. BidVex collects only the Platform Fee + applicable tax. Provincial transfer tax & registration are buyer-paid.'
        )}
      </p>
    </div>
  );
};

const Row = ({ label, value, bold, emphasis, testId }) => (
  <div className="flex items-center justify-between" data-testid={testId}>
    <span className={`${bold ? 'font-semibold text-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-400'}`}>{label}</span>
    <span className={`tabular-nums ${bold ? 'font-bold text-slate-900 dark:text-white' : 'text-slate-700 dark:text-slate-200'} ${emphasis ? 'text-base text-[#0B2545] dark:text-cyan-300' : ''}`}>{value}</span>
  </div>
);

// ===========================================================================
// RelatedVehicles — bottom-of-page horizontal carousel
// ===========================================================================
export const RelatedVehicles = ({ categoryId, excludeId }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const { format: formatCountdown } = useVehicleCountdown();

  useEffect(() => {
    if (!categoryId) { setItems([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const params = new URLSearchParams({ category_id: categoryId, limit: '4' });
        if (excludeId) params.set('exclude_id', excludeId);
        const res = await axios.get(`${API}/vehicles?${params.toString()}`);
        if (!cancelled) setItems(res.data?.vehicles || []);
      } catch {
        if (!cancelled) setItems([]);
      }
    })();
    return () => { cancelled = true; };
  }, [categoryId, excludeId]);

  if (items === null) {
    return (
      <div className="py-8" data-testid="vehicle-related-loading">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('vehicleRelated.loading', 'Loading similar vehicles…')}
        </div>
      </div>
    );
  }

  // Spec rule: hide entirely if fewer than 2 results
  if (items.length < 2) return null;

  return (
    <section className="py-8 sm:py-10" data-testid="vehicle-related">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">
          {t('vehicleRelated.title', 'Similar Vehicles')}
        </h2>
        <button
          type="button"
          onClick={() => navigate(`/vehicle-auctions?category_id=${categoryId}`)}
          className="text-sm font-semibold text-cyan-600 hover:text-cyan-700 hover:underline inline-flex items-center gap-1"
          data-testid="vehicle-related-view-all"
        >
          {t('vehicleRelated.viewAll', 'View more')} <ArrowRight className="h-4 w-4" />
        </button>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory no-scrollbar" style={{ scrollbarWidth: 'none' }}>
        {items.map((v) => {
          const cd = formatCountdown(v.end_time, { endedLabel: t('vehicleCard.ended', 'Ended') });
          return (
            <div key={v.id} className="snap-start flex-shrink-0 w-[78%] sm:w-[40%] md:w-[30%] lg:w-[calc((100%-3rem)/4)]">
              <VehicleListingCard vehicle={v} countdown={cd} compact onClick={() => navigate(`/vehicle-auctions/${v.id}`)} />
            </div>
          );
        })}
      </div>
    </section>
  );
};
