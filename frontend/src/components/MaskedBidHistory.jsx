/**
 * iter369 — Masked bid history component.
 *
 * Displays the full bid history for a lot with strict privacy compliance
 * (Law 25 / PIPEDA / GDPR):
 *   • bidder identity → initials only ("SN")
 *   • IP address → first octet + last octet only ("131.***.***.63")
 *   • Never exposes full name, full email, full IP or user id
 *
 * Sourced from GET /api/multi-item-listings/{id}/lots/{N}/bids-public
 * so the browser never sees the raw bidder documents.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Trophy, TrendingDown, Zap, Loader2 } from 'lucide-react';
import { Badge } from './ui/badge';
import API_BASE from '../config';
import { formatCurrency } from '../utils/currencyFormatter';

const relativeTime = (iso, isFR) => {
  if (!iso) return '';
  const d = new Date(iso);
  const diffSec = Math.max(1, Math.floor((Date.now() - d.getTime()) / 1000));
  if (diffSec < 60) return isFR ? `il y a ${diffSec}s` : `${diffSec}s ago`;
  const m = Math.floor(diffSec / 60);
  if (m < 60) return isFR ? `il y a ${m} min` : `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return isFR ? `il y a ${h} h` : `${h}h ago`;
  const days = Math.floor(h / 24);
  return isFR ? `il y a ${days} j` : `${days}d ago`;
};

export default function MaskedBidHistory({ auctionId, lotNumber, limit = 20 }) {
  const { i18n } = useTranslation();
  const isFR = i18n.language?.startsWith('fr');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auctionId || lotNumber == null) return;
    let cancelled = false;
    const fetchOnce = () => axios
      .get(`${API_BASE}/multi-item-listings/${auctionId}/lots/${lotNumber}/bids-public`, {
        params: { limit },
        timeout: 8000,
      })
      .then((res) => { if (!cancelled) { setData(res.data); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });

    fetchOnce();
    // Poll every 10 s while tab is visible — keeps the "leading" bidder fresh.
    const t = setInterval(() => { if (!document.hidden) fetchOnce(); }, 10000);
    return () => { cancelled = true; clearInterval(t); };
  }, [auctionId, lotNumber, limit]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400" data-testid="masked-bid-history-loading">
        <Loader2 className="h-4 w-4 animate-spin" />
        {isFR ? "Chargement…" : 'Loading…'}
      </div>
    );
  }
  if (!data || data.total_bids === 0) {
    return (
      <div className="text-sm text-slate-500 dark:text-slate-400 py-3 text-center" data-testid="masked-bid-history-empty">
        {isFR ? 'Aucune enchère pour le moment. Soyez le premier!' : 'No bids yet. Be the first!'}
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="masked-bid-history">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
        <span data-testid="masked-bid-total">{data.total_bids} {isFR ? 'enchères' : 'bids'}</span>
        <span className="text-slate-400">·</span>
        <span data-testid="masked-bid-bidders">{data.unique_bidders} {isFR ? 'enchérisseurs' : 'bidders'}</span>
        {data.leading_bidder_initials && (
          <>
            <span className="text-slate-400">·</span>
            <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400" data-testid="masked-bid-leader">
              <Trophy className="h-3 w-3" />
              {isFR ? 'Meneur' : 'Leader'}: <strong>{data.leading_bidder_initials}</strong>
            </span>
          </>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" data-testid="masked-bid-rows">
          <thead className="text-slate-500 dark:text-slate-400 uppercase text-[10px]">
            <tr>
              <th className="text-left py-1 pr-2">{isFR ? 'Bidder' : 'Bidder'}</th>
              <th className="text-left py-1 pr-2">IP</th>
              <th className="text-right py-1 pr-2">{isFR ? 'Montant' : 'Amount'}</th>
              <th className="text-left py-1 pr-2">{isFR ? 'Quand' : 'When'}</th>
              <th className="text-left py-1">{isFR ? 'Statut' : 'Status'}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {data.bids.map((b, i) => {
              const isLead = b.status === 'leading';
              return (
                <tr key={i} className={isLead ? 'bg-emerald-50 dark:bg-emerald-950/30' : ''} data-testid={`masked-bid-row-${i}`}>
                  <td className="py-1.5 pr-2">
                    <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-slate-200 dark:bg-slate-700 text-[10px] font-bold text-slate-800 dark:text-slate-100" data-testid={`masked-bid-initials-${i}`}>
                      {b.initials}
                    </span>
                  </td>
                  <td className="py-1.5 pr-2 font-mono text-[11px] text-slate-500 dark:text-slate-400" data-testid={`masked-bid-ip-${i}`}>
                    {b.ip_masked || '—'}
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono font-semibold text-slate-800 dark:text-slate-100">
                    {formatCurrency(b.amount)}
                    {b.bid_type === 'auto' && (
                      <span title="Auto-Bid" className="inline-flex ml-1 text-cyan-600"><Zap className="h-3 w-3 inline" /></span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 text-slate-500 dark:text-slate-400" title={b.created_at}>
                    {relativeTime(b.created_at, isFR)}
                  </td>
                  <td className="py-1.5">
                    {isLead ? (
                      <Badge className="bg-emerald-600 text-white border-0 text-[10px]">
                        <Trophy className="h-3 w-3 mr-0.5" />
                        {isFR ? 'En tête' : 'Leading'}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-rose-600 border-rose-200">
                        <TrendingDown className="h-3 w-3 mr-0.5" />
                        {isFR ? 'Dépassé' : 'Outbid'}
                      </Badge>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
