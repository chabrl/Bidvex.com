/**
 * iter369 — Compact multi-lot card (BidSpotter-density design).
 *
 * BUG FIXES delivered in this revision:
 *   • Bug 1 — Button text never wraps: `whitespace-nowrap`, tight padding,
 *     `flex-1 min-w-0` on every button so the row shares width equally.
 *   • Bug 2 — Fixed 200 px image slot with `object-fit: contain` and a
 *     neutral background so portrait / landscape / square images all fit
 *     without cropping.
 *   • Bug 3 — Wishlist heart is perfectly centred inside a 36 × 36 px white
 *     circle (`display: flex; align-items: center; justify-content: center`).
 *   • Bug 4 — Countdown badge is ALWAYS red (rose-600 by default, rose-700
 *     `animate-pulse` under 1 h, rose-500 for > 24 h). Never black or grey.
 *   • Bug 5 — Buy Now is removed from the grid card entirely. It lives only
 *     on the lot-detail page.
 *   • Bug 6 — Inline "Max bid" input + Bid button placed directly on the
 *     card (BidSpotter style). Inline errors for empty / below-minimum
 *     bids without a modal.
 *   • Bug 9 — Clicking the image opens the GlobalImageViewer (P0 lightbox).
 *
 * Secondary buttons: Auto-Bid + Fees (opens fee breakdown popover). The
 * popover recalculates live off the value in the bid input.
 */
