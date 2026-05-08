/**
 * iter202 Phase A — Vehicle Auctions Countdown Hook
 * ==================================================
 * Performance constraint #4 (sprint spec): ONE global setInterval per page.
 *
 * Returns a fresh ISO timestamp once per second and a `formatRemaining(endTime)`
 * helper. All vehicle cards consume the same hook so we never spawn a timer
 * per card, even when the grid renders 50+ items.
 */
import { useEffect, useState, useCallback } from 'react';

const PAD = (n) => String(n).padStart(2, '0');

export const formatRemaining = (endTime, now = Date.now(), opts = {}) => {
  if (!endTime) return { ended: true, label: '—', short: '—', critical: false, ms: 0 };
  const end = typeof endTime === 'string' ? new Date(endTime).getTime() : endTime;
  if (Number.isNaN(end)) return { ended: true, label: '—', short: '—', critical: false, ms: 0 };
  const diff = end - now;
  if (diff <= 0) return { ended: true, label: opts.endedLabel || 'Ended', short: '00:00', critical: true, ms: 0 };

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  let label;
  if (days > 0) label = `${days}d ${PAD(hours)}h`;
  else if (hours > 0) label = `${PAD(hours)}h ${PAD(minutes)}m`;
  else label = `${PAD(minutes)}m ${PAD(seconds)}s`;

  // Critical = under 1 hour (used for orange "ending soon" pulse)
  const critical = days === 0 && hours === 0;

  return {
    ended: false,
    label,
    short: days > 0 ? `${days}d` : `${PAD(hours)}:${PAD(minutes)}:${PAD(seconds)}`,
    critical,
    ms: diff,
  };
};

const useVehicleCountdown = () => {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const format = useCallback((endTime, opts) => formatRemaining(endTime, now, opts), [now]);

  return { now, format };
};

export default useVehicleCountdown;
