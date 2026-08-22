/**
 * iter368 — Dedicated Lot Detail page.
 *
 * Route: `/lots/:auctionId/lot/:lotNumber`
 *
 * Design goals (from user spec):
 *   • Optimised for BIDDING — large image gallery, big Current Bid,
 *     Next Valid Bid, countdown, bid history, actions.
 *   • Previous / Next lot navigation at the top; keyboard arrows are
 *     the desktop shortcut. Mobile navigates ONLY through the Prev/Next
 *     buttons — scroll and swipe gestures never change lots
 *     (iter500 fix). Buyer never needs to bounce back to the grid.
 *   • Returning to the grid restores scroll + filters + sort + search
 *     via history state (sessionStorage snapshot written by CompactLotCard
 *     is consumed by MultiItemListingDetailPage on mount).
 *   • All actions preserved: Watchlist, Compare, Auto-Bid, Share,
 *     Report Listing, Buy Now, plus badges (Private Sale, Featured,
 *     Tax-Free) and secondary blocks (Description, Terms, Docs, Seller).
 *
 * We deliberately reuse existing UI primitives (SafeImage, WatchlistButton,
 * ShareButton, CompareCheckbox, ReportListingButton, BidHistory) so this
 * page inherits every prior fix (privacy alias, escrow rendering, tax-free
 * badge logic).
 */
import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
  ChevronLeft, ChevronRight, ArrowLeft, ChevronUp, ChevronDown,
  Clock, Gavel, Flag, Share2, Bot, Zap, ShieldCheck, FileText,
  MapPin, User, Loader2, TrendingUp, Info,
} from 'lucide-react';
import Countdown from 'react-countdown';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency } from '../utils/currencyFormatter';
import { extractErrorMessage } from '../utils/errorHandler';
import SafeImage from '../components/SafeImage';
import GlobalImageViewer from '../components/GlobalImageViewer';
import WatchlistButton from '../components/WatchlistButton';
import ShareButton from '../components/ShareButton';
import { CompareCheckbox } from '../components/CompareBar';
import MaskedBidHistory from '../components/MaskedBidHistory';
import AutoBidModal from '../components/AutoBidModal';
import SanitizedHtml from '../components/SanitizedHtml';
import AcceptedPaymentMethodsCard, { resolveAcceptedMethods } from '../components/AcceptedPaymentMethodsCard';
import { computeDisplayPrice } from '../utils/priceUtils';
import { LangLink } from '../components/LangLink';

const API = API_BASE;

