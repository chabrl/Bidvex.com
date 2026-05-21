/**
 * BidVex — Phase 6.2 Task 6B
 * My Auctions tab — 4 status filters (Drafts / Upcoming / Live / Ended)
 * with per-tab counts. Backend: GET /api/facility/auctions
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useSearchParams, useNavigate } from 'react-router-dom';

import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Loader2, Package, Plus } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const TABS = [
  { key: 'drafts',   label: 'Drafts' },
  { key: 'upcoming', label: 'Upcoming' },
  { key: 'live',     label: 'Live' },
  { key: 'ended',    label: 'Ended' },
];

export default function FacilityAuctions() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialStatus = searchParams.get('status') || 'live';
  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [data, setData] = useState({ auctions: [], counts: {} });
  const [loading, setLoading] = useState(true);

  const fetchAuctions = useCallback(async () => {
    setLoading(true);
    try {
      const token = window.localStorage.getItem('token');
      const res = await axios.get(`${API}/api/facility/auctions?status=${statusFilter}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setData(res.data || { auctions: [], counts: {} });
    } catch (e) {
      console.error('[FacilityAuctions] load failed', e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchAuctions(); }, [fetchAuctions]);

  // Keep URL in sync with selected filter
  useEffect(() => {
    if (searchParams.get('status') !== statusFilter) {
      setSearchParams({ status: statusFilter }, { replace: true });
    }
  }, [statusFilter, searchParams, setSearchParams]);

  const counts = data.counts || {};

  return (
    <Card data-testid="facility-auctions-card">
      <CardHeader>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <CardTitle>My Storage Auctions</CardTitle>
          <Button
            onClick={() => navigate('/storage-auctions/create')}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            size="sm"
            data-testid="facility-create-auction-btn"
          >
            <Plus className="h-4 w-4 mr-1" /> New Auction
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3" data-testid="facility-auction-tabs">
          {TABS.map((tab) => {
            const isActive = statusFilter === tab.key;
            const c = counts[tab.key] ?? 0;
            return (
              <button
                type="button"
                key={tab.key}
                onClick={() => setStatusFilter(tab.key)}
                data-testid={`facility-tab-${tab.key}`}
                className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {tab.label} ({c})
              </button>
            );
          })}
        </div>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="text-center py-10"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></div>
        )}

        {!loading && data.auctions.length === 0 && (
          <div className="text-center py-12 text-sm text-muted-foreground" data-testid="facility-auctions-empty">
            <Package className="h-10 w-10 mx-auto mb-3 opacity-40" />
            No auctions in this tab.
          </div>
        )}

        <div className="space-y-3">
          {!loading && data.auctions.map((a) => {
            const isPending = ['pending_ai_review', 'pending_admin_review', 'pending_review'].includes(a.status);
            return (
              <div
                key={a.id}
                className="border rounded-lg p-3 flex flex-col sm:flex-row gap-3 hover:bg-slate-50 transition-colors w-full overflow-hidden"
                data-testid={`facility-auction-${a.id}`}
              >
                <div className="w-20 h-20 sm:w-24 sm:h-20 rounded bg-slate-200 overflow-hidden flex-shrink-0">
                  {a.images?.[0] ? (
                    <img src={a.images[0]} alt={a.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-2xl">📦</div>
                  )}
                </div>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <h3 className="font-semibold text-sm break-words leading-snug">{a.title}</h3>
                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    {isPending ? (
                      <Badge className="bg-amber-100 text-amber-900 border-amber-300">⏳ Under Review — 5 to 50 min</Badge>
                    ) : (
                      <Badge variant="outline">{a.status?.toUpperCase()}</Badge>
                    )}
                    {statusFilter === 'live' && a.bid_count !== undefined && (
                      <span className="text-xs text-muted-foreground">
                        {a.bid_count} bids · ${Number(a.current_bid || a.current_price || 0).toFixed(2)}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    <Button
                      onClick={() => navigate(`/storage-auctions/${a.id}`)}
                      variant="outline"
                      size="sm"
                      data-testid={`facility-view-${a.id}`}
                    >
                      View
                    </Button>
                    {statusFilter === 'drafts' && (
                      <>
                        <Button
                          onClick={() => navigate(`/edit-listing/${a.id}`)}
                          variant="outline"
                          size="sm"
                          data-testid={`facility-edit-${a.id}`}
                        >
                          Edit
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
