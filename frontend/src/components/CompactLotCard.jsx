/**
 * iter368 — Compact multi-lot card.
 *
 * Optimised for browsing hundreds of lots quickly (BidSpotter-class density
 * while keeping BidVex branding). Deliberately minimal:
 *   • 180 px image with `<` / `>` arrows when >1 photo (single image, no
 *     stacked thumbnails).
 *   • Badges strip (Featured, Reserve, Ending soon, Private Sale, Tax-Free).
 *   • Lot #, title (2-line clamp), location.
 *   • Current Bid + optional Buy Now.
 *   • Auto-Bid Bot Setup button.
 *   • Compact "Fees" popover (Buyer premium, taxes, pickup, storage, others).
 *   • Card border reflects one of four states: default | leading | outbid | ended.
 *
 * NO opening-bid line. NO large fee breakdown inline.
 * Click anywhere on the card (except action buttons) → open dedicated
 * Lot Detail page at `/lots/{auctionId}/lot/{lot_number}` (see LotDetailPage.jsx).
 * The parent page persists its scroll + filters in history state so returning
 * to the grid restores exactly where the buyer was.
 */
import React, { useState, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';
import {
  ChevronLeft, ChevronRight, MapPin, Bot, Info, Zap, Gavel, Trophy, TrendingDown,
} from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';
import Countdown from 'react-countdown';
import { computeDisplayPrice } from '../utils/priceUtils';
import SafeImage from './SafeImage';

const stateStyles = {
  default: 'border-slate-200 dark:border-slate-800 hover:border-cyan-400',
  leading: 'border-emerald-400 shadow-sm shadow-emerald-100 dark:shadow-emerald-900/30',
  outbid:  'border-rose-400 shadow-sm shadow-rose-100 dark:shadow-rose-900/30',
  ended:   'border-slate-300 opacity-90',
};

const stateBadge = {
  leading: { text: 'LEADING', icon: Trophy,        cls: 'bg-emerald-600 text-white' },
  outbid:  { text: 'OUTBID',  icon: TrendingDown,  cls: 'bg-rose-600 text-white' },
  ended:   { text: 'ENDED',   icon: Gavel,         cls: 'bg-slate-500 text-white' },
};

/**
 * @param {object} props
 * @param {object} props.lot - Full lot object (must include lot_number, current_price, images[], etc.)
 * @param {string} props.auctionId - Parent multi-item listing id.
 * @param {object} props.listing - Parent listing (for locale, fees, badges, seller_account_type).
 * @param {string} props.currentUserId
 * @param {(lot: object) => void} props.onOpenAutoBid - Open Auto-Bid Bot setup modal.
 * @param {(lot: object) => void} props.onBuyNow - Buy Now click.
 * @param {() => void} props.onNavigate - Called just before navigation (to snapshot scroll).
 */
export default function CompactLotCard({
  lot, auctionId, listing, currentUserId,
  onOpenAutoBid, onBuyNow, onNavigate,
}) {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const isFR = i18n.language?.startsWith('fr');
  const [imgIdx, setImgIdx] = useState(0);
  const cardRef = useRef(null);

  const images = Array.isArray(lot.images) && lot.images.length > 0 ? lot.images : [];
  const now = Date.now();
  const endTime = lot.lot_end_time ? new Date(lot.lot_end_time).getTime() : null;
  const isEnded = (endTime && endTime <= now) || lot.lot_status === 'ended' || lot.lot_status === 'sold';
  const timeLeft = endTime ? endTime - now : Infinity;
  const isUrgent = timeLeft > 0 && timeLeft < 60 * 60 * 1000; // < 1h

  const state = useMemo(() => {
    if (isEnded) return 'ended';
    if (!currentUserId) return 'default';
    if (lot.highest_bidder_id === currentUserId) return 'leading';
    if ((lot.bid_count || 0) > 0 && lot.highest_bidder_id && lot.highest_bidder_id !== currentUserId) {
      // User has a bid but isn't leading — treat as outbid. Detection of the
      // buyer's own bid history isn't in the lot payload, so this is a best-effort
      // hint; the Lot Detail page confirms with the true bid_status.
      return 'default';
    }
    return 'default';
  }, [isEnded, currentUserId, lot.highest_bidder_id, lot.bid_count]);

  const title = (isFR ? lot.title_fr : lot.title_en) || lot.title || '—';
  const location = [lot.seller_city || listing?.city, lot.seller_province || listing?.region].filter(Boolean).join(', ');

  const dp = useMemo(() => computeDisplayPrice({
    ...lot,
    current_bid: lot.current_price ?? lot.current_bid ?? null,
  }), [lot]);

  const detailHref = `/lots/${auctionId}/lot/${lot.lot_number}`;

  const openDetail = useCallback((e) => {
    if (e && (e.target.closest('button') || e.target.closest('a') || e.target.closest('[data-stop-click]'))) return;
    // iter368 — Snapshot the grid scroll position so return restores it.
    try {
      const state = {
        scrollY: window.scrollY,
        auctionId,
        lot: lot.lot_number,
      };
      window.sessionStorage.setItem(`bidvex_grid_scroll:${auctionId}`, JSON.stringify(state));
    } catch { /* ignore */ }
    onNavigate && onNavigate();
    navigate(detailHref);
  }, [auctionId, lot.lot_number, navigate, onNavigate, detailHref]);

  const nextImg = (e) => { e.stopPropagation(); setImgIdx((i) => (i + 1) % images.length); };
  const prevImg = (e) => { e.stopPropagation(); setImgIdx((i) => (i - 1 + images.length) % images.length); };

  const badge = state !== 'default' ? stateBadge[state] : null;
  const BadgeIcon = badge?.icon;

  return (
    <Card
      ref={cardRef}
      className={`overflow-hidden border-2 transition-all cursor-pointer ${stateStyles[state]}`}
      onClick={openDetail}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') openDetail(e); }}
      data-testid={`lot-card-${lot.lot_number}`}
      data-lot-state={state}
      data-lot-number={lot.lot_number}
    >
      {/* Image (single, 180 px) with < > arrows if >1 photo */}
      <div className="relative bg-slate-100 dark:bg-slate-800" style={{ height: 180 }}>
        {images.length > 0 ? (
          <>
            <SafeImage
              src={images[imgIdx]}
              alt={`${title} · #${lot.lot_number}`}
              className="w-full h-full object-cover"
            />
            {images.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={prevImg}
                  className="absolute left-1 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                  aria-label={isFR ? 'Photo précédente' : 'Previous photo'}
                  data-testid={`lot-card-${lot.lot_number}-prev-image`}
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={nextImg}
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                  aria-label={isFR ? 'Photo suivante' : 'Next photo'}
                  data-testid={`lot-card-${lot.lot_number}-next-image`}
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <div className="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded font-mono">
                  {imgIdx + 1} / {images.length}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-3xl text-slate-400">🖼️</div>
        )}

        {/* Badge strip (state + featured/reserve/tax-free) */}
        <div className="absolute top-1.5 left-1.5 flex flex-wrap gap-1">
          {badge && (
            <Badge className={`${badge.cls} border-0 text-[10px] font-bold px-2 py-0.5`}>
              {BadgeIcon && <BadgeIcon className="h-3 w-3 mr-0.5" />}
              {isFR ? { LEADING: 'EN TÊTE', OUTBID: 'DÉPASSÉ', ENDED: 'TERMINÉ' }[badge.text] : badge.text}
            </Badge>
          )}
          {lot.is_promoted && (
            <Badge className="bg-amber-500 text-white border-0 text-[10px] font-bold px-2 py-0.5" data-testid={`lot-card-${lot.lot_number}-badge-featured`}>
              ★ {isFR ? 'Mis en avant' : 'Featured'}
            </Badge>
          )}
          {lot.reserve_price != null && lot.reserve_price > 0 && (
            <Badge className="bg-blue-600 text-white border-0 text-[10px] font-bold px-2 py-0.5" data-testid={`lot-card-${lot.lot_number}-badge-reserve`}>
              {isFR ? 'Réserve' : 'Reserve'}
            </Badge>
          )}
          {listing?.seller_account_type === 'individual' && (
            <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-200 text-[10px] font-bold px-2 py-0.5" data-testid={`lot-card-${lot.lot_number}-badge-tax-free`}>
              {isFR ? 'Sans taxe' : 'Tax-Free'}
            </Badge>
          )}
        </div>

        {/* Countdown chip top-right (or urgent flash) */}
        {endTime && !isEnded && (
          <div className="absolute top-1.5 right-1.5" data-testid={`lot-card-${lot.lot_number}-countdown`}>
            <Badge className={`${isUrgent ? 'bg-rose-600 animate-pulse' : 'bg-slate-900/80'} text-white border-0 text-[10px] font-mono px-2 py-0.5`}>
              <Countdown
                date={endTime}
                renderer={({ days, hours, minutes, seconds }) => (
                  days > 0 ? `${days}d ${hours}h` : hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m ${seconds}s`
                )}
              />
            </Badge>
          </div>
        )}
      </div>

      {/* Body — as compact as possible */}
      <div className="p-3 space-y-1.5">
        <div className="flex items-baseline gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
          <span className="font-mono font-semibold">#{lot.lot_number}</span>
          {location && (<><span>·</span><MapPin className="h-3 w-3 inline" /><span className="truncate">{location}</span></>)}
        </div>

        <h3 className="text-sm font-semibold text-slate-900 dark:text-white line-clamp-2 leading-snug" data-testid={`lot-card-${lot.lot_number}-title`}>
          {title}
        </h3>

        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[9px] uppercase tracking-wide text-slate-500 dark:text-slate-400 font-semibold">
              {isFR ? 'Enchère courante' : 'Current Bid'}
            </div>
            <div className="text-base font-bold text-emerald-700 dark:text-emerald-400 font-mono" data-testid={`lot-card-${lot.lot_number}-current-bid`}>
              {formatCurrency(dp.totalPrice ?? lot.current_price ?? lot.starting_price ?? 0)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-slate-500 dark:text-slate-400">
              {lot.bid_count || 0} {isFR ? 'enchères' : 'bids'}
            </div>
          </div>
        </div>

        {/* Action row: Buy Now · Auto-Bid · Fees popover */}
        <div className="flex flex-wrap gap-1.5 pt-1" data-stop-click>
          {lot.buy_now_enabled && lot.buy_now_price != null && !isEnded && (
            <Button
              size="sm"
              className="h-7 px-2 text-[11px] font-semibold bg-cyan-600 hover:bg-cyan-700 text-white flex-1 min-w-[80px]"
              onClick={(e) => { e.stopPropagation(); onBuyNow && onBuyNow(lot); }}
              data-testid={`lot-card-${lot.lot_number}-buy-now`}
            >
              <Zap className="h-3 w-3 mr-1" />
              {isFR ? 'Acheter' : 'Buy Now'} {formatCurrency(lot.buy_now_price)}
            </Button>
          )}
          {!isEnded && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-[11px] font-semibold flex-1 min-w-[70px]"
              onClick={(e) => { e.stopPropagation(); onOpenAutoBid && onOpenAutoBid(lot); }}
              data-testid={`lot-card-${lot.lot_number}-auto-bid`}
            >
              <Bot className="h-3 w-3 mr-1" />
              {isFR ? 'Auto-enchère' : 'Auto-Bid'}
            </Button>
          )}
          {/* Fees popover */}
          <Popover>
            <PopoverTrigger asChild>
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2 text-[11px] font-semibold"
                onClick={(e) => e.stopPropagation()}
                data-testid={`lot-card-${lot.lot_number}-fees-btn`}
                aria-label={isFR ? 'Frais additionnels' : 'Additional fees'}
              >
                <Info className="h-3 w-3 mr-1" />
                {isFR ? 'Frais' : 'Fees'}
              </Button>
            </PopoverTrigger>
            <PopoverContent side="top" className="w-64 p-3" data-testid={`lot-card-${lot.lot_number}-fees-popover`}>
              <div className="text-[11px] font-semibold text-slate-900 dark:text-white mb-2">
                {isFR ? 'Frais additionnels applicables' : 'Additional fees'}
              </div>
              <ul className="space-y-1 text-[11px]">
                <li className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>{isFR ? "Prime de l'acheteur" : "Buyer's premium"}</span>
                  <span className="font-mono">
                    {Number((listing?.buyer_premium_rate ?? listing?.premium_percentage / 100 ?? 0.05) * 100).toFixed(1)}%
                  </span>
                </li>
                <li className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>{isFR ? 'Taxes' : 'Taxes'}</span>
                  <span className="font-mono">
                    {listing?.seller_account_type === 'individual'
                      ? (isFR ? 'Aucune' : 'None')
                      : (isFR ? 'Selon province' : 'Per province')}
                  </span>
                </li>
                <li className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>{isFR ? 'Retrait' : 'Pickup'}</span>
                  <span className="font-mono">
                    {listing?.pickup_fee != null ? formatCurrency(listing.pickup_fee) : (isFR ? 'Gratuit' : 'Free')}
                  </span>
                </li>
                {listing?.storage_fee != null && (
                  <li className="flex justify-between text-slate-700 dark:text-slate-300">
                    <span>{isFR ? 'Entreposage' : 'Storage'}</span>
                    <span className="font-mono">{formatCurrency(listing.storage_fee)}</span>
                  </li>
                )}
                <li className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>{isFR ? 'Traitement' : 'Payment processing'}</span>
                  <span className="font-mono">2.9% + $0.30</span>
                </li>
              </ul>
              <div className="mt-2 text-[10px] text-slate-500 dark:text-slate-400 italic">
                {isFR ? "Calcul détaillé au moment du règlement." : 'Exact totals shown at settlement.'}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </Card>
  );
}
