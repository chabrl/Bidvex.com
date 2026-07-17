/**
 * iter202 Phase A — Vehicle Listing Card
 * =======================================
 * Rich vehicle card used by the new VehicleAuctions buyer-grid.
 *
 * Features:
 *   • Explicit `aspect-[16/10]` image container — CLS = 0
 *   • Lazy-loaded image with native loading="lazy" + decoding="async"
 *   • Top-left badges:  LIVE | ENDING SOON | NO RESERVE | PROMOTED
 *   • Top-right badges: TITLE STATUS | DEALER VERIFIED | PROVINCE
 *   • Bottom overlay:   countdown (driven by shared hook — NOT per-card timer)
 *                       and bid count
 *   • Body: title (year make model · trim), running status, mileage/fuel,
 *           dealer · province, current bid, "View" CTA
 *   • Quick-view overlay on hover (desktop)
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Car, Clock, Gauge, Fuel, Settings2, MapPin, ShieldCheck, BadgeCheck,
  AlertTriangle, Building2, User, Sparkles, Award, CheckCircle, TrendingUp,
  Eye, ChevronRight, Flame, Crown,
} from 'lucide-react';
import PartnerBadge from '../PartnerBadge';
import SafeImage from '../SafeImage';
import { formatListingPrice } from '../../utils/currencyFormatter';
// iter286 — Bug 5 — Carfax badge needs viewer's broker status.
import { useAuth } from '../../contexts/AuthContext';
// iter294 P1 — Upcoming countdown badge on index cards.
import UpcomingCountdownBadge from '../UpcomingCountdownBadge';

const PROVINCE_LABEL = {
  BC: 'BC', AB: 'AB', SK: 'SK', MB: 'MB', ON: 'ON', QC: 'QC',
  NB: 'NB', NS: 'NS', PE: 'PE', NL: 'NL', YT: 'YT', NT: 'NT', NU: 'NU',
};

const formatMileage = (mileage, isFr) => {
  if (mileage === null || mileage === undefined || mileage === '') return null;
  const n = Number(mileage);
  if (!Number.isFinite(n) || n <= 0) return null;
  const formatter = new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA');
  return `${formatter.format(n)} km`;
};

const VehicleListingCard = ({ vehicle, countdown, onClick, onQuickView, compact = false }) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [imgError, setImgError] = useState(false);
  // iter286 — Bug 5 — Pull viewer auth context so the Carfax badge can
  // toggle between "Carfax Available" (broker) and "Carfax (Broker Only)".
  const { user } = useAuth() || {};

  const mainImage = (vehicle.media && (
    vehicle.media.find((m) => m.category === 'front')?.url || vehicle.media[0]?.url
  )) || vehicle.image_url || (vehicle.photos && vehicle.photos[0]) || null;

  const titleEn = vehicle.title_en || vehicle.title || '';
  const titleFr = vehicle.title_fr || titleEn;
  const cardTitle = (isFr && titleFr) ? titleFr :
    (vehicle.year && vehicle.make ? `${vehicle.year} ${vehicle.make} ${vehicle.model || ''}`.trim() : titleEn);

  const province = vehicle.location_province ? (PROVINCE_LABEL[vehicle.location_province] || vehicle.location_province) : null;
  const isPromoted = !!vehicle.is_promoted;
  const isFeatured = !!vehicle.is_featured;
  const isEndingSoon = countdown?.critical && !countdown?.ended;
  const isLive = vehicle.auction_type === 'live' && !countdown?.ended;
  const noReserve = !vehicle.reserve_price || vehicle.reserve_price === 0;
  const reserveMet = vehicle.reserve_met === true;
  const titleStatus = vehicle.title_status; // clean | salvage | rebuilt | etc.
  const dealerVerified = vehicle.seller?.verification_status === 'approved' ||
                         vehicle.seller?.dealer_license_verified === true;
  const sellerType = vehicle.seller?.seller_type;

  const currentBid = vehicle.current_bid > 0 ? vehicle.current_bid : (vehicle.starting_price || 0);
  const currency = vehicle.currency || 'CAD';
  const mileageText = formatMileage(vehicle.mileage, isFr);

  // ---------------------------------------------------------------------------
  // Compact variant — used by the homepage carousel (B3). Smaller, simplified.
  // Fields: photo (4:3), Year/Make/Model, City+Province, current bid,
  // time remaining, "Bid Now →" CTA, small verified-dealer badge.
  // ---------------------------------------------------------------------------
  if (compact) {
    return (
      <article
        className="group flex flex-col rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 overflow-hidden"
        data-testid={`vehicle-card-compact-${vehicle.id}`}
      >
        <button
          type="button"
          onClick={onClick}
          className="grid-card-image w-full bg-slate-100 dark:bg-slate-800 text-left"
          aria-label={cardTitle}
          data-testid={`vehicle-card-image-compact-${vehicle.id}`}
        >
          {mainImage && !imgError ? (
            <SafeImage
              src={mainImage}
              alt={cardTitle}
              width="480"
              height="360"
              loading="lazy"
              decoding="async"
              onError={() => setImgError(true)}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Car className="h-12 w-12 text-slate-300 dark:text-slate-700" />
            </div>
          )}
          {dealerVerified && (
            <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-md bg-blue-600 text-white text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 shadow">
              <BadgeCheck className="h-2.5 w-2.5" />
              {t('vehicleCard.dealerVerified', 'Verified dealer')}
            </span>
          )}
          {/* iter304 — Verified Auction Firm badge (compact card variant) */}
          {!!vehicle.seller?.verified_auction_firm && (
            <span className="absolute top-2 right-2 inline-flex items-center gap-1 rounded-md text-white text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 shadow" style={{ backgroundColor: '#2B8FD0' }} data-testid={`vehicle-card-verified-firm-compact-${vehicle.id}`}>
              <ShieldCheck className="h-2.5 w-2.5" />
              {isFr ? "Société d'enchères vérifiée" : 'Verified Auction Firm'}
            </span>
          )}
          {isPromoted && (
            <span className="absolute top-2 right-2 inline-flex items-center gap-0.5 rounded-md bg-amber-500 text-white text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 shadow">
              {t('vehicleCard.promoted', 'Featured')}
            </span>
          )}
        </button>
        <div className="p-3 flex flex-col flex-1 gap-1.5">
          <h4 className="text-sm font-bold text-slate-900 dark:text-white line-clamp-1">
            {cardTitle}
          </h4>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1 line-clamp-1">
            <MapPin className="h-3 w-3 flex-shrink-0" />
            {[vehicle.location_city, province].filter(Boolean).join(', ') || '—'}
          </p>
          <div className="flex items-end justify-between mt-auto pt-1.5">
            <div className="min-w-0">
              <p className="text-[9px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {t('vehicleCard.currentBid', 'Current bid')}
              </p>
              <p className="text-base font-black text-[#0B2545] dark:text-cyan-300 leading-none mt-0.5 truncate">
                {formatListingPrice(currentBid, currency)}
              </p>
            </div>
            <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-slate-600 dark:text-slate-300">
              <Clock className="h-3 w-3" />
              {countdown?.label || '—'}
            </span>
          </div>
          <button
            type="button"
            onClick={onClick}
            className="mt-1 inline-flex items-center justify-center gap-1 rounded-md bg-[#0B2545] hover:bg-[#0E2B52] text-white font-semibold text-xs px-3 py-1.5 transition-colors"
            data-testid={`vehicle-card-compact-cta-${vehicle.id}`}
          >
            {t('vehicleCard.bidNowCta', 'Bid Now')}
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </article>
    );
  }

  // ---------------------------------------------------------------------------
  // Full (default) card — used by VehicleAuctionsPage grid.
  // ---------------------------------------------------------------------------
  return (
    <article
      className="group relative flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 overflow-hidden focus-within:ring-2 focus-within:ring-cyan-500"
      data-testid={`vehicle-card-${vehicle.id}`}
    >
      {/* Image — explicit aspect-ratio prevents CLS.
          iter340 — role="button" div instead of <button>: the quick-view
          overlay contains a real <button>, and interactive elements must
          not nest (React DOM warning). Visual output is identical. */}
      <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(); } }}
        className="relative block aspect-[16/10] w-full bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-900 overflow-hidden cursor-pointer"
        aria-label={cardTitle}
        data-testid={`vehicle-card-image-${vehicle.id}`}
      >
        {mainImage && !imgError ? (
          <SafeImage
            src={mainImage}
            alt={cardTitle}
            width="640"
            height="400"
            loading="lazy"
            decoding="async"
            onError={() => setImgError(true)}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Car className="h-16 w-16 text-slate-300 dark:text-slate-700" />
          </div>
        )}

        {/* Top-left badges */}
        <div className="absolute top-2 left-2 flex flex-col gap-1.5 max-w-[60%]">
          {isPromoted && (
            <span className="inline-flex items-center gap-1 rounded-md bg-amber-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow">
              <Crown className="h-3 w-3" />
              {t('vehicleCard.promoted', 'Featured')}
            </span>
          )}
          {isLive && (
            <span className="inline-flex items-center gap-1 rounded-md bg-red-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow animate-pulse">
              <Flame className="h-3 w-3" />
              {t('vehicleCard.live', 'Live')}
            </span>
          )}
          {/* iter294 P1 — Upcoming countdown on index cards. Computed
              client-side from start_time; NO per-card polling. */}
          {!isLive && vehicle.status === 'active' && vehicle.start_time && new Date(vehicle.start_time).getTime() > Date.now() && (
            <UpcomingCountdownBadge
              startTime={vehicle.start_time}
              compact
              className="shadow"
            />
          )}
          {isEndingSoon && (
            <span className="inline-flex items-center gap-1 rounded-md bg-orange-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow animate-pulse">
              <Clock className="h-3 w-3" />
              {t('vehicleCard.endingSoon', 'Ending soon')}
            </span>
          )}
          {noReserve && (
            <span className="inline-flex items-center gap-1 rounded-md bg-purple-600 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow">
              <Award className="h-3 w-3" />
              {t('vehicleCard.noReserve', 'No reserve')}
            </span>
          )}
          {reserveMet && (
            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow">
              <CheckCircle className="h-3 w-3" />
              {t('vehicleCard.reserveMet', 'Reserve met')}
            </span>
          )}
        </div>

        {/* Top-right badges */}
        <div className="absolute top-2 right-2 flex flex-col items-end gap-1.5 max-w-[40%]">
          {titleStatus === 'clean' && (
            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/95 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow">
              <ShieldCheck className="h-3 w-3" />
              {t('vehicleCard.titleClean', 'Clean title')}
            </span>
          )}
          {titleStatus === 'salvage' && (
            <span className="inline-flex items-center gap-1 rounded-md bg-red-600 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow">
              <AlertTriangle className="h-3 w-3" />
              {t('vehicleCard.titleSalvage', 'Salvage')}
            </span>
          )}
          {dealerVerified && (
            <span className="inline-flex items-center gap-1 rounded-md bg-blue-600 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow">
              <BadgeCheck className="h-3 w-3" />
              {t('vehicleCard.dealerVerified', 'Verified dealer')}
            </span>
          )}
          {/* iter304 — Verified Auction Firm badge (full card variant) */}
          {!!vehicle.seller?.verified_auction_firm && (
            <span className="inline-flex items-center gap-1 rounded-md text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 shadow" style={{ backgroundColor: '#2B8FD0' }} data-testid={`vehicle-card-verified-firm-${vehicle.id}`}>
              <ShieldCheck className="h-3 w-3" />
              {isFr ? "Société d'enchères vérifiée" : 'Verified Auction Firm'}
            </span>
          )}
          {province && (
            <span className="inline-flex items-center gap-1 rounded-md bg-black/60 backdrop-blur-sm text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1">
              <MapPin className="h-3 w-3" />
              {province}
            </span>
          )}
        </div>

        {/* Bottom overlays */}
        <div className="absolute inset-x-2 bottom-2 flex items-end justify-between gap-2">
          <span
            className={`inline-flex items-center gap-1 rounded-md text-white text-[11px] font-bold px-2 py-1 shadow backdrop-blur-sm ${
              countdown?.ended ? 'bg-slate-700/80' : isEndingSoon ? 'bg-orange-600/90' : 'bg-black/60'
            }`}
            data-testid={`vehicle-card-countdown-${vehicle.id}`}
          >
            <Clock className="h-3 w-3" />
            {countdown?.label || '—'}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-white/95 dark:bg-slate-900/90 text-slate-900 dark:text-white text-[11px] font-bold px-2 py-1 shadow">
            <TrendingUp className="h-3 w-3" />
            {t('vehicleCard.bidCount', '{{count}} bids', { count: vehicle.bid_count || 0 })}
          </span>
        </div>

        {/* Quick-view overlay (desktop only) */}
        {onQuickView && (
          <div
            className="hidden sm:flex absolute inset-0 items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity"
            aria-hidden
          >
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); e.preventDefault(); onQuickView?.(vehicle); }}
              className="inline-flex items-center gap-2 rounded-full bg-white text-slate-900 font-semibold px-4 py-2 shadow-lg hover:bg-cyan-50 hover:text-[#0B2545] transition"
              data-testid={`vehicle-card-quickview-${vehicle.id}`}
            >
              <Eye className="h-4 w-4" />
              {t('vehicleCard.quickView', 'Quick view')}
            </button>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-col flex-1 p-4 gap-3">
        <div>
          <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white leading-tight line-clamp-1">
            {cardTitle}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 line-clamp-1">
            {[vehicle.trim, vehicle.exterior_color].filter(Boolean).join(' · ') || (vehicle.body_type || '')}
          </p>
        </div>

        {/* Spec chip row */}
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          {vehicle.condition_report?.is_running !== undefined && (
            vehicle.condition_report.is_running ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 font-semibold">
                <CheckCircle className="h-3 w-3" />
                {t('vehicleCard.running', 'Running')}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 px-2 py-0.5 font-semibold">
                <AlertTriangle className="h-3 w-3" />
                {t('vehicleCard.notRunning', 'Non-running')}
              </span>
            )
          )}
          {sellerType === 'dealer' && (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 font-semibold">
              <Building2 className="h-3 w-3" />
              {t('vehicleCard.dealer', 'Dealer')}
            </span>
          )}
          {sellerType === 'private' && (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 font-semibold">
              <User className="h-3 w-3" />
              {t('vehicleCard.private', 'Private')}
            </span>
          )}
          {vehicle.seller_id && <PartnerBadge sellerId={vehicle.seller_id} size="sm" />}
        </div>

        {/* iter285 — Bug 4 — Province eligibility pill (compact). Shows top
            3 eligible provinces or "All Provinces". Renders TBD when the
            listing predates the feature (legacy listings stay healthy). */}
        {(() => {
          const eligible = vehicle.eligible_provinces;
          if (!Array.isArray(eligible) || eligible.length === 0) {
            return (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold"
                style={{ background: '#fffbeb', color: '#b7791f', fontSize: '10px', border: '1px solid #f6c90e' }}
                data-testid={`vehicle-card-province-pill-${vehicle.id}`}
              >
                ⚠️ {t('vehicleCard.eligibilityTBD', 'Eligibility TBD')}
              </span>
            );
          }
          const isAllSentinel = eligible.length === 1 && eligible[0] === 'ALL';
          const summary = isAllSentinel
            ? t('vehicleCard.allProvinces', 'All Provinces')
            : eligible.slice(0, 3).join(' · ');
          return (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold"
              style={{ background: '#f0fff4', color: '#276749', fontSize: '10px', border: '1px solid #c6f6d5' }}
              data-testid={`vehicle-card-province-pill-${vehicle.id}`}
            >
              ✅ {summary}
            </span>
          );
        })()}

        {/* iter286 — Bug 5 — Carfax availability pill. Only renders when the
            listing has a Carfax URL or PDF attached. Broker partners see a
            green "Carfax Available" badge; individual buyers see a gray
            "Carfax (Broker Only)" badge — a soft conversion nudge. */}
        {(vehicle.carfax_url || vehicle.carfax_file) && (() => {
          const isBroker = !!(
            user?.is_broker_partner ||
            user?.is_broker ||
            user?.broker_partner_status === 'active' ||
            user?.broker_partner_status === 'approved' ||
            user?.role === 'admin'
          );
          if (isBroker) {
            return (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold"
                style={{ background: '#f0fff4', color: '#276749', fontSize: '10px', border: '1px solid #c6f6d5' }}
                data-testid={`vehicle-card-carfax-badge-${vehicle.id}`}
              >
                📄 Carfax Available
              </span>
            );
          }
          return (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
              style={{ background: '#f7fafc', color: '#718096', fontSize: '10px', border: '1px solid #cbd5e0' }}
              data-testid={`vehicle-card-carfax-badge-${vehicle.id}`}
            >
              🔒 Carfax (Broker Only)
            </span>
          );
        })()}

        {/* Specs grid */}
        <div className="grid grid-cols-2 gap-1.5 text-xs text-slate-600 dark:text-slate-400">
          {mileageText && (
            <div className="flex items-center gap-1.5 min-w-0">
              <Gauge className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate">{mileageText}</span>
            </div>
          )}
          {vehicle.fuel_type && (
            <div className="flex items-center gap-1.5 min-w-0">
              <Fuel className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate capitalize">{vehicle.fuel_type}</span>
            </div>
          )}
          {vehicle.transmission && (
            <div className="flex items-center gap-1.5 min-w-0">
              <Settings2 className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate capitalize">{vehicle.transmission}</span>
            </div>
          )}
          {(vehicle.location_city || province) && (
            <div className="flex items-center gap-1.5 min-w-0">
              <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate">
                {[vehicle.location_city, province].filter(Boolean).join(', ')}
              </span>
            </div>
          )}
        </div>

        {/* Footer — price + CTA */}
        <div className="mt-auto pt-3 border-t border-slate-100 dark:border-slate-800 flex items-end justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {t('vehicleCard.currentBid', 'Current bid')}
            </p>
            <p className="text-xl sm:text-2xl font-black text-[#0B2545] dark:text-cyan-300 leading-none mt-1 truncate" data-testid={`vehicle-card-price-${vehicle.id}`}>
              {formatListingPrice(currentBid, currency)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClick}
            className="inline-flex items-center gap-1 rounded-lg bg-[#0B2545] hover:bg-[#0E2B52] text-white font-semibold text-xs sm:text-sm px-3 py-2 transition-colors flex-shrink-0"
            data-testid={`vehicle-card-cta-${vehicle.id}`}
          >
            {t('vehicleCard.viewCta', 'View')}
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </article>
  );
};

export default VehicleListingCard;