import React, { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';
import WatchlistButton from './WatchlistButton';
import AutoBidModal from './AutoBidModal';
import GlobalImageViewer from './GlobalImageViewer';
import { ChevronLeft, ChevronRight, MapPin, Bot, Info, Gavel } from 'lucide-react';
import Countdown from 'react-countdown';
import { formatCurrency } from '../utils/currencyFormatter';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import SafeImage from './SafeImage';

const stateStyles = {
  default: 'border-slate-200 dark:border-slate-800 hover:border-cyan-400',
  leading: 'border-emerald-500 shadow-emerald-100 dark:shadow-emerald-900/30',
  outbid:  'border-rose-500 shadow-rose-100 dark:shadow-rose-900/30',
  ended:   'border-slate-300 opacity-90',
};

// Countdown color thresholds (Bug 4): red < 1 h with pulse, red < 24 h,
// slightly darker red otherwise. NEVER black/grey.
const countdownColor = (msLeft) => {
  if (msLeft < 60 * 60 * 1000) return 'bg-rose-700 text-white animate-pulse';
  if (msLeft < 24 * 60 * 60 * 1000) return 'bg-rose-600 text-white';
  return 'bg-rose-500 text-white';
};

export default function CompactLotCard({
  lot, auctionId, listing, currentUserId, incrementInfo,
  onOpenAutoBid, onNavigate,
  onBuyNow: _onBuyNow,  // kept for backward-compat; Buy Now removed from grid (Bug 5)
}) {
  const { i18n } = useTranslation();
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const isFR = i18n.language?.startsWith('fr');
  const [imgIdx, setImgIdx] = useState(0);
  const [autoBidOpen, setAutoBidOpen] = useState(false);
  const [feesPreview, setFeesPreview] = useState(null);
  const [feesLoading, setFeesLoading] = useState(false);
  const [bidInput, setBidInput] = useState('');
  const [bidError, setBidError] = useState('');
  const [placing, setPlacing] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);

  const images = Array.isArray(lot.images) && lot.images.length > 0 ? lot.images : [];
  const currentPrice = Number(lot.current_price ?? lot.starting_price ?? 0);
  const now = Date.now();
  const endTime = lot.lot_end_time ? new Date(lot.lot_end_time).getTime() : null;
  const isEnded = (endTime && endTime <= now) || lot.lot_status === 'ended' || lot.lot_status === 'sold';
  const timeLeft = endTime ? endTime - now : Infinity;
  const state = useMemo(() => {
    if (isEnded) return 'ended';
    if (currentUserId && lot.highest_bidder_id === currentUserId) return 'leading';
    if (currentUserId && Array.isArray(lot.outbid_user_ids) && lot.outbid_user_ids.includes(currentUserId)) return 'outbid';
    return 'default';
  }, [isEnded, currentUserId, lot.highest_bidder_id, lot.outbid_user_ids]);

  const title = (isFR ? lot.title_fr : lot.title_en) || lot.title || '—';
  const location = [lot.seller_city || listing?.city, lot.seller_province || listing?.region].filter(Boolean).join(', ');
  const currency = listing?.currency || 'CAD';

  // Derive the next valid bid from the same increment engine used elsewhere.
  const getIncrement = useCallback((bid) => {
    if (!incrementInfo) return 5;
    if (incrementInfo.increment_option === 'fixed' && incrementInfo.fixed_increment) return Number(incrementInfo.fixed_increment);
    const sched = incrementInfo.schedule || [];
    for (const row of sched) {
      const lo = Number(row.min ?? 0);
      const hi = row.max == null ? Infinity : Number(row.max);
      if (bid >= lo && bid < hi) return Number(row.step);
    }
    return sched.length ? Number(sched[sched.length - 1].step) : 5;
  }, [incrementInfo]);
  const step = getIncrement(currentPrice);
  const nextBid = currentPrice + step;

  const detailHref = `/lots/${auctionId}/lot/${lot.lot_number}`;

  const openDetail = useCallback((e) => {
    if (e && (e.target.closest('button') || e.target.closest('a') || e.target.closest('input') || e.target.closest('[data-stop-click]'))) return;
    try {
      window.sessionStorage.setItem(`bidvex_grid_scroll:${auctionId}`, JSON.stringify({
        scrollY: window.scrollY, auctionId, lot: lot.lot_number,
      }));
    } catch { /* ignore */ }
    onNavigate && onNavigate();
    navigate(detailHref);
  }, [auctionId, lot.lot_number, navigate, onNavigate, detailHref]);

  const nextImg = (e) => { e.stopPropagation(); setImgIdx((i) => (i + 1) % images.length); };
  const prevImg = (e) => { e.stopPropagation(); setImgIdx((i) => (i - 1 + images.length) % images.length); };

  // Fetch canonical fees using the current bid input (or the lot's current
  // price when the input is empty). Recalculates on every popover open.
  const loadFees = useCallback(() => {
    const amt = Number(bidInput) || currentPrice;
    setFeesLoading(true);
    axios
      .get(`${API_BASE}/multi-item-listings/${auctionId}/lots/${lot.lot_number}/fees-preview`, {
        params: { bid_amount: amt },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 8000,
      })
      .then((res) => setFeesPreview(res.data))
      .catch(() => setFeesPreview(null))
      .finally(() => setFeesLoading(false));
  }, [auctionId, lot.lot_number, currentPrice, token, bidInput]);

  // ---------- Bid handler (Bug 6) ----------
  const handleQuickBid = async (e) => {
    e.stopPropagation();
    setBidError('');
    if (!user) { navigate('/auth'); return; }
    const amount = Number(bidInput);
    if (!bidInput || Number.isNaN(amount)) {
      setBidError(isFR ? 'Veuillez entrer un montant' : 'Please enter a bid amount');
      return;
    }
    if (amount < nextBid) {
      setBidError(isFR
        ? `L'enchère minimum est ${formatCurrency(nextBid)}`
        : `Minimum bid is ${formatCurrency(nextBid)}`);
      return;
    }
    setPlacing(true);
    try {
      await axios.post(
        `${API_BASE}/multi-item-listings/${auctionId}/lots/${lot.lot_number}/bid`,
        { amount, bid_type: 'normal' },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setBidInput('');
      setBidError('');
      // Bubble a soft signal to the parent so it can refetch.
      window.dispatchEvent(new CustomEvent('bidvex:lot-bid-placed', {
        detail: { auctionId, lotNumber: lot.lot_number, amount },
      }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to place bid');
      setBidError(msg);
    } finally {
      setPlacing(false);
    }
  };

  // ---------- Render ----------
  const stateBanners = {
    leading: { text: isFR ? '🏆 Vous menez' : "🏆 You're Leading", cls: 'bg-emerald-500 text-white' },
    outbid:  { text: isFR ? '⚠️ Surenchéri' : '⚠️ Outbid', cls: 'bg-rose-500 text-white animate-pulse' },
    ended:   { text: isFR ? 'TERMINÉ' : 'ENDED', cls: 'bg-slate-600 text-white' },
    default: null,
  };
  const banner = stateBanners[state];

  return (
    <>
      <Card
        className={`overflow-hidden border-2 transition-all cursor-pointer ${stateStyles[state]}`}
        onClick={openDetail}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter') openDetail(e); }}
        data-testid={`lot-card-${lot.lot_number}`}
        data-lot-state={state}
        data-lot-number={lot.lot_number}
      >
        {/* State banner (Leading / Outbid / Ended) — sits above the image */}
        {banner && (
          <div className={`text-[10px] font-bold uppercase tracking-wide px-3 py-1 text-center ${banner.cls}`} data-testid={`lot-card-${lot.lot_number}-banner`}>
            {banner.text}
          </div>
        )}

        {/* Bug 2 — Fixed 200 px image slot, object-contain (never cropped), neutral bg */}
        <div
          className="relative bg-[#f8f9fa] dark:bg-slate-800 flex items-center justify-center overflow-hidden"
          style={{ height: 200 }}
          data-testid={`lot-card-${lot.lot_number}-image-wrapper`}
        >
          {images.length > 0 ? (
            <>
              <SafeImage
                src={images[imgIdx]}
                alt={`${title} · #${lot.lot_number}`}
                className={`w-full h-full object-contain cursor-zoom-in ${isEnded ? 'grayscale' : ''}`}
                style={{ maxHeight: 200, maxWidth: '100%', width: 'auto', height: 'auto' }}
                onClick={(e) => { e.stopPropagation(); setViewerOpen(true); }}
              />
              {images.length > 1 && (
                <>
                  <button
                    type="button"
                    onClick={prevImg}
                    className="absolute left-1 top-1/2 -translate-y-1/2 h-7 w-7 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                    aria-label={isFR ? 'Photo précédente' : 'Previous photo'}
                    data-testid={`lot-card-${lot.lot_number}-prev-image`}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={nextImg}
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                    aria-label={isFR ? 'Photo suivante' : 'Next photo'}
                    data-testid={`lot-card-${lot.lot_number}-next-image`}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                  <div className="absolute bottom-1 left-1/2 -translate-x-1/2 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded font-mono" data-testid={`lot-card-${lot.lot_number}-image-counter`}>
                    {imgIdx + 1} / {images.length}
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl text-slate-400">🖼️</div>
          )}

          {/* TOP-LEFT badge: Tax Free (green) OR Partner Auction (blue) */}
          <div className="absolute top-2.5 left-2.5">
            {listing?.seller_account_type === 'partner' ? (
              <Badge className="bg-blue-600 text-white border-0 text-[10px] font-bold px-2 py-0.5" data-testid={`lot-card-${lot.lot_number}-badge-partner`}>
                {isFR ? 'Enchère partenaire' : 'Partner Auction'}
              </Badge>
            ) : listing?.seller_account_type === 'individual' ? (
              <Badge className="bg-emerald-500 text-white border-0 text-[10px] font-bold px-2 py-0.5" data-testid={`lot-card-${lot.lot_number}-badge-tax-free`}>
                {isFR ? 'Sans taxe' : 'Tax Free'}
              </Badge>
            ) : null}
          </div>

          {/* Bug 4 — TOP-CENTER/LEFT countdown chip: always red, pulse if <1h */}
          {endTime && !isEnded && (
            <div className="absolute top-2.5 left-1/2 -translate-x-1/2" data-testid={`lot-card-${lot.lot_number}-countdown`}>
              <Badge className={`${countdownColor(timeLeft)} border-0 text-[10px] font-mono font-bold px-2 py-0.5 shadow-md flex items-center gap-1`}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                <Countdown
                  date={endTime}
                  renderer={({ days, hours, minutes, seconds }) => (
                    days > 0 ? `${days}d ${hours}h` : hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m ${seconds}s`
                  )}
                />
              </Badge>
            </div>
          )}

          {/* Bug 3 — TOP-RIGHT wishlist heart, PERFECTLY centered in a 36×36 white circle */}
          <div
            className="absolute top-2.5 right-2.5 wishlist-btn-wrapper"
            data-stop-click
            data-testid={`lot-card-${lot.lot_number}-watchlist`}
          >
            <div
              className="flex items-center justify-center rounded-full bg-white dark:bg-slate-900 shadow-md p-0"
              style={{ width: 36, height: 36, lineHeight: 1 }}
            >
              <WatchlistButton
                itemId={`${auctionId}:${lot.lot_number}`}
                itemType="lot"
                size="sm"
                showLabel={false}
              />
            </div>
          </div>
        </div>

        {/* Body — BidSpotter style */}
        <div className="p-3 space-y-1.5">
          <div className="flex items-baseline gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
            <span className="font-mono font-semibold">#{lot.lot_number}</span>
            {location && (<><span>·</span><MapPin className="h-3 w-3 inline flex-shrink-0" /><span className="truncate">{location}</span></>)}
          </div>

          <h3 className="text-sm font-semibold text-slate-900 dark:text-white line-clamp-2 leading-snug" data-testid={`lot-card-${lot.lot_number}-title`}>
            {title}
          </h3>

          {/* Bug 6 — Inline bid input row */}
          {!isEnded && (
            <div className="pt-1 space-y-1.5" data-stop-click>
              <div className="flex gap-2 items-center">
                <div className="relative flex-1 min-w-0">
                  <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs font-bold pointer-events-none">$</span>
                  <input
                    type="number"
                    min={nextBid}
                    step={step}
                    inputMode="numeric"
                    placeholder={`Min ${formatCurrency(nextBid)}`}
                    value={bidInput}
                    onChange={(e) => { setBidInput(e.target.value); setBidError(''); }}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full pl-6 pr-2 py-1.5 border-2 border-slate-200 dark:border-slate-700 rounded-lg text-xs font-semibold focus:border-cyan-500 focus:outline-none bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                    data-testid={`lot-card-${lot.lot_number}-bid-input`}
                  />
                </div>
                <Button
                  size="sm"
                  disabled={placing}
                  onClick={handleQuickBid}
                  className="bg-cyan-600 hover:bg-cyan-700 text-white font-bold px-3 py-1.5 rounded-lg text-xs whitespace-nowrap disabled:opacity-50 h-auto min-w-0 flex-shrink-0"
                  data-testid={`lot-card-${lot.lot_number}-bid`}
                >
                  <Gavel className="h-3 w-3 mr-1 inline" />
                  {isFR ? 'Enchérir' : 'Bid'}
                </Button>
              </div>
              {bidError && (
                <div className="text-[10px] text-rose-600 dark:text-rose-400 font-semibold px-1" data-testid={`lot-card-${lot.lot_number}-bid-error`}>
                  {bidError}
                </div>
              )}
              <div className="flex justify-between items-center text-[10px] text-slate-500 dark:text-slate-400 px-1">
                <span>
                  {isFR ? 'Actuelle' : 'Current'}:{' '}
                  <strong className="text-slate-900 dark:text-white font-mono" data-testid={`lot-card-${lot.lot_number}-current-bid`}>
                    {formatCurrency(currentPrice)} {currency}
                  </strong>
                </span>
                <span>{lot.bid_count || 0} {(lot.bid_count === 1 ? (isFR ? 'enchère' : 'bid') : (isFR ? 'enchères' : 'bids'))}</span>
              </div>
            </div>
          )}
          {isEnded && (
            <div className="flex justify-between items-center py-1">
              <div>
                <div className="text-[9px] uppercase tracking-wide text-slate-500 dark:text-slate-400 font-semibold">
                  {isFR ? 'Enchère finale' : 'Final Bid'}
                </div>
                <div className="text-base font-bold text-slate-900 dark:text-white font-mono">
                  {formatCurrency(currentPrice)} {currency}
                </div>
              </div>
              <Badge className="bg-slate-500 text-white">{isFR ? 'TERMINÉ' : 'ENDED'}</Badge>
            </div>
          )}

          {/* Bug 1 — Secondary actions row: Auto-Bid + Fees. flex-1 min-w-0 so
              the labels never wrap even at 280 px card width. */}
          {!isEnded && (
            <div className="flex gap-1.5 pt-1" data-stop-click>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 min-w-0 h-8 px-2 text-[11px] font-semibold whitespace-nowrap overflow-hidden text-ellipsis"
                onClick={(e) => {
                  e.stopPropagation();
                  if (onOpenAutoBid) onOpenAutoBid(lot);
                  else setAutoBidOpen(true);
                }}
                data-testid={`lot-card-${lot.lot_number}-auto-bid`}
              >
                <Bot className="h-3 w-3 mr-1 flex-shrink-0" />
                <span className="truncate">{isFR ? 'Auto-enchère' : 'Auto-Bid'}</span>
              </Button>
              <Popover onOpenChange={(o) => { if (o) loadFees(); }}>
                <PopoverTrigger asChild>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 min-w-0 h-8 px-2 text-[11px] font-semibold whitespace-nowrap overflow-hidden text-ellipsis"
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`lot-card-${lot.lot_number}-fees-btn`}
                    aria-label={isFR ? 'Frais additionnels' : 'Additional fees'}
                  >
                    <Info className="h-3 w-3 mr-1 flex-shrink-0" />
                    <span className="truncate">{isFR ? 'Frais' : 'Fees'}</span>
                  </Button>
                </PopoverTrigger>
                <PopoverContent side="top" className="w-72 p-3" data-testid={`lot-card-${lot.lot_number}-fees-popover`} onClick={(e) => e.stopPropagation()}>
                  <div className="text-[11px] font-semibold text-slate-900 dark:text-white mb-2 flex items-center justify-between">
                    <span>{isFR ? 'Détail des frais' : 'Fee Breakdown'}</span>
                    {feesPreview && (
                      <Badge className={feesPreview.is_private_sale ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-amber-100 text-amber-800 border-amber-200'}>
                        {feesPreview.is_private_sale
                          ? (isFR ? 'Sans taxe' : 'Tax-Free')
                          : (isFR ? 'Taxable' : 'Taxable')}
                      </Badge>
                    )}
                  </div>
                  {feesLoading || !feesPreview ? (
                    <div className="text-[11px] text-slate-500 dark:text-slate-400">
                      {isFR ? 'Chargement…' : 'Loading…'}
                    </div>
                  ) : (
                    <ul className="space-y-1 text-[11px]" data-testid={`lot-card-${lot.lot_number}-fees-body`}>
                      {feesPreview.quantity > 1 && (
                        <li className="flex justify-between text-slate-500">
                          <span>{feesPreview.quantity} × {formatCurrency(feesPreview.unit_bid)}</span>
                          <span className="font-mono">{formatCurrency(feesPreview.subtotal)}</span>
                        </li>
                      )}
                      <li className="flex justify-between">
                        <span className="text-slate-600 dark:text-slate-400">
                          {feesPreview.quantity > 1
                            ? (isFR ? 'Sous-total' : 'Subtotal')
                            : (isFR ? 'Prix marteau' : 'Hammer')}
                        </span>
                        <span className="font-mono">{formatCurrency(feesPreview.subtotal)}</span>
                      </li>
                      {!feesPreview.is_private_sale && feesPreview.tax_on_hammer > 0 && (
                        <li className="flex justify-between">
                          <span className="text-slate-600 dark:text-slate-400">
                            {isFR ? `Taxe sur l'article (${feesPreview.tax_rate_pct}%)` : `Tax on item (${feesPreview.tax_rate_pct}%)`}
                          </span>
                          <span className="font-mono">{formatCurrency(feesPreview.tax_on_hammer)}</span>
                        </li>
                      )}
                      <li className="flex justify-between">
                        <span className="text-slate-600 dark:text-slate-400">
                          {isFR ? "Frais plateforme" : 'Platform Fee'} ({feesPreview.buyer_premium_rate_pct}%)
                        </span>
                        <span className="font-mono">{formatCurrency(feesPreview.buyer_premium_amount)}</span>
                      </li>
                      {feesPreview.tax_on_fee > 0 && (
                        <li className="flex justify-between">
                          <span className="text-slate-600 dark:text-slate-400">
                            {isFR ? `Taxe sur frais (${feesPreview.tax_rate_pct}%)` : `Tax on fee (${feesPreview.tax_rate_pct}%)`}
                          </span>
                          <span className="font-mono">{formatCurrency(feesPreview.tax_on_fee)}</span>
                        </li>
                      )}
                      <li className="flex justify-between pt-1 border-t border-slate-100 dark:border-slate-700 font-semibold">
                        <span className="text-slate-800 dark:text-slate-100">{isFR ? 'Total estimé' : 'Estimated total'}</span>
                        <span className="font-mono text-emerald-700 dark:text-emerald-400" data-testid={`lot-card-${lot.lot_number}-fees-total`}>
                          {formatCurrency(feesPreview.estimated_total)}
                        </span>
                      </li>
                      <li className="text-[10px] text-slate-500 dark:text-slate-400 pt-1">
                        {feesPreview.is_private_sale
                          ? (isFR ? '✓ Sans taxe — la taxe s\'applique uniquement aux frais de plateforme' : '✓ Tax-Free item — taxes apply only to platform fees')
                          : (isFR ? '⚠️ Article taxable — la taxe s\'applique au prix total' : '⚠️ Taxable item — tax applies to total purchase price')}
                      </li>
                    </ul>
                  )}
                </PopoverContent>
              </Popover>
            </div>
          )}
        </div>
      </Card>

      {/* Local Auto-Bid modal if parent didn't provide one */}
      {!onOpenAutoBid && (
        <AutoBidModal
          open={autoBidOpen}
          onOpenChange={setAutoBidOpen}
          auctionId={auctionId}
          lot={lot}
          incrementInfo={incrementInfo}
          onSaved={() => { /* parent will re-fetch via event */ }}
        />
      )}

      {/* Bug 9 — Fullscreen image viewer on image click */}
      <GlobalImageViewer
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        images={images}
        startIndex={imgIdx}
      />
    </>
  );
}
