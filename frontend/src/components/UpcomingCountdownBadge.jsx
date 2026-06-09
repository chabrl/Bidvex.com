import React, { useEffect, useState } from 'react';

/**
 * UpcomingCountdownBadge — iter293 Directive P1
 *
 * Reusable countdown shown on:
 *  • Vehicle listings index card
 *  • Vehicle detail page
 *  • Multi-lot vehicle auction detail page
 *
 * Props:
 *   startTime  — ISO string or Date
 *   onLive     — optional callback invoked when the countdown reaches 0
 *                (lets the parent page swap to the bidding UI without
 *                a hard refresh)
 *   compact    — `true` shrinks the badge for use inside list cards
 *
 * Behaviour:
 *   - When `startTime > now`, renders "Bidding opens in Xd Xh Xm Xs"
 *     with the iter291 Tailwind palette.
 *   - When `startTime <= now`, fires `onLive()` ONCE and renders
 *     `null` (parent renders the live bidding UI instead).
 */
const _fmt = (totalSeconds) => {
  if (totalSeconds < 0) totalSeconds = 0;
  const d = Math.floor(totalSeconds / 86400);
  const h = Math.floor((totalSeconds % 86400) / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.floor(totalSeconds % 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

const UpcomingCountdownBadge = ({ startTime, onLive, compact = false, className = '' }) => {
  const [remaining, setRemaining] = useState(() => {
    if (!startTime) return 0;
    return Math.max(0, (new Date(startTime).getTime() - Date.now()) / 1000);
  });
  const [fired, setFired] = useState(false);

  useEffect(() => {
    if (!startTime) return undefined;
    const tick = () => {
      const r = Math.max(0, (new Date(startTime).getTime() - Date.now()) / 1000);
      setRemaining(r);
      if (r <= 0 && !fired) {
        setFired(true);
        if (typeof onLive === 'function') onLive();
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startTime, onLive, fired]);

  if (!startTime || remaining <= 0) return null;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-medium border border-blue-200 ${className}`}
        data-testid="upcoming-countdown-badge"
      >
        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        Opens in {_fmt(remaining)}
      </span>
    );
  }

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-800 text-sm font-semibold border border-blue-200 shadow-sm ${className}`}
      data-testid="upcoming-countdown-badge"
    >
      <svg className="h-4 w-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
      Bidding opens in {_fmt(remaining)}
    </div>
  );
};

export default UpcomingCountdownBadge;
