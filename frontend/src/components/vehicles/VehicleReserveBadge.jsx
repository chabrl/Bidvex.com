/**
 * iter484.2 Gate 2 — Vehicle Reserve Status Chip
 * ===============================================
 *
 * Buyer-facing chip that surfaces the AUTHORITATIVE reserve state of a
 * vehicle auction.  The chip NEVER exposes the raw reserve amount.
 *
 * Source of truth: backend `reserve_state` field emitted by
 * `mask_reserve_for_buyer()` in `services/reserve_price_gate.py`
 * (`none | met | not_met`).  Fallback: derive from `has_reserve` +
 * `reserve_met` for backwards-compat with older polling frames.
 *
 * Scope: VEHICLES ONLY.  Do NOT reuse on storage / liquidation /
 * general-merchandise / non-vehicle multi-item auctions.
 *
 * Test IDs:
 *   - `vehicle-reserve-badge` (root)
 *   - `vehicle-reserve-badge-{none|met|not_met|set}`
 *
 * @param {object} props
 * @param {object|null} props.doc  vehicle listing / lot (data-driven)
 * @param {'chip'|'card'} [props.variant] 'chip' (compact) | 'card' (with subtitle)
 * @param {string} [props.className]
 * @param {boolean} [props.reserveMetRealtime] override from useVehicleBidding
 *                                             realtime channel (optional)
 * @param {boolean} [props.hideWhenNone] if true, render nothing when no reserve
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Lock, CheckCircle2 } from 'lucide-react';

function resolveState(doc, reserveMetRealtime) {
  if (!doc || typeof doc !== 'object') return 'unknown';
  // Realtime "met" override — the WebSocket channel wins the moment
  // the crossing bid lands, even before a fresh GET refreshes the doc.
  if (reserveMetRealtime === true) return 'met';
  // Backend-provided authoritative state (preferred)
  if (typeof doc.reserve_state === 'string') {
    const s = doc.reserve_state.toLowerCase();
    if (s === 'none' || s === 'met' || s === 'not_met') return s;
  }
  // Fallback for backwards-compat with older API frames
  const hasReserve = !!doc.has_reserve;
  if (!hasReserve) return 'none';
  return doc.reserve_met ? 'met' : 'not_met';
}

export default function VehicleReserveBadge({
  doc,
  variant = 'chip',
  className = '',
  reserveMetRealtime,
  hideWhenNone = false,
}) {
  const { i18n } = useTranslation();
  const isFR = (i18n.language || '').startsWith('fr');
  const state = resolveState(doc, reserveMetRealtime);
  if (state === 'unknown') return null;
  if (state === 'none' && hideWhenNone) return null;

  const CONFIG = {
    none: {
      label:   isFR ? 'Sans réserve'    : 'No Reserve',
      subtitle:isFR ? 'Ce véhicule sera vendu à la plus haute enchère.'
                    : 'This vehicle will sell to the highest bidder.',
      tint:    'border-emerald-200 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
      Icon:    CheckCircle2,
    },
    met: {
      label:   isFR ? 'Réserve atteinte' : 'Reserve Met',
      subtitle:isFR ? "Le prix de réserve du vendeur est atteint\u00a0; la vente se réalisera à la clôture."
                    : "The seller's reserve price is met — the auction will complete at close.",
      tint:    'border-emerald-300 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200 dark:border-emerald-700',
      Icon:    CheckCircle2,
    },
    not_met: {
      label:   isFR ? 'Réserve non atteinte' : 'Reserve Not Met',
      subtitle:isFR ? 'L\u2019enchère actuelle n\u2019a pas encore atteint le prix de réserve du vendeur.'
                    : 'The current bid has not yet reached the seller\u2019s reserve price.',
      tint:    'border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-800',
      Icon:    Lock,
    },
  };
  const { label, subtitle, tint, Icon } = CONFIG[state];

  if (variant === 'card') {
    return (
      <div
        className={`rounded-lg border p-3 flex items-start gap-2.5 ${tint} ${className}`}
        data-testid="vehicle-reserve-badge"
        data-state={state}
      >
        <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div
            className="text-sm font-semibold leading-tight"
            data-testid={`vehicle-reserve-badge-${state}`}
          >
            {label}
          </div>
          <div className="text-[11px] opacity-90 mt-0.5 leading-snug">{subtitle}</div>
        </div>
      </div>
    );
  }

  // chip variant (default) — used on cards + inline on detail
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tint} ${className}`}
      data-testid="vehicle-reserve-badge"
      data-state={state}
      title={subtitle}
    >
      <span data-testid={`vehicle-reserve-badge-${state}`}>
        <Icon className="h-3 w-3" aria-hidden="true" />
      </span>
      <span>{label}</span>
    </span>
  );
}
