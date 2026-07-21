/**
 * iter367 P1 — Bid increment reference table for multi-lot pages.
 * Displays the tiered bid-increment structure so buyers know the exact
 * next-bid amount at any price level. Static reference — mirrors
 * BidVex's platform-wide increment ladder (see backend
 * services/bid_increment.py if it exists, else the well-known ladder).
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, TrendingUp } from 'lucide-react';

const INCREMENTS = [
  { min: 0,       max: 24.99,      step: 1 },
  { min: 25,      max: 99.99,      step: 2.50 },
  { min: 100,     max: 499.99,     step: 5 },
  { min: 500,     max: 999.99,     step: 10 },
  { min: 1000,    max: 2499.99,    step: 25 },
  { min: 2500,    max: 4999.99,    step: 50 },
  { min: 5000,    max: 9999.99,    step: 100 },
  { min: 10000,   max: 24999.99,   step: 250 },
  { min: 25000,   max: 49999.99,   step: 500 },
  { min: 50000,   max: Infinity,   step: 1000 },
];

const fmt = (v) => v === Infinity ? '∞' : `$${v.toLocaleString('en-CA', { minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 2 })}`;

export default function BidIncrementTable({ defaultOpen = false }) {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const isFR = i18n.language === 'fr';

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden" data-testid="bid-increment-table">
      <button
        type="button"
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        data-testid="bid-increment-toggle"
      >
        <TrendingUp className="h-4 w-4 text-cyan-600" />
        <span className="font-semibold text-sm text-slate-900 dark:text-white flex-1 text-left">
          {isFR ? 'Barème des incréments d\'enchère' : 'Bid Increment Table'}
        </span>
        {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
      </button>
      {open && (
        <div className="border-t border-slate-200 dark:border-slate-800">
          <table className="w-full text-xs" data-testid="bid-increment-rows">
            <thead className="bg-slate-50 dark:bg-slate-800/50">
              <tr>
                <th className="text-left py-2 px-4 font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                  {isFR ? 'Prix courant' : 'Current price'}
                </th>
                <th className="text-right py-2 px-4 font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                  {isFR ? 'Incrément' : 'Increment'}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {INCREMENTS.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td className="py-1.5 px-4 text-slate-700 dark:text-slate-300 font-mono">
                    {fmt(row.min)} — {fmt(row.max)}
                  </td>
                  <td className="py-1.5 px-4 text-right font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                    +{fmt(row.step)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 bg-amber-50 dark:bg-amber-950/30 border-t border-amber-200 dark:border-amber-900 text-[10px] text-amber-800 dark:text-amber-200">
            {isFR
              ? 'Les incréments s\'appliquent automatiquement à chaque enchère. La fonction Enchère auto respecte ce barème.'
              : 'Increments apply automatically to every bid. Auto-Bid uses this same ladder.'}
          </div>
        </div>
      )}
    </div>
  );
}
