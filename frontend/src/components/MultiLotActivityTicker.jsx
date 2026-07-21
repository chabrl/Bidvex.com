/**
 * iter367 P1 — Multi-lot live activity ticker.
 * Polls `/api/lots/{auction_id}/recent-activity` every 15 s and renders
 * a compact scrolling list of the newest bid events across all lots.
 * Auto-pauses when the tab is hidden to save battery.
 */
import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Zap, Gavel } from 'lucide-react';
import API_BASE from '../config';
import { formatCurrency } from '../utils/currencyFormatter';

export default function MultiLotActivityTicker({ auctionId, onLotClick }) {
  const { i18n } = useTranslation();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);
  const isFR = i18n.language === 'fr';

  useEffect(() => {
    if (!auctionId) return;
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const res = await axios.get(`${API_BASE}/lots/${auctionId}/recent-activity?limit=10`, { timeout: 8000 });
        if (!cancelled) {
          setEvents(res.data?.events || []);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    };

    fetchOnce();
    timerRef.current = setInterval(() => {
      if (!document.hidden) fetchOnce();
    }, 15000);

    return () => {
      cancelled = true;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [auctionId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 p-4 animate-pulse" data-testid="ticker-loading">
        <div className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded mb-3" />
        <div className="h-3 w-full bg-slate-200 dark:bg-slate-700 rounded" />
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 p-4 text-center" data-testid="ticker-empty">
        <Gavel className="h-5 w-5 mx-auto text-slate-400 mb-1" />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {isFR ? 'Aucune enchère récente — soyez le premier!' : 'No recent bids — be the first!'}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-cyan-200 dark:border-cyan-900 bg-gradient-to-r from-cyan-50 to-blue-50 dark:from-cyan-950/40 dark:to-blue-950/40" data-testid="multi-lot-activity-ticker">
      <div className="flex items-center gap-2 px-4 pt-3">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <h3 className="text-sm font-bold text-cyan-900 dark:text-cyan-100">
          {isFR ? 'Activité en direct' : 'Live activity'}
        </h3>
        <span className="text-[10px] text-cyan-700 dark:text-cyan-300 ml-auto uppercase tracking-wide">
          {isFR ? 'Actualisé toutes les 15s' : 'Updates every 15s'}
        </span>
      </div>
      <ul className="divide-y divide-cyan-100 dark:divide-cyan-900 px-4 pb-3 max-h-56 overflow-y-auto no-scrollbar">
        {events.map((e, i) => (
          <li
            key={`${e.lot_id}-${e.timestamp}-${i}`}
            className="flex items-center gap-3 py-2 cursor-pointer hover:bg-white/50 dark:hover:bg-white/5 rounded transition-colors"
            onClick={() => onLotClick && e.lot_id != null && onLotClick(e.lot_id)}
            data-testid={`ticker-event-${i}`}
          >
            <Zap className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
            <div className="flex-1 min-w-0 text-xs">
              <span className="font-semibold text-slate-900 dark:text-white">{e.bidder_alias}</span>
              <span className="text-slate-500 dark:text-slate-400 mx-1">
                {isFR ? 'a misé' : 'bid'}
              </span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(e.amount)}</span>
              <span className="text-slate-500 dark:text-slate-400 mx-1">
                {isFR ? 'sur' : 'on'}
              </span>
              <span className="truncate text-slate-700 dark:text-slate-300">
                {e.lot_title}
              </span>
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 flex-shrink-0">{e.time_ago}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
