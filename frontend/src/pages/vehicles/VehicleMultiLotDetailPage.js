import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import {
  Layers, Car, Gavel, Loader2, Clock, BellRing, Trophy,
  Lock, Unlock, ChevronDown, ChevronUp, History, ShieldAlert, Shield,
  ChevronLeft, ChevronRight, Gauge, MapPin, Hash, X, ZoomIn,
} from 'lucide-react';
import { toast } from 'sonner';
import UpcomingCountdownBadge from '../../components/UpcomingCountdownBadge';
import { getTimingModeShortLabel } from '../../lib/vehicleMultiLotTimingModes';
import WatchlistButton from '../../components/WatchlistButton';
import { usePlatformTermsGate } from '../../contexts/PlatformTermsGateContext';
import SafeImage from '../../components/SafeImage';
import useVehicleCountdown from '../../hooks/useVehicleCountdown';
import { extractErrorMessage } from '../../utils/errorHandler';
import AcceptedPaymentMethodsCard from '../../components/AcceptedPaymentMethodsCard';
import VehicleReserveBadge from '../../components/vehicles/VehicleReserveBadge';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * VehicleMultiLotDetailPage — iter293 Directive 2 / iter295 P0+P1 addendum
 *
 * Adds (iter295):
 *   • 403 broker_required handling (province-gated buyer restriction)
 *   • 402 deposit_required → per-lot deposit modal
 *   • Per-lot Bid History (collapsible "Last 10 bids" panel)
 *   • Lot Queue deposit-lock icon
 */
const fmtCurrency = (n) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n || 0);

// iter418 — Map `lot.media` (array of `{url, thumbnail_url, order}`) → sorted URL list.
// The full-size URL is used for the hero image and the thumbnail_url (or same URL
// when missing) is used for thumbnail strips + queue cards.
const getSortedMediaUrls = (lot) => {
  const media = Array.isArray(lot?.media) ? lot.media : [];
  const sorted = [...media].sort(
    (a, b) => (Number(a?.order) || 0) - (Number(b?.order) || 0),
  );
  return sorted
    .map((m) => ({
      full: m?.url || m?.thumbnail_url || '',
      thumb: m?.thumbnail_url || m?.url || '',
    }))
    .filter((m) => m.full);
};

const StatusBadge = ({ status }) => {
  const styles = {
    draft:     'bg-gray-100 text-gray-700 border-gray-300',
    upcoming:  'bg-blue-100 text-blue-700 border-blue-300',
    live:      'bg-green-100 text-green-700 border-green-300',
    ended:     'bg-orange-100 text-orange-700 border-orange-300',
    sold:      'bg-purple-100 text-purple-700 border-purple-300',
    cancelled: 'bg-red-100 text-red-700 border-red-300',
  };
  // iter345 — defensive against legacy/partial VML docs that omit `status`.
  const safe = (status || 'unknown').toString();
  return (
    <Badge className={`${styles[safe] || styles.upcoming} border`} data-testid={`status-badge-${safe}`}>
      {safe.toUpperCase()}
    </Badge>
  );
};

