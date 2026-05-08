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
import { formatListingPrice } from '../../utils/currencyFormatter';

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

const VehicleListingCard = ({ vehicle, countdown, onClick, onQuickView }) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [imgError, setImgError] = useState(false);

  const mainImage = (vehicle.media && (
    vehicle.media.find((m) => m.category === 'front')?.url || vehicle.media[0]?.url
  )) || vehicle.image_url || null;

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

  return (
    <article
      className="group relative flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 overflow-hidden focus-within:ring-2 focus-within:ring-cyan-500"
      data-testid={`vehicle-card-${vehicle.id}`}
    >
      {/* Image — explicit aspect-ratio prevents CLS */}
      <button
        type="button"
        onClick={onClick}
        className="relative block aspect-[16/10] w-full bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-900 overflow-hidden"
        aria-label={cardTitle}
        data-testid={`vehicle-card-image-${vehicle.id}`}
      >
        {mainImage && !imgError ? (
          <img
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
      </button>

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
