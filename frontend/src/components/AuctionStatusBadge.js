/**
 * AuctionStatusBadge + CountdownTimer — iter178 (FIX 4)
 * =======================================================
 * Shared bilingual status badge (UPCOMING / LIVE / ENDED) and a
 * zero-dep countdown timer for upcoming auctions.
 */
import React, { useEffect, useState } from 'react';

export const AuctionStatusBadge = ({ status, endTime, startTime, className = '' }) => {
  const now = new Date();
  const start = startTime ? new Date(startTime) : null;
  const end = endTime ? new Date(endTime) : null;

  const isUpcoming = status === 'upcoming' || (start && start > now);
  const isLive = !isUpcoming && status === 'active' && (!end || end > now);
  const isEnded = !isUpcoming && !isLive && (status === 'ended' || status === 'sold' || status === 'unsold' || (end && end <= now));

  if (isUpcoming) {
    return (
      <div
        data-testid="auction-status-upcoming"
        className={`bg-blue-100 text-blue-700 border border-blue-300 px-3 py-1 rounded-full text-xs font-bold inline-flex items-center gap-1 ${className}`}
      >
        🗓️ <span>UPCOMING · À VENIR</span>
      </div>
    );
  }
  if (isLive) {
    return (
      <div
        data-testid="auction-status-live"
        className={`bg-green-500 text-white px-3 py-1 rounded-full text-xs font-bold inline-flex items-center gap-1 animate-pulse ${className}`}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-white"></span>
        <span>LIVE · EN DIRECT</span>
      </div>
    );
  }
  if (isEnded) {
    return (
      <div
        data-testid="auction-status-ended"
        className={`bg-gray-200 text-gray-600 px-3 py-1 rounded-full text-xs font-bold inline-flex items-center gap-1 ${className}`}
      >
        <span>ENDED · TERMINÉE</span>
      </div>
    );
  }
  return null;
};

export const CountdownTimer = ({ targetTime, testId = 'countdown-timer' }) => {
  const [remaining, setRemaining] = useState(() => Math.max(0, new Date(targetTime) - new Date()));

  useEffect(() => {
    const t = setInterval(() => {
      setRemaining(Math.max(0, new Date(targetTime) - new Date()));
    }, 1000);
    return () => clearInterval(t);
  }, [targetTime]);

  if (remaining <= 0) {
    return <span data-testid={testId} className="font-mono">00:00:00</span>;
  }

  const d = Math.floor(remaining / 86_400_000);
  const h = Math.floor((remaining % 86_400_000) / 3_600_000);
  const m = Math.floor((remaining % 3_600_000) / 60_000);
  const s = Math.floor((remaining % 60_000) / 1000);
  const pad = (n) => String(n).padStart(2, '0');

  return (
    <span data-testid={testId} className="font-mono font-bold">
      {d > 0 && `${d}d `}{pad(h)}:{pad(m)}:{pad(s)}
    </span>
  );
};

export default AuctionStatusBadge;