// ── iter295 P1 — Bid History (collapsible per lot) ─────────────────────
const BidHistoryPanel = ({ eventId, lot }) => {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}/lots/${lot.id}/bid-history`);
      setRows(r.data?.data || []);
    } catch (e) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [eventId, lot.id]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !rows) loadHistory();
  };

  return (
    <div className="mt-2 border-t pt-2" data-testid={`bid-history-panel-${lot.lot_number}`}>
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between text-xs font-medium text-slate-600 hover:text-slate-900"
        data-testid={`bid-history-toggle-${lot.lot_number}`}
      >
        <span className="inline-flex items-center gap-1">
          <History className="h-3.5 w-3.5" />
          Bid History
          {typeof lot.bid_count === 'number' && lot.bid_count > 0 && (
            <span className="ml-1 px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] font-semibold">
              {lot.bid_count}
            </span>
          )}
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {open && (
        <div className="mt-2" data-testid={`bid-history-rows-${lot.lot_number}`}>
          {loading && (
            <div className="text-xs text-slate-500 flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" /> Loading…
            </div>
          )}
          {!loading && rows && rows.length === 0 && (
            <div className="text-xs text-slate-500 italic">No bids yet on this lot.</div>
          )}
          {!loading && rows && rows.length > 0 && (
            <ul className="space-y-1">
              {rows.map((b) => (
                <li
                  key={b.bid_id}
                  className="flex items-center justify-between text-xs bg-slate-50 rounded px-2 py-1"
                  data-testid={`bid-history-row-${lot.lot_number}-${b.bid_id}`}
                >
                  <span className="text-slate-700">{b.alias}</span>
                  <span className="font-semibold text-emerald-700">{fmtCurrency(b.amount)}</span>
                  <span className="text-slate-500">
                    {b.created_at ? new Date(b.created_at).toLocaleTimeString() : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

// iter419 — Photo-swipe zoom modal for the active-lot hero gallery.
// Full-screen dark backdrop, keyboard arrows + Escape, on-image left/right
// arrow controls, counter "n / total", close button, and touch-swipe
// support for mobile. Only used on the Active Lot image gallery.
const PhotoZoomModal = ({ images, initialIndex = 0, alt = '', onClose }) => {
  const [index, setIndex] = useState(initialIndex);
  const touchStartX = React.useRef(null);
  const touchDeltaX = React.useRef(0);

  const total = images?.length || 0;

  const prev = useCallback(() => {
    if (total <= 1) return;
    setIndex((i) => (i - 1 + total) % total);
  }, [total]);

  const next = useCallback(() => {
    if (total <= 1) return;
    setIndex((i) => (i + 1) % total);
  }, [total]);

  // Keyboard navigation + Escape.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') prev();
      else if (e.key === 'ArrowRight') next();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, prev, next]);

  // Lock body scroll while modal is open.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prevOverflow; };
  }, []);

  // Touch-swipe handlers (mobile).
  const onTouchStart = (e) => {
    if (e.touches?.length !== 1) return;
    touchStartX.current = e.touches[0].clientX;
    touchDeltaX.current = 0;
  };
  const onTouchMove = (e) => {
    if (touchStartX.current == null || e.touches?.length !== 1) return;
    touchDeltaX.current = e.touches[0].clientX - touchStartX.current;
  };
  const onTouchEnd = () => {
    const dx = touchDeltaX.current;
    touchStartX.current = null;
    touchDeltaX.current = 0;
    if (Math.abs(dx) < 40) return; // ignore taps
    if (dx > 0) prev(); else next();
  };

  if (!total) return null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/95 flex items-center justify-center select-none"
      onClick={onClose}
      data-testid="photo-zoom-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Vehicle photo viewer"
    >
      {/* Top bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between p-3 sm:p-4 text-white z-10">
        <span
          className="text-sm font-mono bg-white/10 rounded px-2 py-1"
          data-testid="photo-zoom-counter"
        >
          {index + 1} / {total}
        </span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="p-2 rounded-full bg-white/10 hover:bg-white/20 transition"
          aria-label="Close photo viewer"
          data-testid="photo-zoom-close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Image */}
      <div
        className="relative w-full h-full flex items-center justify-center px-4"
        onClick={(e) => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <SafeImage
          src={images[index]?.full}
          alt={`${alt} — photo ${index + 1}`}
          className="max-w-full max-h-full object-contain"
          loading="eager"
          data-testid="photo-zoom-image"
        />

        {/* Arrows */}
        {total > 1 && (
          <>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); prev(); }}
              className="absolute left-2 sm:left-4 top-1/2 -translate-y-1/2 bg-white/10 hover:bg-white/20 text-white rounded-full p-3 transition"
              aria-label="Previous image"
              data-testid="photo-zoom-prev"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); next(); }}
              className="absolute right-2 sm:right-4 top-1/2 -translate-y-1/2 bg-white/10 hover:bg-white/20 text-white rounded-full p-3 transition"
              aria-label="Next image"
              data-testid="photo-zoom-next"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          </>
        )}
      </div>
    </div>
  );
};

const VehicleMultiLotDetailPage = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const { runWithTermsGate } = usePlatformTermsGate();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidAmount, setBidAmount] = useState('');
  const [placing, setPlacing] = useState(false);
  const [activeLotOverride, setActiveLotOverride] = useState(null);
  const [notifying, setNotifying] = useState(false);

  // iter295 — deposit modal state
  const [depositModal, setDepositModal] = useState(null); // { lotId, amount, lotNumber, lotTitle }
  const [payingDeposit, setPayingDeposit] = useState(false);
  // iter295 — deposit-lock map: { [lot_id]: true/false }
  const [depositMap, setDepositMap] = useState({});
  // iter418 — active-lot image gallery cursor (fix: images never rendered)
  const [activeImageIdx, setActiveImageIdx] = useState(0);
  // iter419 — active-lot photo-swipe zoom modal
  const [zoomOpen, setZoomOpen] = useState(false);
  const [zoomIndex, setZoomIndex] = useState(0);
  // iter418 — one shared per-second tick for all countdowns on the page
  const { format: formatCountdown } = useVehicleCountdown();

  const refresh = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}`);
      setEvent(r.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    let cancelled = false;
    let timer;
    const runner = async () => {
      if (cancelled) return;
      try {
        const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}`);
        if (cancelled) return;
        setEvent(r.data);
      } catch (e) {
        console.error(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    runner();
    timer = setInterval(runner, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [eventId]);

  // iter295 — Pre-load per-lot deposit lock state for the logged-in buyer.
  // Best-effort: anonymous users skip silently. The fetch happens inside
  // a top-level useEffect (not exported) so React Compiler's
  // set-state-in-effect rule sees the state update as initialization.
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token || !event?.lots?.length) return;
    let cancelled = false;
    (async () => {
      try {
        const results = await Promise.all(
          event.lots.map((lt) =>
            axios.get(
              `${API}/vehicle-multi-lot-auctions/${event.id}/lots/${lt.id}/my-deposit`,
              { headers: { Authorization: `Bearer ${token}` } },
            ).then((r) => [lt.id, !!r.data?.has_deposit]).catch(() => [lt.id, false]),
          ),
        );
        if (cancelled) return;
        const map = {};
        results.forEach(([id, has]) => { map[id] = has; });
        setDepositMap(map);
      } catch {
        /* silent */
      }
    })();
    return () => { cancelled = true; };
  }, [event]);

  let activeLotId = null;
  if (activeLotOverride) {
    activeLotId = activeLotOverride;
  } else if (event?.lots?.length) {
    const live = event.lots.find((l) => l.status === 'live');
    const upcoming = event.lots.find((l) => l.status === 'upcoming');
    activeLotId = live?.id || upcoming?.id || event.lots[0].id;
  }

  const activeLot = event?.lots?.find((l) => l.id === activeLotId) || null;

  // iter418 — Prev/Next lot navigation. Uses `lot_sequence` when available,
  // otherwise falls back to the array order.
  const lotIds = event?.lot_sequence?.length
    ? event.lot_sequence
    : (event?.lots || []).map((l) => l.id);
  const activeIndex = activeLot ? lotIds.indexOf(activeLot.id) : -1;
  const prevLotId = activeIndex > 0 ? lotIds[activeIndex - 1] : null;
  const nextLotId = activeIndex >= 0 && activeIndex < lotIds.length - 1
    ? lotIds[activeIndex + 1] : null;

  // iter418 — Reset the image gallery cursor whenever the active lot changes
  // so the hero always starts at photo #1 of the newly selected lot.
  useEffect(() => {
    setActiveImageIdx(0);
  }, [activeLotId]);

  // iter418 — Ordered media URLs for the currently-visible active lot.
  const activeLotMedia = activeLot ? getSortedMediaUrls(activeLot) : [];

  const payDeposit = async () => {
    if (!depositModal) return;
    setPayingDeposit(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/vehicle-multi-lot-auctions/${event.id}/lots/${depositModal.lotId}/deposit`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Deposit paid — you can now bid on this lot.');
      setDepositMap((m) => ({ ...m, [depositModal.lotId]: true }));
      setDepositModal(null);
    } catch (e) {
      toast.error(extractErrorMessage(e) || 'Deposit payment failed');
    } finally {
      setPayingDeposit(false);
    }
  };

  const handleBid = async () => {
    if (!activeLot) return;
    const amt = Number(bidAmount);
    if (!amt || amt <= 0) { toast.error('Enter a bid amount'); return; }
    setPlacing(true);
    try {
      const token = localStorage.getItem('token');
      await runWithTermsGate(() => axios.post(
        `${API}/vehicle-multi-lot-auctions/${event.id}/lots/${activeLot.id}/bid`,
        { event_id: event.id, lot_id: activeLot.id, amount: amt },
        { headers: { Authorization: `Bearer ${token}` } },
      ));
      toast.success('Bid placed!');
      setBidAmount('');
      refresh();
    } catch (e) {
      // iter404 — silent no-op when the inline T&C modal is cancelled.
      if (e?.termsGateCancelled) { setPlacing(false); return; }
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;

      // iter295 P1 — 402 deposit_required → open per-lot deposit modal
      if (status === 402 && detail?.code === 'deposit_required') {
        setDepositModal({
          lotId:     detail.lot_id || activeLot.id,
          amount:    Number(detail.deposit_amount) || 200,
          lotNumber: detail.lot_number || activeLot.lot_number,
          lotTitle:  detail.lot_title || activeLot.title,
        });
        toast.message(detail.message_en || 'Refundable deposit required.');
      }
      // iter295 P0 — 403 broker_required → province-gate toast + nav to broker directory
      else if (status === 403 && detail?.code === 'broker_required') {
        toast.error(
          detail.message_en || 'A licensed broker is required to bid in your province.',
          {
            action: {
              label: 'Find a broker',
              onClick: () => navigate(detail.action_url || '/brokers'),
            },
          },
        );
      }
      else {
        toast.error(typeof detail === 'string' ? detail : (detail?.message_en || 'Bid failed'));
      }
    } finally {
      setPlacing(false);
    }
  };

  const handleNotify = async () => {
    setNotifying(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/upcoming-notify/subscribe`, {
        listing_id: event.id,
        listing_type: 'vehicle_multi_lot',
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success('We\u2019ll email you when bidding opens!');
    } catch (e) {
      toast.error(extractErrorMessage(e) || 'Subscription failed — login required');
    } finally {
      setNotifying(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center"><Loader2 className="h-8 w-8 animate-spin mx-auto" /></div>;
  }
  if (!event) {
    return <div className="p-8 text-center text-gray-600">Event not found.</div>;
  }

  const lots = event.lots || [];
  const minBid = activeLot
    ? (Number(activeLot.current_bid) > 0
      ? Number(activeLot.current_bid) + Number(activeLot.bid_increment || 100)
      : Number(activeLot.starting_price))
    : 0;

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6" data-testid="multi-lot-detail-page">
      {/* Header */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Layers className="h-5 w-5 text-blue-600" />
              <h1 className="text-2xl sm:text-3xl font-bold">{event.title}</h1>
              <StatusBadge status={event.status} />
              <Badge variant="outline" className="border-blue-300 text-blue-700">
                {getTimingModeShortLabel(event.timing_mode)}
              </Badge>
            </div>
            <p className="text-sm text-gray-600">
              {lots.length} lot{lots.length === 1 ? '' : 's'} · Event starts {new Date(event.start_time).toLocaleString()}
            </p>
            {event.description && <p className="mt-2 text-gray-700">{event.description}</p>}
          </div>
          {event.status === 'upcoming' && (
            <div className="flex flex-col items-end gap-2">
              <UpcomingCountdownBadge startTime={event.start_time} onLive={refresh} />
              <Button onClick={handleNotify} disabled={notifying} variant="outline" size="sm" data-testid="notify-btn">
                {notifying ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <BellRing className="h-4 w-4 mr-1" />}
                Notify me when live
              </Button>
              {/* iter345 BUG-2 — save the whole VML event to the buyer's watchlist */}
              <div data-testid="vml-watchlist-btn-wrapper">
                <WatchlistButton itemId={event.id} itemType="vehicle_multi_lot" size="default" showLabel />
              </div>
            </div>
          )}
          {event.status !== 'upcoming' && (
            <div className="flex items-center gap-2">
              {/* iter345 BUG-2 — save the whole VML event to the buyer's watchlist */}
              <div data-testid="vml-watchlist-btn-wrapper">
                <WatchlistButton itemId={event.id} itemType="vehicle_multi_lot" size="default" showLabel />
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Active Lot */}
      {activeLot && (
        <Card className="p-4 sm:p-6 border-blue-200 bg-gradient-to-r from-white to-blue-50" data-testid="active-lot-card">
          {/* iter418 — Prev/Next lot navigation strip (only when >1 lot) */}
          {lotIds.length > 1 && (
            <div className="flex items-center justify-between mb-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => prevLotId && setActiveLotOverride(prevLotId)}
                disabled={!prevLotId}
                data-testid="active-lot-prev-btn"
              >
                <ChevronLeft className="h-4 w-4 mr-1" /> Previous Lot
              </Button>
              <span className="text-xs text-slate-500 font-medium" data-testid="active-lot-position">
                Lot {activeIndex + 1} of {lotIds.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => nextLotId && setActiveLotOverride(nextLotId)}
                disabled={!nextLotId}
                data-testid="active-lot-next-btn"
              >
                Next Lot <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          <div className="flex flex-col lg:flex-row gap-6 justify-between">
            {/* Left column — Image gallery + vehicle info */}
            <div className="flex-1 min-w-0">
              {/* iter418 — Hero image + thumbnail gallery */}
              <div className="mb-4" data-testid="active-lot-gallery">
                <div className="relative w-full aspect-[4/3] bg-slate-100 rounded-lg overflow-hidden">
                  {activeLotMedia.length > 0 ? (
                    <>
                      <button
                        type="button"
                        onClick={() => { setZoomIndex(activeImageIdx); setZoomOpen(true); }}
                        className="w-full h-full block group relative"
                        aria-label="Zoom image"
                        data-testid="active-lot-hero-zoom-btn"
                      >
                        <SafeImage
                          src={activeLotMedia[activeImageIdx]?.full}
                          alt={`Lot ${activeLot.lot_number} — ${activeLot.year} ${activeLot.make} ${activeLot.model}`}
                          className="w-full h-full object-cover cursor-zoom-in transition group-hover:brightness-95"
                          loading="eager"
                          fetchPriority="high"
                          data-testid="active-lot-hero-image"
                        />
                        <span className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded inline-flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                          <ZoomIn className="h-3.5 w-3.5" /> Click to zoom
                        </span>
                      </button>
                      {activeLotMedia.length > 1 && (
                        <>
                          <button
                            type="button"
                            onClick={() => setActiveImageIdx((i) => (i - 1 + activeLotMedia.length) % activeLotMedia.length)}
                            className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-full p-2"
                            aria-label="Previous image"
                            data-testid="active-lot-image-prev"
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setActiveImageIdx((i) => (i + 1) % activeLotMedia.length)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-full p-2"
                            aria-label="Next image"
                            data-testid="active-lot-image-next"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </button>
                          <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded">
                            {activeImageIdx + 1} / {activeLotMedia.length}
                          </div>
                        </>
                      )}
                    </>
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                      <Car className="h-12 w-12 mb-2" />
                      <span className="text-sm">No photos available</span>
                    </div>
                  )}
                </div>
                {activeLotMedia.length > 1 && (
                  <div className="mt-2 flex gap-2 overflow-x-auto pb-1" data-testid="active-lot-thumb-strip">
                    {activeLotMedia.slice(0, 8).map((m, i) => (
                      <button
                        key={m.full}
                        type="button"
                        onClick={() => { setActiveImageIdx(i); setZoomIndex(i); setZoomOpen(true); }}
                        className={`flex-shrink-0 w-16 h-16 rounded-md overflow-hidden border-2 transition ${
                          i === activeImageIdx ? 'border-blue-500 ring-2 ring-blue-200' : 'border-transparent opacity-70 hover:opacity-100'
                        }`}
                        data-testid={`active-lot-thumb-${i}`}
                      >
                        <SafeImage
                          src={m.thumb}
                          alt={`Photo ${i + 1}`}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <Car className="h-5 w-5 text-blue-600" />
                <h2 className="text-xl font-semibold">Lot #{activeLot.lot_number} — {activeLot.title}</h2>
                <StatusBadge status={activeLot.status} />
                {/* iter484.2 Gate 2 — Reserve chip driven by masked
                    `has_reserve` + `reserve_state` fields.  Never
                    reveals the raw amount. */}
                <VehicleReserveBadge doc={activeLot} variant="chip" />
                {/* iter295 — deposit lock icon on active lot */}
                {activeLot.status === 'live' && (
                  depositMap[activeLot.id]
                    ? <Badge className="bg-emerald-50 text-emerald-800 border border-emerald-200 inline-flex items-center gap-1"
                        data-testid="active-lot-deposit-unlocked">
                        <Unlock className="h-3 w-3" /> Bid-Enabled
                      </Badge>
                    : <Badge className="bg-amber-50 text-amber-800 border border-amber-200 inline-flex items-center gap-1"
                        data-testid="active-lot-deposit-locked">
                        <Lock className="h-3 w-3" /> Deposit Required
                      </Badge>
                )}
              </div>
              <p className="text-lg font-medium text-slate-900" data-testid="active-lot-ymm">
                {activeLot.year} {activeLot.make} {activeLot.model}
                {activeLot.trim ? <span className="text-slate-600"> {activeLot.trim}</span> : null}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
                {typeof activeLot.mileage === 'number' && (
                  <span className="inline-flex items-center gap-1" data-testid="active-lot-mileage">
                    <Gauge className="h-3.5 w-3.5" /> {activeLot.mileage.toLocaleString()} km
                  </span>
                )}
                {(activeLot.location_city || activeLot.location_province) && (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5" />
                    {[activeLot.location_city, activeLot.location_province].filter(Boolean).join(', ')}
                  </span>
                )}
                {activeLot.vin && (
                  <span className="inline-flex items-center gap-1 font-mono text-xs">
                    <Hash className="h-3.5 w-3.5" /> {activeLot.vin}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3 text-sm">
                <div>
                  <div className="text-gray-500 text-xs">Starting</div>
                  <div className="font-medium">{fmtCurrency(activeLot.starting_price)}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs">Current Bid</div>
                  <div className="font-bold text-green-700 text-base" data-testid="active-lot-current-bid">
                    {fmtCurrency(activeLot.current_bid)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs">Bids</div>
                  <div className="font-medium" data-testid="active-lot-bid-count">{activeLot.bid_count || 0}</div>
                </div>
              </div>
              {activeLot.description && <p className="mt-3 text-sm text-gray-600">{activeLot.description}</p>}

              {/* iter295 P1 — Active-lot bid history */}
              <BidHistoryPanel eventId={event.id} lot={activeLot} />
            </div>

            {/* Bid panel */}
            <div className="lg:w-80 space-y-3">
              {activeLot.status === 'upcoming' && (
                <UpcomingCountdownBadge startTime={activeLot.start_time} onLive={refresh} />
              )}
              {activeLot.status === 'live' && activeLot.end_time && (() => {
                // iter418 — Live per-second countdown (was previously a static toLocaleTimeString).
                const c = formatCountdown(activeLot.end_time);
                const critical = c.critical || (c.ms > 0 && c.ms <= 120000);
                return (
                  <div
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-mono font-semibold ${
                      critical ? 'bg-red-100 text-red-700 animate-pulse' : 'bg-green-100 text-green-700'
                    }`}
                    data-testid="active-lot-countdown"
                  >
                    <Clock className="h-4 w-4" />
                    {c.ended ? 'Ended' : c.label}
                  </div>
                );
              })()}
              {activeLot.status === 'live' && (
                <div className="space-y-2">
                  <Input
                    type="number"
                    placeholder={`Min ${fmtCurrency(minBid)}`}
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                    data-testid="bid-amount-input"
                  />
                  <Button onClick={handleBid} disabled={placing} className="w-full bg-green-600 hover:bg-green-700" data-testid="place-bid-btn">
                    {placing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Gavel className="h-4 w-4 mr-1" />}
                    Place Bid
                  </Button>
                  <p className="text-xs text-gray-500 text-center">2-min soft-close active — late bids extend the lot.</p>
                </div>
              )}
              {(activeLot.status === 'ended' || activeLot.status === 'sold') && (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-center">
                  <Trophy className="h-5 w-5 mx-auto text-purple-600 mb-1" />
                  <p className="text-sm font-semibold text-purple-800">
                    Lot {activeLot.status === 'sold' ? 'SOLD' : 'CLOSED'} at {fmtCurrency(activeLot.current_bid)}
                  </p>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* iter484.2 Gate 1 — Vehicle Multi-Lot accepted payment methods.
          Auction-level (applies to every lot in the event).  Shown
          above the Lot Queue so buyers see the seller's approved
          methods before choosing a lot to bid on. */}
      <AcceptedPaymentMethodsCard listing={event} />

      {/* Lot queue — iter418 rebuilt as visual card grid */}
      <Card className="p-4 sm:p-6">
        <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Layers className="h-5 w-5" /> Lot Queue ({lots.length})
        </h3>
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
          data-testid="lot-queue-grid"
        >
          {lots.map((lot) => {
            const media = getSortedMediaUrls(lot);
            const thumb = media[0]?.thumb || '';
            const isActive = lot.id === activeLotId;
            const c = lot.end_time ? formatCountdown(lot.end_time) : null;
            const isLive = lot.status === 'live';
            const isUpcoming = lot.status === 'upcoming';
            // iter484.2 Gate 2 — VehicleReserveBadge is the single
            // source of truth for the buyer-visible reserve state.
            // The raw amount is masked on the API.
            return (
              <div
                key={lot.id}
                role="button"
                tabIndex={0}
                onClick={() => setActiveLotOverride(lot.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setActiveLotOverride(lot.id);
                  }
                }}
                className={`text-left rounded-lg border overflow-hidden bg-white transition hover:shadow-md cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  isActive
                    ? 'ring-2 ring-blue-500 border-blue-500 shadow-md'
                    : 'border-slate-200'
                }`}
                data-testid={`lot-card-${lot.lot_number}`}
              >
                {/* Thumbnail */}
                <div className="relative aspect-[4/3] bg-slate-100">
                  {thumb ? (
                    <SafeImage
                      src={thumb}
                      alt={`Lot ${lot.lot_number} — ${lot.year} ${lot.make} ${lot.model}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                      data-testid={`lot-card-thumb-${lot.lot_number}`}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-400">
                      <Car className="h-8 w-8" />
                    </div>
                  )}
                  {/* Lot number badge */}
                  <div className="absolute top-2 left-2 bg-black/70 text-white text-xs font-bold px-2 py-1 rounded">
                    Lot #{lot.lot_number}
                  </div>
                  {/* Active "NOW" badge */}
                  {isActive && (
                    <div
                      className="absolute top-2 right-2 bg-blue-600 text-white text-[10px] font-bold px-2 py-1 rounded shadow"
                      data-testid={`lot-card-active-indicator-${lot.lot_number}`}
                    >
                      NOW VIEWING
                    </div>
                  )}
                  {/* Status badge (bottom-left) */}
                  <div className="absolute bottom-2 left-2">
                    <StatusBadge status={lot.status} />
                  </div>
                  {/* Countdown (bottom-right) */}
                  {c && !c.ended && (isLive || isUpcoming) && (
                    <div
                      className={`absolute bottom-2 right-2 text-[11px] font-mono font-semibold px-2 py-1 rounded ${
                        c.critical ? 'bg-red-600 text-white animate-pulse' : 'bg-black/70 text-white'
                      }`}
                      data-testid={`lot-card-countdown-${lot.lot_number}`}
                    >
                      <Clock className="h-3 w-3 inline mr-0.5" />
                      {isUpcoming ? `Starts ${c.short}` : c.short}
                    </div>
                  )}
                </div>
                {/* Body */}
                <div className="p-3 space-y-1.5">
                  <div className="font-semibold text-sm truncate" data-testid={`lot-card-ymm-${lot.lot_number}`}>
                    {lot.year} {lot.make} {lot.model}
                  </div>
                  <div className="text-xs text-slate-500 flex items-center gap-1">
                    <Gauge className="h-3 w-3" />
                    {typeof lot.mileage === 'number' ? `${lot.mileage.toLocaleString()} km` : '—'}
                  </div>
                  <div className="flex items-baseline justify-between pt-1">
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-wide">Current</div>
                      <div className="font-bold text-green-700 text-sm" data-testid={`lot-card-current-bid-${lot.lot_number}`}>
                        {fmtCurrency(lot.current_bid)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-slate-500 uppercase tracking-wide">Bids</div>
                      <div className="font-semibold text-slate-700 text-sm" data-testid={`lot-card-bid-count-${lot.lot_number}`}>
                        {lot.bid_count || 0}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {/* iter484.2 Gate 2 — Reserve chip on lot queue
                        thumbnail.  Data-driven by masked has_reserve /
                        reserve_state.  Raw amount is not available on
                        the client any more. */}
                    <VehicleReserveBadge doc={lot} variant="chip" hideWhenNone />
                    {depositMap[lot.id] ? (
                      <span
                        className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700"
                        data-testid={`lot-deposit-ok-${lot.lot_number}`}
                      >
                        <Unlock className="h-3 w-3" /> Bid-ready
                      </span>
                    ) : (
                      <span
                        className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700"
                        data-testid={`lot-deposit-locked-${lot.lot_number}`}
                      >
                        <Lock className="h-3 w-3" /> Deposit
                      </span>
                    )}
                  </div>
                </div>
                {/* Bid history sub-panel */}
                <div className="px-3 pb-3 border-t border-slate-100 mt-1 pt-2" onClick={(e) => e.stopPropagation()}>
                  <BidHistoryPanel eventId={event.id} lot={lot} />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* iter295 P1 — Per-lot deposit modal (triggered by 402) */}
      {depositModal && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          data-testid="lot-deposit-modal"
          onClick={() => !payingDeposit && setDepositModal(null)}
        >
          <div
            className="bg-white rounded-lg p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <ShieldAlert className="h-5 w-5 text-amber-600" />
              <h3 className="text-lg font-semibold">Refundable Deposit Required</h3>
            </div>
            <p className="text-sm text-slate-600 mb-3">
              To bid on <strong>Lot #{depositModal.lotNumber} — {depositModal.lotTitle}</strong>,
              a refundable deposit of <strong>{fmtCurrency(depositModal.amount)}</strong> is required.
              It is fully refunded if you do not win this lot.
            </p>
            <div className="bg-blue-50 border border-blue-100 rounded p-3 text-xs text-blue-900 mb-4 inline-flex items-start gap-2">
              <Shield className="h-4 w-4 mt-0.5 shrink-0" />
              <span>The deposit applies only to this lot — bidding on another lot requires a separate deposit.</span>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setDepositModal(null)}
                disabled={payingDeposit}
                data-testid="lot-deposit-cancel-btn"
              >
                Cancel
              </Button>
              <Button
                onClick={payDeposit}
                disabled={payingDeposit}
                className="bg-blue-600 hover:bg-blue-700"
                data-testid="lot-deposit-confirm-btn"
              >
                {payingDeposit
                  ? <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  : <Shield className="h-4 w-4 mr-1" />}
                Pay {fmtCurrency(depositModal.amount)} deposit
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* iter419 — Photo-swipe zoom modal for active-lot hero gallery */}
      {zoomOpen && activeLot && activeLotMedia.length > 0 && (
        <PhotoZoomModal
          images={activeLotMedia}
          initialIndex={zoomIndex}
          alt={`Lot ${activeLot.lot_number} — ${activeLot.year} ${activeLot.make} ${activeLot.model}`}
          onClose={() => setZoomOpen(false)}
        />
      )}
    </div>
  );
};

export default VehicleMultiLotDetailPage;
