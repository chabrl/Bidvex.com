import React, { useEffect, useState } from 'react';

const pad = (n) => String(n).padStart(2, '0');

/**
 * Live countdown to a UTC ISO end-time.
 * Goes red when <10 min remain; shows "Ended" when past.
 */
const StorageCountdown = ({ endTime, compact = false }) => {
  const [remaining, setRemaining] = useState(() => {
    const t = new Date(endTime).getTime() - Date.now();
    return Math.max(0, t);
  });

  useEffect(() => {
    const tick = () => setRemaining(Math.max(0, new Date(endTime).getTime() - Date.now()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [endTime]);

  if (remaining === 0) {
    return <span className="text-red-600 font-bold text-sm">Ended / Terminée</span>;
  }
  const totalSec = Math.floor(remaining / 1000);
  const days = Math.floor(totalSec / 86400);
  const hours = Math.floor((totalSec % 86400) / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  const urgent = remaining < 10 * 60 * 1000;

  return (
    <span
      className={`font-mono tabular-nums ${urgent ? 'text-red-600' : 'text-slate-700 dark:text-slate-200'} ${compact ? 'text-xs' : 'text-sm'}`}
      data-testid="storage-countdown"
    >
      {days > 0 && <span>{days}d </span>}
      {pad(hours)}:{pad(minutes)}:{pad(seconds)}
    </span>
  );
};

export default StorageCountdown;
