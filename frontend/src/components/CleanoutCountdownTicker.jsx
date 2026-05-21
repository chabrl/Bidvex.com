/**
 * BidVex — Phase 6.2 Task 4
 * Cleanout Countdown Ticker (live every second).
 *
 *   • Green:        > 48h remaining
 *   • Amber:        24–48h remaining
 *   • Flashing red: < 24h remaining
 *   • Grey:         already past deadline / completed
 */
import React, { useEffect, useState } from 'react';

const _pad = (n) => String(n).padStart(2, '0');

export default function CleanoutCountdownTicker({ deadlineAt, status }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (!deadlineAt) return null;

  const deadlineMs = new Date(deadlineAt).getTime();
  const remainingMs = deadlineMs - now;
  const remainingH = remainingMs / 3_600_000;

  // Resolved states render a static badge.
  if (['released', 'forfeited', 'captured'].includes(status)) {
    const tone = status === 'released'
      ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
      : 'bg-slate-200 text-slate-700 border-slate-300';
    return (
      <div
        className={`rounded-lg border px-4 py-3 text-sm font-semibold ${tone}`}
        data-testid="cleanout-ticker-resolved"
      >
        {status === 'released' && '✅ Cleanout approved — deposit released.'}
        {status === 'forfeited' && '⛔ Deposit forfeited.'}
        {status === 'captured' && '⛔ Deposit captured.'}
      </div>
    );
  }

  // Active countdown
  const isPastDue = remainingMs <= 0;
  const absMs = Math.abs(remainingMs);
  const hours = Math.floor(absMs / 3_600_000);
  const minutes = Math.floor((absMs % 3_600_000) / 60_000);
  const seconds = Math.floor((absMs % 60_000) / 1000);

  let tone, label;
  if (isPastDue) {
    tone = 'bg-red-100 text-red-900 border-red-400 animate-pulse';
    label = '⚠️ PAST DEADLINE';
  } else if (remainingH < 24) {
    tone = 'bg-red-100 text-red-900 border-red-400 animate-pulse';
    label = '🔴 URGENT — Cleanout Deadline Approaching';
  } else if (remainingH < 48) {
    tone = 'bg-amber-100 text-amber-900 border-amber-400';
    label = '🟡 Cleanout Deadline';
  } else {
    tone = 'bg-emerald-100 text-emerald-900 border-emerald-400';
    label = '🟢 Cleanout Deadline';
  }

  return (
    <div
      className={`rounded-lg border px-4 py-3 ${tone}`}
      data-testid="cleanout-countdown-ticker"
    >
      <div className="text-xs font-semibold uppercase tracking-wide opacity-80 mb-1">{label}</div>
      <div
        className="text-2xl font-mono font-bold tabular-nums"
        data-testid="cleanout-countdown-value"
      >
        {isPastDue ? '−' : ''}{_pad(hours)}h {_pad(minutes)}m {_pad(seconds)}s
      </div>
      {status === 'pending_verification' && (
        <div className="text-xs mt-2 italic opacity-90">
          ⏳ Verification requested — awaiting admin approval.
        </div>
      )}
    </div>
  );
}
