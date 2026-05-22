/**
 * BidVex — Phase 6.3 Task 2
 * StorageAuctionClock — real-time countdown ticker with 4 visual states.
 *
 *   Normal  (> 2h):   slate text, no animation
 *   Warning (< 2h):   bold amber
 *   Critical(< 5m):   pulsing crimson + animated bell
 *   Ended  (<= 0):    grey, static "Auction ended"
 *
 * Also surfaces a flash banner when a bid extended the close time within the
 * last 60s (soft-close anti-snipe). Pass `endTime` (ISO string) and an optional
 * `extendedAt` timestamp from the most recent bid response.
 */
import React, { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';

const _pad = (n) => String(n).padStart(2, '0');

export default function StorageAuctionClock({
  endTime,
  extendedAt = null,
  extensionMinutes = 2,
  testIdPrefix = 'storage-clock',
}) {
  const [now, setNow] = useState(Date.now());
  const [showSoftCloseFlash, setShowSoftCloseFlash] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Flash the soft-close notice for 8 seconds after a fresh extension.
  useEffect(() => {
    if (!extendedAt) return;
    const ms = Date.now() - new Date(extendedAt).getTime();
    if (ms >= 0 && ms < 60_000) {
      setShowSoftCloseFlash(true);
      const t = setTimeout(() => setShowSoftCloseFlash(false), 8000);
      return () => clearTimeout(t);
    }
  }, [extendedAt]);

  if (!endTime) return null;

  const endMs = new Date(endTime).getTime();
  const remainingMs = endMs - now;
  const ended = remainingMs <= 0;

  const absMs = Math.max(0, remainingMs);
  const days = Math.floor(absMs / 86_400_000);
  const hours = Math.floor((absMs % 86_400_000) / 3_600_000);
  const minutes = Math.floor((absMs % 3_600_000) / 60_000);
  const seconds = Math.floor((absMs % 60_000) / 1000);

  // State selection
  let toneClass, label, ringClass = '';
  if (ended) {
    toneClass = 'text-slate-400';
    label = 'Auction ended';
  } else if (remainingMs < 5 * 60_000) {
    toneClass = 'text-red-600 dark:text-red-400 font-mono font-bold animate-pulse';
    ringClass = 'ring-2 ring-red-500/50 ring-offset-1 ring-offset-background';
    label = '⚠️ ENDING NOW — FINAL MOMENTS';
  } else if (remainingMs < 2 * 3_600_000) {
    toneClass = 'text-amber-600 dark:text-amber-400 font-bold';
    label = '⏰ Ending soon';
  } else {
    toneClass = 'text-slate-700 dark:text-slate-300';
    label = 'Time remaining';
  }

  return (
    <div className="space-y-1.5" data-testid={`${testIdPrefix}-root`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
        {label}
        {remainingMs < 5 * 60_000 && !ended && (
          <Bell className="h-3 w-3 text-red-600 animate-bounce" />
        )}
      </div>
      {ended ? (
        <div className={`text-xl font-mono font-bold ${toneClass}`} data-testid={`${testIdPrefix}-ended`}>
          —
        </div>
      ) : (
        <div
          className={`text-2xl font-mono tabular-nums tracking-wider ${toneClass} ${ringClass} rounded px-1 inline-block`}
          data-testid={`${testIdPrefix}-value`}
        >
          {days > 0 && <span>{days}d </span>}
          {_pad(hours)}:{_pad(minutes)}:{_pad(seconds)}
        </div>
      )}

      {showSoftCloseFlash && (
        <div
          className="mt-1 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1 text-[11px] font-semibold text-amber-900 dark:text-amber-200 animate-pulse"
          data-testid={`${testIdPrefix}-soft-close-flash`}
        >
          ⚡ Extended: {extensionMinutes} {extensionMinutes === 1 ? 'minute' : 'minutes'} added to prevent sniping!
        </div>
      )}
    </div>
  );
}
