/**
 * iter368 — Bid Increment Table (dynamic).
 *
 * Fetches the seller-selected increment schedule from
 * `GET /api/multi-item-listings/{auctionId}/increment-info` and renders it.
 *
 * Supports every increment strategy the backend exposes:
 *   • "tiered"      — 8-tier ladder (BidVex default)
 *   • "simplified"  — 4-tier ladder
 *   • "fixed"       — single flat increment
 *   • (future modes automatically render as their own schedule rows)
 *
 * The component NEVER hardcodes tiers. If the backend adds a new strategy
 * tomorrow, this table renders it correctly with zero client-side change.
 * The same endpoint is the source of truth for QuickBid pill amounts.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, TrendingUp, Loader2 } from 'lucide-react';
import API_BASE from '../config';

export default function BidIncrementTable({ auctionId, defaultOpen = false }) {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const isFR = i18n.language === 'fr';

  useEffect(() => {
    if (!auctionId || !open || data) return;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    axios
      .get(`${API_BASE}/multi-item-listings/${auctionId}/increment-info`, { timeout: 8000 })
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch((e) => { if (!cancelled) setErr(e.response?.data?.detail || 'Unable to load bid schedule'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [auctionId, open, data]);

  const strategyLabel = (opt) => {
    switch ((opt || '').toLowerCase()) {
      case 'simplified': return isFR ? 'Barème simplifié' : 'Simplified schedule';
      case 'fixed':      return isFR ? 'Incrément fixe' : 'Fixed increment';
      case 'tiered':
      default:           return isFR ? 'Barème par paliers' : 'Tiered schedule';
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden" data-testid="bid-increment-table" data-auction-id={auctionId || ''}>
      <button
        type="button"
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        data-testid="bid-increment-toggle"
      >
        <TrendingUp className="h-4 w-4 text-cyan-600" />
        <span className="font-semibold text-sm text-slate-900 dark:text-white flex-1 text-left">
          {isFR ? "Barème des incréments d'enchère" : 'Bid Increment Table'}
        </span>
        {data?.increment_option && (
          <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400 hidden sm:inline" data-testid="bid-increment-strategy">
            {strategyLabel(data.increment_option)}
          </span>
        )}
        {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
      </button>
      {open && (
        <div className="border-t border-slate-200 dark:border-slate-800">
          {loading && (
            <div className="p-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400" data-testid="bid-increment-loading">
              <Loader2 className="h-4 w-4 animate-spin" />
              {isFR ? 'Chargement du barème…' : 'Loading schedule…'}
            </div>
          )}
          {err && !loading && (
            <div className="p-4 text-sm text-rose-600 dark:text-rose-400" data-testid="bid-increment-error">{err}</div>
          )}
          {!loading && !err && data && (
            <>
              {/* iter368 — Fixed mode: single "Current Bid → Next Bid Increment" row.
                    Tiered / Simplified / future modes: multi-row schedule from server. */}
              {data.increment_option === 'fixed' ? (
                <div className="p-4" data-testid="bid-increment-fixed">
                  <div className="grid grid-cols-2 gap-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 p-4">
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400 font-semibold">
                        {isFR ? 'Enchère courante' : 'Current bid'}
                      </div>
                      <div className="text-lg font-mono text-slate-800 dark:text-slate-200 mt-0.5">
                        {isFR ? 'Toute valeur' : 'Any amount'}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400 font-semibold">
                        {isFR ? 'Prochain incrément' : 'Next bid increment'}
                      </div>
                      <div className="text-lg font-mono font-bold text-emerald-600 dark:text-emerald-400 mt-0.5" data-testid="bid-increment-fixed-value">
                        +${Number(data.fixed_increment).toLocaleString('en-CA')}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
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
                    {(data.schedule || []).map((row, i) => (
                      <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40" data-testid={`bid-increment-tier-${i}`}>
                        <td className="py-1.5 px-4 text-slate-700 dark:text-slate-300 font-mono">{row.range_label}</td>
                        <td className="py-1.5 px-4 text-right font-semibold text-emerald-600 dark:text-emerald-400 font-mono">{row.increment_label}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <div className="px-4 py-2 bg-amber-50 dark:bg-amber-950/30 border-t border-amber-200 dark:border-amber-900 text-[10px] text-amber-800 dark:text-amber-200">
                {isFR
                  ? "Les incréments s'appliquent automatiquement à chaque enchère. Enchère auto et Quick Bid respectent ce barème."
                  : 'Increments apply automatically to every bid. Auto-Bid and Quick Bid use this same ladder.'}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