export default function LotDetailPage() {
  const { auctionId, lotNumber: lotNumberParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, token } = useAuth();
  const { i18n, t } = useTranslation();
  const isFR = i18n.language?.startsWith('fr');

  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [incrementInfo, setIncrementInfo] = useState(null);
  const [imgIdx, setImgIdx] = useState(0);
  const [bidAmount, setBidAmount] = useState('');
  // iter369 — real Auto-Bid modal + live fee preview + lightbox.
  const [autoBidOpen, setAutoBidOpen] = useState(false);
  const [feesPreview, setFeesPreview] = useState(null);
  const [feesOpen, setFeesOpen] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  // iter484.2 — Buyer must acknowledge accepted payment methods
  // BEFORE placing a bid. Reset when the lot changes.
  const [paymentAck, setPaymentAck] = useState(false);

  const lotNumber = Number(lotNumberParam);
  const lot = useMemo(() => (listing?.lots || []).find((l) => l.lot_number === lotNumber) || null, [listing, lotNumber]);
  const lotIndex = useMemo(() => (listing?.lots || []).findIndex((l) => l.lot_number === lotNumber), [listing, lotNumber]);
  const prevLot = lotIndex > 0 ? listing.lots[lotIndex - 1] : null;
  const nextLot = lotIndex >= 0 && lotIndex < (listing?.lots?.length || 0) - 1 ? listing.lots[lotIndex + 1] : null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [listingRes, incRes] = await Promise.all([
          axios.get(`${API}/multi-item-listings/${auctionId}`),
          axios.get(`${API}/multi-item-listings/${auctionId}/increment-info`).catch(() => null),
        ]);
        if (cancelled) return;
        setListing(listingRes.data);
        if (incRes) setIncrementInfo(incRes.data);
      } catch (e) {
        if (!cancelled) setError(extractErrorMessage(e) || 'Failed to load auction');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [auctionId]);

  // iter369 — Live current-bid polling every 5 s (per user spec).
  useEffect(() => {
    if (!auctionId || !lotNumber) return;
    const tick = async () => {
      try {
        const res = await axios.get(`${API}/multi-item-listings/${auctionId}`, { timeout: 6000 });
        if (res.data) setListing((prev) => (
          // Only replace when the polled snapshot is newer.
          !prev || (res.data.updated_at || '') >= (prev.updated_at || '') ? res.data : prev
        ));
      } catch { /* ignore transient */ }
    };
    const t = setInterval(() => { if (!document.hidden) tick(); }, 5000);
    return () => clearInterval(t);
  }, [auctionId, lotNumber]);

  // iter369 — Fee preview (buyer-premium hierarchy, taxes, deposit) whenever
  // the lot changes or user auth changes.
  useEffect(() => {
    if (!lot || !auctionId) return;
    let cancelled = false;
    const url = `${API}/multi-item-listings/${auctionId}/lots/${lot.lot_number}/fees-preview`;
    axios
      .get(url, {
        params: { bid_amount: Number(lot.current_price ?? lot.starting_price ?? 0) },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 8000,
      })
      .then((res) => { if (!cancelled) setFeesPreview(res.data); })
      .catch(() => { /* non-fatal — collapsible just hides preview */ });
    return () => { cancelled = true; };
  }, [auctionId, lot?.lot_number, user?.subscription_tier, token, lot]);

  useEffect(() => { setImgIdx(0); setPaymentAck(false); }, [lotNumber]);

  // iter368 — Compute minimum increment via the server-derived schedule.
  // Single source of truth: same ladder used by the backend enforcement.
  const getMinIncrement = useCallback((currentBid) => {
    if (!incrementInfo) return 5;
    if (incrementInfo.increment_option === 'fixed' && incrementInfo.fixed_increment) {
      return Number(incrementInfo.fixed_increment);
    }
    const sched = incrementInfo.schedule || [];
    const bid = Number(currentBid || 0);
    for (const row of sched) {
      const lo = Number(row.min ?? 0);
      const hi = row.max == null ? Infinity : Number(row.max);
      if (bid >= lo && bid < hi) return Number(row.step);
    }
    return sched.length ? Number(sched[sched.length - 1].step) : 5;
  }, [incrementInfo]);

  const currentBid = Number(lot?.current_price ?? lot?.starting_price ?? 0);
  const nextValidBid = currentBid + getMinIncrement(currentBid);
  // Three-pill Quick Bid suggestions, all derived from the same ladder.
  const bidSuggestions = useMemo(() => {
    if (!lot) return [];
    const b1 = nextValidBid;
    const b2 = b1 + getMinIncrement(b1);
    const b3 = b2 + getMinIncrement(b2);
    return [b1, b2, b3];
  }, [lot, nextValidBid, getMinIncrement]);

  const goToLot = useCallback((num) => {
    if (num == null) return;
    navigate(`/lots/${auctionId}/lot/${num}`);
  }, [auctionId, navigate]);

  // Return to grid + restore scroll (relies on sessionStorage snapshot).
  const backToGrid = useCallback(() => {
    navigate(`/lots/${auctionId}?lot=${lotNumber}`);
  }, [auctionId, lotNumber, navigate]);

  // Keyboard arrows nav — iter368.
  useEffect(() => {
    const handler = (e) => {
      if (e.target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
      if (e.key === 'ArrowRight' && nextLot) goToLot(nextLot.lot_number);
      if (e.key === 'ArrowLeft' && prevLot) goToLot(prevLot.lot_number);
      if (e.key === 'Escape') backToGrid();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [nextLot, prevLot, goToLot, backToGrid]);

  // iter500 — Mobile scroll must NEVER trigger lot navigation.
  // The old swipe-to-navigate handlers hijacked scroll gestures and
  // pushed the user to another lot. Removed entirely; the Prev/Next
  // buttons at the top and bottom of the page are now the only way to
  // change lots. Keyboard arrows above still work (desktop only —
  // ArrowLeft/ArrowRight keys don't fire on scroll).

  const handlePlaceBid = async (amount) => {
    if (!user) { navigate('/auth'); return; }
    if (!amount || amount < nextValidBid) {
      toast.error(t('bid.mustBeAtLeast', { defaultValue: 'Bid must be at least {{amount}}', amount: formatCurrency(nextValidBid) }));
      return;
    }
    // iter484.2 — Buyer must acknowledge the seller's accepted payment
    // methods before the bid is submitted. Server-side enforcement of
    // the actual method allowlist still runs at checkout time.
    if (!paymentAck) {
      toast.error(isFR
        ? 'Veuillez confirmer que vous comprenez les modes de paiement acceptés avant d\u2019enchérir.'
        : 'Please acknowledge the accepted payment methods before placing a bid.');
      return;
    }
    try {
      await axios.post(
        `${API}/multi-item-listings/${auctionId}/lots/${lotNumber}/bid`,
        { amount, bid_type: 'normal' },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } },
      );
      toast.success(t('bid.placed', 'Bid placed successfully!'));
      setBidAmount('');
      // Re-fetch to update current_price and highest_bidder_id.
      const res = await axios.get(`${API}/multi-item-listings/${auctionId}`);
      setListing(res.data);
    } catch (e) {
      // iter400 — use extractErrorMessage so bilingual Trust-Gate 403
      // envelopes render as a clean string (not a raw object → React #31).
      const { extractErrorMessage } = await import('../utils/errorHandler');
      toast.error(extractErrorMessage(e) || 'Failed to place bid');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="lot-detail-loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }
  if (error || !listing || !lot) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 text-center" data-testid="lot-detail-not-found">
        <Gavel className="h-12 w-12 text-slate-400 mb-3" />
        <h1 className="text-2xl font-bold mb-2">{isFR ? 'Lot introuvable' : 'Lot not found'}</h1>
        <p className="text-slate-600 dark:text-slate-400 mb-4">{error || (isFR ? 'Ce lot n\'existe pas ou a été retiré.' : 'That lot does not exist or was removed.')}</p>
        <Button onClick={() => navigate(`/lots/${auctionId}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          {isFR ? 'Retour aux lots' : 'Back to lots'}
        </Button>
      </div>
    );
  }

  const images = Array.isArray(lot.images) && lot.images.length > 0 ? lot.images : [];
  const endTime = lot.lot_end_time ? new Date(lot.lot_end_time).getTime() : null;
  const isEnded = (endTime && endTime <= Date.now()) || lot.lot_status === 'ended' || lot.lot_status === 'sold';
  const title = (isFR ? lot.title_fr : lot.title_en) || lot.title || '—';
  const description = (isFR ? lot.description_fr : lot.description_en) || lot.description || '';
  const dp = computeDisplayPrice({ ...lot, current_bid: lot.current_price ?? null });

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="lot-detail-page" data-lot-number={lot.lot_number}>
      {/* Top nav — Back + Previous / Next */}
      <div className="sticky top-0 z-30 bg-white/95 dark:bg-slate-950/95 backdrop-blur border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-6xl mx-auto px-4 py-2 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={backToGrid} data-testid="lot-detail-back-to-grid">
            <ArrowLeft className="h-4 w-4 mr-1" />
            <span className="hidden sm:inline">{isFR ? 'Retour à la grille' : 'Back to grid'}</span>
            <span className="sm:hidden">{isFR ? 'Grille' : 'Grid'}</span>
          </Button>
          <div className="flex-1 text-center text-[11px] text-slate-500 dark:text-slate-400 font-mono truncate">
            {listing.title} · #{lot.lot_number} / {listing.lots.length}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => goToLot(prevLot?.lot_number)}
            disabled={!prevLot}
            data-testid="lot-detail-prev"
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            <span className="hidden sm:inline">{isFR ? 'Précédent' : 'Prev'}</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => goToLot(nextLot?.lot_number)}
            disabled={!nextLot}
            data-testid="lot-detail-next"
          >
            <span className="hidden sm:inline">{isFR ? 'Suivant' : 'Next'}</span>
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT — Gallery + Description + Terms + Bid history */}
        <div className="lg:col-span-2 space-y-4">
          {/* Large image gallery */}
          <div className="rounded-xl overflow-hidden bg-black relative" style={{ aspectRatio: '4 / 3' }}>
            {images.length > 0 ? (
              <>
                <div className="absolute inset-0 flex items-center justify-center">
                  <SafeImage
                    src={images[imgIdx]}
                    alt={title}
                    className="w-full h-full object-contain cursor-zoom-in"
                    onClick={() => setLightboxOpen(true)}
                    data-testid="lot-detail-main-image"
                  />
                </div>
                {images.length > 1 && (
                  <>
                    <button className="absolute left-2 top-1/2 -translate-y-1/2 h-10 w-10 bg-black/60 text-white rounded-full flex items-center justify-center hover:bg-black/80 z-10" onClick={(e) => { e.stopPropagation(); setImgIdx((i) => (i - 1 + images.length) % images.length); }} data-testid="lot-detail-prev-image"><ChevronLeft className="h-5 w-5" /></button>
                    <button className="absolute right-2 top-1/2 -translate-y-1/2 h-10 w-10 bg-black/60 text-white rounded-full flex items-center justify-center hover:bg-black/80 z-10" onClick={(e) => { e.stopPropagation(); setImgIdx((i) => (i + 1) % images.length); }} data-testid="lot-detail-next-image"><ChevronRight className="h-5 w-5" /></button>
                    <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded font-mono z-10">{imgIdx + 1} / {images.length}</div>
                  </>
                )}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-6xl text-slate-500">🖼️</div>
            )}
          </div>

          {/* Thumbnail strip */}
          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
              {images.map((src, i) => (
                <button key={i} type="button" onClick={() => { setImgIdx(i); setLightboxOpen(true); }} className={`flex-shrink-0 h-14 w-14 rounded-lg overflow-hidden border-2 cursor-zoom-in ${i === imgIdx ? 'border-cyan-500' : 'border-transparent'}`} data-testid={`lot-detail-thumb-${i}`}>
                  <SafeImage src={src} alt={`thumb ${i}`} className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}

          {/* Badges + title + location */}
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {lot.is_promoted && <Badge className="bg-amber-500 text-white">★ {isFR ? 'Mis en avant' : 'Featured'}</Badge>}
              {lot.reserve_price != null && lot.reserve_price > 0 && <Badge className="bg-blue-600 text-white">{isFR ? 'Réserve' : 'Reserve'}</Badge>}
              {listing?.seller_account_type === 'individual' && <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-200">{isFR ? 'Sans taxe (Vente privée)' : 'Tax-Free (Private Sale)'}</Badge>}
              {listing?.is_private_sale && <Badge className="bg-purple-100 text-purple-800 border border-purple-200">{isFR ? 'Vente privée' : 'Private Sale'}</Badge>}
              <Badge variant="outline">{(lot.condition || '').replace('_', ' ').toUpperCase()}</Badge>
              {lot.quantity > 1 && <Badge variant="outline">{isFR ? 'Qté' : 'Qty'}: {lot.quantity}</Badge>}
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white" data-testid="lot-detail-title">
              #{lot.lot_number} · {title}
            </h1>
            {(lot.seller_city || listing.city) && (
              <div className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400">
                <MapPin className="h-3.5 w-3.5" />
                {[lot.seller_city || listing.city, lot.seller_province || listing.region].filter(Boolean).join(', ')}
              </div>
            )}
          </div>

          {/* iter369 — Auction Summary block: opening bid, current bid, leader,
              ends in, bids, lot #, auction name, seller, location. */}
          <Card data-testid="lot-detail-summary">
            <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-y-2 gap-x-6 text-sm">
              {[
                [isFR ? 'Enchère de départ' : 'Opening Bid', formatCurrency(lot.starting_price ?? 0)],
                [isFR ? 'Enchère courante' : 'Current Bid',
                  <span key="cb" className="font-semibold text-emerald-700 dark:text-emerald-400 font-mono">
                    {formatCurrency(currentBid)}
                  </span>],
                [isFR ? 'Meneur' : 'Current Leader',
                  <span key="lead" data-testid="lot-detail-leader-initials">
                    {feesPreview?.leading_bidder_initials || '—'}
                  </span>],
                [isFR ? 'Se termine dans' : 'Ends In',
                  endTime && !isEnded
                    ? <Countdown key="end" date={endTime} renderer={({ days, hours, minutes, seconds }) =>
                        <span data-testid="lot-detail-summary-countdown">{days}d {hours}h {minutes}m {seconds}s</span>} />
                    : <span key="end" className="text-slate-500">{isFR ? 'Terminé' : 'Ended'}</span>],
                [isFR ? 'Enchères' : 'Bids', `${lot.bid_count || 0} · ${lot.unique_bidders || 0} ${isFR ? 'enchérisseurs' : 'bidders'}`],
                [isFR ? 'Lot' : 'Lot', `#${lot.lot_number} of ${listing.lots.length}`],
                [isFR ? 'Enchère' : 'Auction', listing.title],
                [isFR ? 'Vendeur' : 'Seller', listing.seller_display_name || listing.seller_name || '—'],
                [isFR ? 'Emplacement' : 'Location',
                  [lot.seller_city || listing.city, lot.seller_province || listing.region].filter(Boolean).join(', ') || '—'],
              ].map(([lbl, val], i) => (
                <div key={i} className="flex justify-between gap-3">
                  <span className="text-slate-500 dark:text-slate-400">{lbl}</span>
                  <span className="font-medium text-slate-800 dark:text-slate-100 text-right truncate max-w-[60%]">{val}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* iter369 — Multi-unit notice: quantity > 1 */}
          {lot.quantity > 1 && (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 p-3 text-xs text-amber-900 dark:text-amber-200" data-testid="lot-detail-multi-unit-notice">
              {isFR
                ? <>Ce lot contient <strong>{lot.quantity}</strong> unités. La valeur totale du lot correspond à l&apos;enchère courante multipliée par la quantité ({formatCurrency(currentBid)} × {lot.quantity} = <strong>{formatCurrency(currentBid * lot.quantity)}</strong>). Vous enchérissez le prix <strong>par unité</strong>.</>
                : <>This lot contains <strong>{lot.quantity}</strong> units. The total lot value reflects the current bid multiplied by quantity ({formatCurrency(currentBid)} × {lot.quantity} = <strong>{formatCurrency(currentBid * lot.quantity)}</strong>). You are bidding the <strong>per-unit</strong> price.</>}
            </div>
          )}

          {/* iter369 — Fee Breakdown (collapsible, buyer-tier aware, single source of truth) */}
          {feesPreview && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden" data-testid="lot-detail-fee-breakdown">
              <button
                type="button"
                onClick={() => setFeesOpen((v) => !v)}
                className="w-full flex items-center gap-2 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                data-testid="lot-detail-fee-breakdown-toggle"
              >
                <Info className="h-4 w-4 text-cyan-600" />
                <span className="text-sm font-semibold flex-1 text-left">
                  {isFR ? 'Voir le détail des frais' : 'View Fee Breakdown'}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-slate-500">
                  {feesPreview.buyer_premium_rate_pct}% BP
                </span>
              </button>
              {feesOpen && (
                <div className="border-t border-slate-200 dark:border-slate-800 p-4 space-y-2 text-sm" data-testid="lot-detail-fee-breakdown-body">
                  {[
                    [isFR ? 'Statut fiscal' : 'Tax Status',
                      feesPreview.is_private_sale
                        ? <Badge key="tx" className="bg-emerald-100 text-emerald-800 border border-emerald-200">{isFR ? 'Sans taxe (Vente privée)' : 'Tax-Free (Private Sale)'}</Badge>
                        : <span key="tx">{isFR ? 'Selon province' : 'Per province'}</span>],
                    [`${isFR ? "Prime de l'acheteur" : "Buyer's Premium"} (${feesPreview.buyer_premium_rate_pct}%)`,
                      formatCurrency(feesPreview.buyer_premium_amount)],
                    [isFR ? 'Taxes' : 'Taxes',
                      feesPreview.is_private_sale ? formatCurrency(0) : formatCurrency(feesPreview.tax_amount)],
                    [isFR ? 'Dépôt requis' : 'Deposit Required',
                      feesPreview.deposit_required > 0
                        ? formatCurrency(feesPreview.deposit_required)
                        : (isFR ? 'Aucun dépôt requis' : 'No deposit required')],
                    [isFR ? 'Paiement' : 'Payment',
                      (() => {
                        const acc = resolveAcceptedMethods(listing);
                        if (acc.length === 0) {
                          return <span key="pay" className="text-xs text-amber-600">{isFR ? 'Aucun mode configuré' : 'None configured'}</span>;
                        }
                        return (
                          <span key="pay" className="text-xs" data-testid="lot-detail-fee-payment-methods-summary">
                            {acc.length} {isFR ? (acc.length > 1 ? 'modes acceptés' : 'mode accepté') : (acc.length > 1 ? 'methods accepted' : 'method accepted')}
                          </span>
                        );
                      })()],
                    [<strong key="est">{isFR ? 'Total estimé' : 'Estimated Total'}</strong>,
                      <strong key="est-v" className="text-emerald-700 dark:text-emerald-400 font-mono" data-testid="lot-detail-fee-estimated-total">
                        {formatCurrency(feesPreview.estimated_total)} {feesPreview.currency}
                      </strong>],
                  ].map(([lbl, val], i) => (
                    <div key={i} className="flex justify-between gap-3">
                      <span className="text-slate-600 dark:text-slate-400">{lbl}</span>
                      <span className="text-slate-800 dark:text-slate-100 text-right">{val}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* iter369 — Buy Now section (only when available) */}
          {lot.buy_now_enabled && lot.buy_now_price != null && !isEnded && (
            <div className="rounded-xl border-2 border-cyan-500/30 bg-gradient-to-r from-cyan-50 to-blue-50 dark:from-cyan-950/40 dark:to-blue-950/40 p-4 flex items-center gap-3" data-testid="lot-detail-buy-now-section">
              <Zap className="h-6 w-6 text-cyan-600 flex-shrink-0" />
              <div className="flex-1 text-sm">
                <div className="font-bold text-cyan-900 dark:text-cyan-200">
                  {isFR ? 'Achat immédiat disponible' : 'Buy Now Available'} — {formatCurrency(lot.buy_now_price)}
                </div>
                <div className="text-xs text-cyan-700 dark:text-cyan-300">
                  {isFR ? "Sautez les enchères — achetez tout de suite au prix fixe." : 'Skip the bidding — purchase instantly at the fixed price.'}
                </div>
              </div>
              <Button
                className="bg-cyan-600 hover:bg-cyan-700 text-white"
                onClick={() => navigate(`/lots/${auctionId}?lot=${lot.lot_number}&buy_now=1`)}
                data-testid="lot-detail-buy-now-section-cta"
              >
                {isFR ? 'Acheter' : 'Buy Now'}
              </Button>
            </div>
          )}

          {/* iter369 — Deposit notice (dynamic per auction) */}
          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-start gap-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 p-3" data-testid="lot-detail-deposit-notice">
            <ShieldCheck className="h-4 w-4 text-slate-400 flex-shrink-0 mt-0.5" />
            <span>
              {feesPreview?.deposit_required > 0 ? (
                isFR
                  ? <>Un dépôt de <strong>{formatCurrency(feesPreview.deposit_required)}</strong> est requis pour enchérir sur ce lot. Il sera déduit du total en cas de gain, sinon libéré automatiquement.</>
                  : <>A deposit of <strong>{formatCurrency(feesPreview.deposit_required)}</strong> is required to bid on this lot. It will be applied to your winning total, otherwise released automatically.</>
              ) : (
                isFR
                  ? <>Aucun dépôt requis pour enchérir sur cette enchère. Consultez la carte « Modes de paiement acceptés » pour les modes offerts par le vendeur. Tout dépôt déjà payé sera déduit de votre total gagnant en CAD.</>
                  : <>No deposit is required to bid on this auction. See the &ldquo;Accepted Payment Methods&rdquo; card below for the options offered by this seller. Any deposit you already paid will be deducted from your winning total in CAD.</>
              )}
            </span>
          </div>

          {/* iter484.2 — Buyer-facing Accepted Payment Methods card.
              Dynamic (data-driven from listing.accepted_payment_methods),
              bilingual, replaces the hardcoded "BidVex Stripe checkout"
              copy that previously misled buyers on multi-method auctions. */}
          <AcceptedPaymentMethodsCard listing={listing} />

          {/* Description */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">{isFR ? 'Description' : 'Description'}</CardTitle></CardHeader>
            <CardContent className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap" data-testid="lot-detail-description">
              {description || <em>{isFR ? 'Aucune description fournie.' : 'No description provided.'}</em>}
            </CardContent>
          </Card>

          {/* Auction terms — iter369: sanitized HTML render (no raw tags visible) */}
          {(listing.auction_terms_en || listing.auction_terms_fr) && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><ShieldCheck className="h-4 w-4" />{isFR ? "Modalités de l'enchère" : 'Auction Terms'}</CardTitle></CardHeader>
              <CardContent data-testid="lot-detail-terms">
                <SanitizedHtml
                  html={(isFR ? listing.auction_terms_fr : listing.auction_terms_en) || listing.auction_terms_en}
                  className="text-xs text-slate-700 dark:text-slate-300 max-h-64 overflow-y-auto prose prose-sm dark:prose-invert max-w-none"
                />
              </CardContent>
            </Card>
          )}

          {/* Shipping + Pickup info */}
          {(listing.shipping_info || listing.pickup_locations) && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base">{isFR ? 'Livraison et retrait' : 'Shipping & Pickup'}</CardTitle></CardHeader>
              <CardContent className="text-xs text-slate-700 dark:text-slate-300 space-y-1" data-testid="lot-detail-shipping-pickup">
                {listing.shipping_info && (
                  <div><span className="font-semibold">{isFR ? 'Livraison :' : 'Shipping:'}</span> {typeof listing.shipping_info === 'string' ? listing.shipping_info : JSON.stringify(listing.shipping_info)}</div>
                )}
                {Array.isArray(listing.pickup_locations) && listing.pickup_locations.length > 0 && (
                  <div><span className="font-semibold">{isFR ? 'Retrait :' : 'Pickup:'}</span> {listing.pickup_locations.map((p) => p.address || p.name).filter(Boolean).join(' · ')}</div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Documents */}
          {listing.documents && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><FileText className="h-4 w-4" />{isFR ? 'Documents' : 'Documents'}</CardTitle></CardHeader>
              <CardContent className="text-xs text-slate-700 dark:text-slate-300" data-testid="lot-detail-documents">
                {typeof listing.documents === 'string'
                  ? listing.documents
                  : Object.entries(listing.documents).map(([k, v]) => (
                      <div key={k}><span className="font-semibold">{k}:</span> {String(v)}</div>
                    ))}
              </CardContent>
            </Card>
          )}

          {/* Bid history — iter369: masked initials + IP octets 1+4 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                {isFR ? "Historique des enchères" : 'Bid History'}
              </CardTitle>
            </CardHeader>
            <CardContent data-testid="lot-detail-bid-history">
              <MaskedBidHistory auctionId={auctionId} lotNumber={lot.lot_number} />
            </CardContent>
          </Card>
        </div>

        {/* RIGHT — Bidding panel + actions + seller */}
        <div className="space-y-4">
          {/* Bidding panel */}
          <Card className="border-cyan-200 dark:border-cyan-900 shadow-sm">
            <CardContent className="p-4 space-y-3">
              {/* Countdown */}
              {endTime && !isEnded && (
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="h-4 w-4 text-rose-600" />
                  <span className="font-semibold text-rose-600">
                    <Countdown date={endTime} renderer={({ days, hours, minutes, seconds }) => (
                      days > 0 ? `${days}d ${hours}h ${minutes}m` : `${hours}h ${minutes}m ${seconds}s`
                    )} />
                  </span>
                </div>
              )}
              {isEnded && (
                <Badge className="bg-slate-500 text-white text-xs">{isFR ? 'Enchère terminée' : 'Auction ended'}</Badge>
              )}
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">{isFR ? 'Enchère actuelle' : 'Current Bid'}</div>
                <div className="text-3xl font-bold text-emerald-700 dark:text-emerald-400 font-mono" data-testid="lot-detail-current-bid">{formatCurrency(dp.totalPrice ?? currentBid)}</div>
                {dp.isMultiplied && (
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">({formatCurrency(dp.unitPrice)} × {dp.quantity})</div>
                )}
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">{isFR ? 'Prochaine enchère valide' : 'Next Valid Bid'}</div>
                <div className="text-lg font-bold text-slate-900 dark:text-white font-mono" data-testid="lot-detail-next-bid">{formatCurrency(nextValidBid)}</div>
              </div>

              {/* Three Quick Bid pills — amount pickers that populate the
                  custom-bid input; the actual submission happens via the
                  "Place Bid" button below. iter485 UX fix: previously these
                  pills submitted the bid on click, which mismatched the
                  "select amount → confirm ack → place bid" mental model
                  and left users stuck when the payment-ack was checked
                  AFTER a pill click. */}
              {!isEnded && (
                <div className="grid grid-cols-3 gap-1.5" data-testid="lot-detail-quick-bid">
                  {bidSuggestions.map((amt, i) => (
                    <Button
                      key={i}
                      size="sm"
                      variant="outline"
                      className="text-xs font-mono h-8"
                      onClick={() => setBidAmount(String(amt))}
                      data-testid={`lot-detail-quick-bid-${i}`}
                    >
                      {formatCurrency(amt)}
                    </Button>
                  ))}
                </div>
              )}

              {/* Custom bid input */}
              {!isEnded && (
                <div className="space-y-1.5">
                  <Input
                    type="number"
                    min={nextValidBid}
                    step="1"
                    placeholder={`${isFR ? 'Min' : 'Min'}: ${formatCurrency(nextValidBid)}`}
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                    data-testid="lot-detail-bid-input"
                  />
                  {/* iter484.2 — Pre-bid acknowledgement of accepted
                      payment methods. Must be checked before the buyer
                      can submit a bid. */}
                  <label
                    className="flex items-start gap-2 text-[11px] leading-snug text-slate-600 dark:text-slate-300 cursor-pointer select-none px-1 py-1"
                    data-testid="lot-detail-payment-ack-label"
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-3.5 w-3.5 accent-emerald-600 flex-shrink-0"
                      checked={paymentAck}
                      onChange={(e) => setPaymentAck(e.target.checked)}
                      data-testid="bid-payment-ack-checkbox"
                    />
                    <span>
                      {isFR
                        ? 'Je comprends les modes de paiement acceptés pour cette enchère et j\u2019accepte de compléter le paiement en utilisant l\u2019un des modes approuvés par le vendeur si je gagne.'
                        : 'I understand the accepted payment methods for this auction and agree to complete payment using one of the seller\u2019s approved methods if I win.'}
                    </span>
                  </label>
                  <Button
                    className="w-full h-9 bg-emerald-600 hover:bg-emerald-700 text-white font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handlePlaceBid(Number(bidAmount))}
                    disabled={!paymentAck || !bidAmount || Number(bidAmount) < nextValidBid}
                    data-testid="lot-detail-place-bid"
                  >
                    <Gavel className="h-4 w-4 mr-1.5" />
                    {isFR ? 'Placer une enchère' : 'Place Bid'}
                  </Button>
                </div>
              )}

              {/* Buy Now */}
              {lot.buy_now_enabled && lot.buy_now_price != null && !isEnded && (
                <Button
                  variant="secondary"
                  className="w-full bg-cyan-600 hover:bg-cyan-700 text-white"
                  onClick={() => navigate(`/lots/${auctionId}?lot=${lot.lot_number}&buy_now=1`)}
                  data-testid="lot-detail-buy-now"
                >
                  <Zap className="h-4 w-4 mr-1.5" />
                  {isFR ? 'Acheter maintenant' : 'Buy Now'} {formatCurrency(lot.buy_now_price)}
                </Button>
              )}

              {/* Auto-Bid — iter369 real modal (subscription-gated) */}
              {!isEnded && (
                <Button
                  variant="outline"
                  className="w-full h-9 text-xs"
                  onClick={() => setAutoBidOpen(true)}
                  data-testid="lot-detail-auto-bid"
                >
                  <Bot className="h-4 w-4 mr-1.5" />
                  {isFR ? "Configurer l'auto-enchère" : 'Auto-Bid Bot Setup'}
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Actions strip */}
          <Card>
            <CardContent className="p-3 flex flex-wrap items-center gap-2" data-testid="lot-detail-actions">
              <WatchlistButton itemId={`${auctionId}:${lot.lot_number}`} itemType="lot" size="sm" showLabel={true} />
              <CompareCheckbox item={{
                id: `${auctionId}:lot:${lot.lot_number}`,
                title: `${title} · #${lot.lot_number}`,
                image: images[0],
                images,
                current_price: currentBid,
                city: lot.seller_city || listing.city,
                region: lot.seller_province || listing.region,
                auction_id: auctionId,
                lot_number: lot.lot_number,
              }} section="lots" />
              <ShareButton url={`${window.location.origin}/lots/${auctionId}/lot/${lot.lot_number}`} title={`${title} · #${lot.lot_number}`} description={description} />
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  // Simple mailto for now — a dedicated report modal is P2.
                  const subj = encodeURIComponent(`Report: ${title} (${auctionId} lot ${lot.lot_number})`);
                  window.location.href = `mailto:trust@bidvex.com?subject=${subj}`;
                }}
                data-testid="lot-detail-report"
              >
                <Flag className="h-3.5 w-3.5 mr-1" />
                {isFR ? 'Signaler' : 'Report'}
              </Button>
            </CardContent>
          </Card>

          {/* Seller info */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><User className="h-4 w-4" />{isFR ? 'Vendeur' : 'Seller'}</CardTitle></CardHeader>
            <CardContent className="text-xs space-y-1 text-slate-700 dark:text-slate-300" data-testid="lot-detail-seller">
              <div className="font-semibold text-slate-900 dark:text-white">{listing.seller_display_name || listing.seller_name || (isFR ? 'Vendeur BidVex' : 'BidVex Seller')}</div>
              {listing.seller_account_type && (
                <div className="capitalize"><Badge variant="outline">{String(listing.seller_account_type).replace('_', ' ')}</Badge></div>
              )}
              <LangLink to={`/seller/${listing.seller_id}`} className="text-cyan-600 hover:underline text-xs">
                {isFR ? 'Voir le profil du vendeur →' : 'View seller profile →'}
              </LangLink>
            </CardContent>
          </Card>

          {/* Reserve status hint */}
          {lot.reserve_price != null && lot.reserve_price > 0 && (
            <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1" data-testid="lot-detail-reserve">
              <Info className="h-3.5 w-3.5" />
              {isFR
                ? (currentBid >= (lot.reserve_price || 0) ? 'La réserve est atteinte.' : 'La réserve n\'est pas encore atteinte.')
                : (currentBid >= (lot.reserve_price || 0) ? 'Reserve has been met.' : 'Reserve has not yet been met.')}
            </div>
          )}
        </div>
      </div>

      {/* Bottom nav — repeated Previous / Next for continuous browsing */}
      <div className="max-w-6xl mx-auto px-4 pb-8 flex items-center justify-between gap-2">
        <Button variant="outline" size="sm" onClick={() => goToLot(prevLot?.lot_number)} disabled={!prevLot} data-testid="lot-detail-prev-bottom">
          <ChevronLeft className="h-4 w-4 mr-1" />
          {isFR ? 'Lot précédent' : 'Previous Lot'}
        </Button>
        <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono hidden sm:block">
          {isFR ? 'Astuce: utilisez ← / → pour naviguer' : 'Tip: use ← / → to navigate'}
        </div>
        <Button variant="outline" size="sm" onClick={() => goToLot(nextLot?.lot_number)} disabled={!nextLot} data-testid="lot-detail-next-bottom">
          {isFR ? 'Lot suivant' : 'Next Lot'}
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>

      {/* iter369 — Real Auto-Bid modal */}
      <AutoBidModal
        open={autoBidOpen}
        onOpenChange={setAutoBidOpen}
        auctionId={auctionId}
        lot={lot}
        incrementInfo={incrementInfo}
        onSaved={() => {
          // Optimistically refetch the auction so bid_count + current_price update.
          axios.get(`${API}/multi-item-listings/${auctionId}`).then((res) => setListing(res.data)).catch(() => {});
        }}
      />

      {/* iter369 — Global fullscreen image viewer */}
      <GlobalImageViewer
        open={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
        images={images}
        startIndex={imgIdx}
      />
    </div>
  );
}
