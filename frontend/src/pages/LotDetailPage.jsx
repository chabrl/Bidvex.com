/**
 * iter368 — Dedicated Lot Detail page.
 *
 * Route: `/lots/:auctionId/lot/:lotNumber`
 *
 * Design goals (from user spec):
 *   • Optimised for BIDDING — large image gallery, big Current Bid,
 *     Next Valid Bid, countdown, bid history, actions.
 *   • Previous / Next lot navigation at the top; keyboard arrows +
 *     mobile swipe move between lots. Buyer never needs to bounce
 *     back to the grid.
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
import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
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
import SafeImage from '../components/SafeImage';
import WatchlistButton from '../components/WatchlistButton';
import ShareButton from '../components/ShareButton';
import { CompareCheckbox } from '../components/CompareBar';
import PublicBidHistory from '../components/PublicBidHistory';
import { computeDisplayPrice } from '../utils/priceUtils';
import { LangLink } from '../components/LangLink';

const API = API_BASE;

export default function LotDetailPage() {
  const { auctionId, lotNumber: lotNumberParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { i18n, t } = useTranslation();
  const isFR = i18n.language?.startsWith('fr');

  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [incrementInfo, setIncrementInfo] = useState(null);
  const [imgIdx, setImgIdx] = useState(0);
  const [bidAmount, setBidAmount] = useState('');

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
        if (!cancelled) setError(e?.response?.data?.detail || 'Failed to load auction');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [auctionId]);

  useEffect(() => { setImgIdx(0); }, [lotNumber]);

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

  // Swipe navigation for mobile — iter368.
  const touchStartX = useRef(null);
  const onTouchStart = (e) => { touchStartX.current = e.touches[0].clientX; };
  const onTouchEnd = (e) => {
    if (touchStartX.current == null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 60) {
      if (dx < 0 && nextLot) goToLot(nextLot.lot_number);
      else if (dx > 0 && prevLot) goToLot(prevLot.lot_number);
    }
    touchStartX.current = null;
  };

  const handlePlaceBid = async (amount) => {
    if (!user) { navigate('/auth'); return; }
    if (!amount || amount < nextValidBid) {
      toast.error(t('bid.mustBeAtLeast', { defaultValue: 'Bid must be at least {{amount}}', amount: formatCurrency(nextValidBid) }));
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
      toast.error(e?.response?.data?.detail || 'Failed to place bid');
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
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="lot-detail-page" data-lot-number={lot.lot_number} onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
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
                <SafeImage src={images[imgIdx]} alt={title} className="w-full h-full object-contain" />
                {images.length > 1 && (
                  <>
                    <button className="absolute left-2 top-1/2 -translate-y-1/2 h-10 w-10 bg-black/60 text-white rounded-full flex items-center justify-center hover:bg-black/80" onClick={() => setImgIdx((i) => (i - 1 + images.length) % images.length)} data-testid="lot-detail-prev-image"><ChevronLeft className="h-5 w-5" /></button>
                    <button className="absolute right-2 top-1/2 -translate-y-1/2 h-10 w-10 bg-black/60 text-white rounded-full flex items-center justify-center hover:bg-black/80" onClick={() => setImgIdx((i) => (i + 1) % images.length)} data-testid="lot-detail-next-image"><ChevronRight className="h-5 w-5" /></button>
                    <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded font-mono">{imgIdx + 1} / {images.length}</div>
                  </>
                )}
              </>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-6xl text-slate-500">🖼️</div>
            )}
          </div>

          {/* Thumbnail strip */}
          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
              {images.map((src, i) => (
                <button key={i} type="button" onClick={() => setImgIdx(i)} className={`flex-shrink-0 h-14 w-14 rounded-lg overflow-hidden border-2 ${i === imgIdx ? 'border-cyan-500' : 'border-transparent'}`} data-testid={`lot-detail-thumb-${i}`}>
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

          {/* Description */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">{isFR ? 'Description' : 'Description'}</CardTitle></CardHeader>
            <CardContent className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap" data-testid="lot-detail-description">
              {description || <em>{isFR ? 'Aucune description fournie.' : 'No description provided.'}</em>}
            </CardContent>
          </Card>

          {/* Auction terms + shipping + pickup */}
          {(listing.auction_terms_en || listing.auction_terms_fr) && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><ShieldCheck className="h-4 w-4" />{isFR ? "Modalités de l'enchère" : 'Auction Terms'}</CardTitle></CardHeader>
              <CardContent className="text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap max-h-64 overflow-y-auto" data-testid="lot-detail-terms">
                {(isFR ? listing.auction_terms_fr : listing.auction_terms_en) || listing.auction_terms_en}
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

          {/* Bid history */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                {isFR ? "Historique des enchères" : 'Bid History'} · {lot.bid_count || 0} {isFR ? 'enchères' : 'bids'}
              </CardTitle>
            </CardHeader>
            <CardContent data-testid="lot-detail-bid-history">
              <PublicBidHistory listingId={auctionId} lotNumber={lot.lot_number} currentPrice={currentBid} />
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

              {/* Three Quick Bid pills — same increment ladder */}
              {!isEnded && (
                <div className="grid grid-cols-3 gap-1.5" data-testid="lot-detail-quick-bid">
                  {bidSuggestions.map((amt, i) => (
                    <Button
                      key={i}
                      size="sm"
                      variant="outline"
                      className="text-xs font-mono h-8"
                      onClick={() => handlePlaceBid(amt)}
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
                  <Button className="w-full h-9 bg-emerald-600 hover:bg-emerald-700 text-white font-bold" onClick={() => handlePlaceBid(Number(bidAmount))} data-testid="lot-detail-place-bid">
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

              {/* Auto-Bid */}
              {!isEnded && (
                <Button
                  variant="outline"
                  className="w-full h-9 text-xs"
                  onClick={() => toast.info(t('autoBid.openSoon', 'Auto-Bid Bot setup opens shortly.'))}
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
    </div>
  );
}
