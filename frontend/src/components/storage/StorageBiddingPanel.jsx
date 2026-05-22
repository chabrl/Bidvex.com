/**
 * BidVex — Phase 6.3 Task 1
 * StorageBiddingPanel — sticky right-column / mobile bottom-bar bid card.
 *
 * Surfaces:
 *   • Current high bid + dynamic min-next ($25 increment)
 *   • Leader status ring: 🏆 You are the high bidder / ⚠️ You've been outbid
 *   • 3 quick-tap increments: +$25 / +$50 / +$100
 *   • Slide-to-confirm gate (prevents accidental pocket-bids)
 *   • Forwards the placed-bid response to the parent so the clock can show
 *     the soft-close extension flash.
 *
 * Props:
 *   auction        — full auction object (current_bid, leader_id, status, etc)
 *   currentUserId  — auth.id from useAuth()
 *   onPlaceBid     — async (amount: number) => result | throws — caller wires axios
 *   loading        — submission in-flight indicator (parent-controlled)
 */
import React, { useMemo, useState } from 'react';
import { Trophy, AlertTriangle, Loader2, ChevronRight } from 'lucide-react';

const BID_STEP = 25;

export default function StorageBiddingPanel({
  auction,
  currentUserId,
  onPlaceBid,
  loading = false,
}) {
  const [bidInput, setBidInput] = useState('');
  const [slideValue, setSlideValue] = useState(0);
  const [errorMsg, setErrorMsg] = useState('');

  const currentBid = Number(auction?.current_bid ?? auction?.current_price ?? 0);
  const minNext = currentBid > 0
    ? currentBid + BID_STEP
    : Number(auction?.starting_bid ?? auction?.starting_price ?? 0) || BID_STEP;
  const isLeader = !!currentUserId && auction?.leader_id === currentUserId;
  const isLive = auction?.status === 'active';
  const userBidAmount = Number(bidInput) || 0;

  const quickIncrements = useMemo(() => [
    { label: '+$25',  value: currentBid + 25 },
    { label: '+$50',  value: currentBid + 50 },
    { label: '+$100', value: currentBid + 100 },
  ], [currentBid]);

  const applyQuick = (amt) => {
    setBidInput(String(amt));
    setErrorMsg('');
    setSlideValue(0); // reset slider so user has to re-confirm
  };

  const handleSliderChange = async (e) => {
    const v = Number(e.target.value);
    setSlideValue(v);
    if (v >= 100) {
      // Threshold reached — fire the bid
      await dispatchBid();
    }
  };

  const dispatchBid = async () => {
    setErrorMsg('');
    const amt = Number(bidInput);
    if (!amt || amt < minNext) {
      setErrorMsg(`Minimum bid is $${minNext.toFixed(2)}`);
      setSlideValue(0);
      return;
    }
    try {
      await onPlaceBid(amt);
      setBidInput('');
      setSlideValue(0);
    } catch (err) {
      setErrorMsg(err?.response?.data?.detail || err?.message || 'Bid failed.');
      setSlideValue(0);
    }
  };

  if (!isLive) {
    return (
      <div
        className="rounded-lg border bg-slate-50 dark:bg-slate-900 px-4 py-6 text-center text-sm text-muted-foreground"
        data-testid="storage-bid-panel-inactive"
      >
        This auction is not currently accepting bids.
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border bg-white dark:bg-slate-900 shadow-md p-4 space-y-3"
      data-testid="storage-bidding-panel"
    >
      {/* Leader status ring */}
      {currentUserId && (
        isLeader ? (
          <div
            className="flex items-center gap-2 rounded-md bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-300 px-3 py-2 text-sm font-semibold text-emerald-800 dark:text-emerald-200"
            data-testid="storage-bid-leader-badge"
          >
            <Trophy className="h-4 w-4 shrink-0" />
            <span>🏆 You are the current high bidder!</span>
          </div>
        ) : (
          auction?.has_user_bid && (
            <div
              className="flex items-center gap-2 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-800 dark:text-amber-200"
              data-testid="storage-bid-outbid-badge"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>⚠️ You&apos;ve been outbid! Raise your bid to stay in the running.</span>
            </div>
          )
        )
      )}

      {/* Current high bid */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">
            Current High Bid
          </div>
          <div className="text-xl font-bold tabular-nums" data-testid="storage-bid-current">
            ${currentBid.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">
            Minimum Next Bid
          </div>
          <div className="text-xl font-bold tabular-nums text-blue-700 dark:text-blue-400" data-testid="storage-bid-min-next">
            ${minNext.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Quick-tap increments */}
      <div className="grid grid-cols-3 gap-1.5">
        {quickIncrements.map((q) => (
          <button
            key={q.label}
            type="button"
            onClick={() => applyQuick(q.value)}
            disabled={loading}
            data-testid={`storage-bid-quick-${q.label.replace(/[^a-z0-9]+/gi, '')}`}
            className="px-2 py-2 rounded-md border border-slate-200 dark:border-slate-700 text-xs font-semibold hover:bg-blue-50 hover:border-blue-400 dark:hover:bg-blue-900/30 active:scale-95 transition-all"
          >
            {q.label}
          </button>
        ))}
      </div>

      {/* Custom bid input */}
      <div>
        <label className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold block mb-1">
          Your Bid (≥ ${minNext.toFixed(2)})
        </label>
        <input
          type="number"
          inputMode="decimal"
          min={minNext}
          step={BID_STEP}
          value={bidInput}
          onChange={(e) => { setBidInput(e.target.value); setSlideValue(0); setErrorMsg(''); }}
          placeholder={`${minNext.toFixed(2)}`}
          disabled={loading}
          data-testid="storage-bid-input"
          className="w-full rounded-md border border-slate-300 dark:border-slate-700 px-3 py-2 text-base font-semibold tabular-nums bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Slide-to-confirm */}
      <div>
        <label className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold block mb-1">
          Slide to confirm your bid →
        </label>
        <div className="relative h-12 rounded-full bg-gradient-to-r from-slate-100 to-blue-100 dark:from-slate-800 dark:to-blue-900/40 border border-slate-300 dark:border-slate-700 overflow-hidden">
          <div
            className="absolute inset-0 bg-blue-600/30 pointer-events-none transition-all"
            style={{ width: `${slideValue}%` }}
            aria-hidden="true"
          />
          <input
            type="range"
            min={0}
            max={100}
            value={slideValue}
            onChange={handleSliderChange}
            disabled={loading || !userBidAmount}
            data-testid="storage-bid-slide-confirm"
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            aria-label="Slide to confirm bid"
          />
          <div className="absolute inset-0 flex items-center justify-between px-4 pointer-events-none">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 truncate">
              {loading ? 'Placing bid…' : userBidAmount
                ? `Slide to bid $${userBidAmount.toFixed(2)}`
                : 'Enter a bid amount above'}
            </span>
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-blue-700" />
            ) : (
              <ChevronRight
                className="h-5 w-5 text-blue-700 dark:text-blue-400 transition-transform"
                style={{ transform: `translateX(${(slideValue / 100) * 200}px)` }}
              />
            )}
          </div>
        </div>
      </div>

      {errorMsg && (
        <p className="text-xs text-red-600 dark:text-red-400 font-medium" data-testid="storage-bid-error">
          {errorMsg}
        </p>
      )}

      <p className="text-[10px] text-muted-foreground leading-tight">
        Bidding requires a Stripe authorization hold for the cleanout security deposit.
        Holds release automatically if you do not win.
      </p>
    </div>
  );
}
