/**
 * QuickBidButtons — iter175
 * ==========================
 * Three one-tap "+$X" pills above any bid input. Multipliers scale by the
 * auction's `bidIncrement`:
 *   • +$X   = 1× bid_increment
 *   • +$Y   = 5× bid_increment
 *   • +$Z   = 10× bid_increment
 * (so a $10-increment storage auction shows +$10 / +$50 / +$100, while a
 *  $100-increment vehicle auction shows +$100 / +$500 / +$1,000)
 *
 * UX: clicking a pill stages the candidate amount AND surfaces a "Confirm bid"
 * banner directly below — preventing accidental submissions on mobile thumbs.
 * Confirming calls onConfirm(amount); cancelling clears the staged amount.
 *
 * Bilingual (Bill 96): every visible string ships EN + FR simultaneously.
 */
import React, { useState } from 'react';
import { Button } from './ui/button';
import { Loader2, Zap, Check, X } from 'lucide-react';

const formatCAD = (n) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n);

const QuickBidButtons = ({
  currentBid = 0,
  bidIncrement = 10,
  onConfirm,
  disabled = false,
  loading = false,
  testidPrefix = 'quick-bid',
}) => {
  const [staged, setStaged] = useState(null); // candidate amount

  // Multipliers — at minimum +1, +5, +10 (scaled by increment)
  const multipliers = [1, 5, 10];
  const base = Number(currentBid) || 0;
  const incr = Number(bidIncrement) || 10;

  const handlePill = (mult) => {
    if (disabled || loading) return;
    const amt = +(base + (incr * mult)).toFixed(2);
    setStaged(amt);
  };

  const handleCancel = () => setStaged(null);
  const handleConfirm = async () => {
    if (!staged || disabled || loading) return;
    await onConfirm?.(staged);
    setStaged(null);
  };

  return (
    <div className="space-y-2" data-testid={`${testidPrefix}-container`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
          <Zap className="h-3 w-3" />
          Quick Bid · Offre rapide
        </span>
        <span className="text-[10px] text-muted-foreground">
          One-tap · Un clic
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {multipliers.map((m) => {
          const delta = incr * m;
          const candidate = +(base + delta).toFixed(2);
          const isStaged = staged === candidate;
          return (
            <button
              key={m}
              type="button"
              onClick={() => handlePill(m)}
              disabled={disabled || loading}
              data-testid={`${testidPrefix}-pill-${m}x`}
              className={`relative px-3 py-2 rounded-full text-sm font-bold transition-all border-2 ${
                isStaged
                  ? 'bg-blue-600 text-white border-blue-700 shadow-md scale-[1.02]'
                  : 'bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:hover:bg-blue-900/40 dark:text-blue-200 dark:border-blue-900'
              } ${disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span className="block leading-tight">+{formatCAD(delta)}</span>
              <span className="block text-[10px] font-normal opacity-80 leading-tight">
                = {formatCAD(candidate)}
              </span>
            </button>
          );
        })}
      </div>

      {staged !== null && (
        <div
          data-testid={`${testidPrefix}-confirm-banner`}
          className="rounded-md border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-700 p-3 space-y-2 animate-in fade-in slide-in-from-top-1"
        >
          <p className="text-xs text-amber-900 dark:text-amber-100 leading-snug">
            <span className="font-bold">Confirm bid · Confirmez l'offre</span>
            <br />
            You're about to bid <strong>{formatCAD(staged)}</strong>. Vous êtes sur le point d'enchérir <strong>{formatCAD(staged)}</strong>.
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={handleConfirm}
              disabled={loading}
              className="flex-1 bg-amber-600 hover:bg-amber-700 text-white"
              data-testid={`${testidPrefix}-confirm-btn`}
            >
              {loading
                ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" />…</>
                : <><Check className="h-3 w-3 mr-1" />Confirm · Confirmer</>}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleCancel}
              disabled={loading}
              data-testid={`${testidPrefix}-cancel-btn`}
            >
              <X className="h-3 w-3 mr-1" />
              Cancel · Annuler
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuickBidButtons;
