import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * BidVex — Phase 6.2 Task 5
 * Admin Storage Hold Settlements desk.
 *
 * Lists every cleanout-hold row (across every facility) with quick
 * Approve / Forfeit actions wired to the existing release-deposit API.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Loader2, RefreshCw } from 'lucide-react';
import { authHeaders } from '../../utils/authToken';

const API = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_COLORS = {
  held: 'bg-amber-100 text-amber-900 border-amber-300',
  pending_verification: 'bg-blue-100 text-blue-900 border-blue-300',
  released: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  forfeited: 'bg-red-100 text-red-900 border-red-300',
  captured: 'bg-red-100 text-red-900 border-red-300',
};

export default function StorageHoldSettlementsTab() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [facilityFilter, setFacilityFilter] = useState('');
  const [actionRowId, setActionRowId] = useState(null);
  const [forfeitReason, setForfeitReason] = useState({});

  const fetchHolds = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      if (facilityFilter) params.set('facility_name', facilityFilter);
      const res = await axios.get(
        `${API}/api/admin/storage-auctions/cleanout-holds?${params.toString()}`,
        { headers: authHeaders() },
      );
      setRows(res.data?.rows || []);
      setTotal(res.data?.total || 0);
    } catch (e) {
      console.error(e);
      toast.error('Failed to load cleanout holds.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, facilityFilter]);

  useEffect(() => {
    fetchHolds();
  }, [fetchHolds]);

  const handleApprove = async (invoiceId) => {
    if (!window.confirm('Approve cleanout? Buyer\'s deposit will be released back to their card.')) return;
    setActionRowId(invoiceId);
    try {
      await axios.post(
        `${API}/api/admin/storage-auctions/${invoiceId}/release-deposit`,
        { forfeit_deposit: false, reason: 'Admin approved cleanout' },
        { headers: authHeaders() },
      );
      toast.success('Cleanout approved — deposit released.');
      await fetchHolds();
    } catch (e) {
      console.error(e);
      toast.error(extractErrorMessage(e) || 'Failed to approve cleanout.');
    } finally {
      setActionRowId(null);
    }
  };

  const handleForfeit = async (invoiceId) => {
    const reason = (forfeitReason[invoiceId] || '').trim();
    if (reason.length < 10) {
      toast.error('A detailed reason (≥ 10 chars) is required to forfeit a deposit.');
      return;
    }
    if (!window.confirm(`Forfeit this deposit?\n\nReason: "${reason}"\n\nThis will capture the funds via Stripe and log a violation against the buyer. This action cannot be undone.`)) return;
    setActionRowId(invoiceId);
    try {
      await axios.post(
        `${API}/api/admin/storage-auctions/${invoiceId}/release-deposit`,
        { forfeit_deposit: true, reason },
        { headers: authHeaders() },
      );
      toast.success('Deposit forfeited — funds captured.');
      await fetchHolds();
    } catch (e) {
      console.error(e);
      toast.error(extractErrorMessage(e) || 'Failed to forfeit deposit.');
    } finally {
      setActionRowId(null);
    }
  };

  return (
    <Card className="glassmorphism" data-testid="storage-hold-settlements-card">
      <CardHeader>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <CardTitle>Storage Hold Settlements</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Every cleanout deposit hold across all facilities. {total} total.
            </p>
          </div>
          <Button onClick={fetchHolds} variant="outline" size="sm" disabled={loading} data-testid="refresh-holds-btn">
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          {['', 'held', 'pending_verification', 'released', 'forfeited'].map((s) => (
            <button
              key={s || 'all'}
              onClick={() => setStatusFilter(s)}
              data-testid={`hold-status-filter-${s || 'all'}`}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                statusFilter === s ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-700 border-slate-200'
              }`}
            >
              {s === '' ? 'All' : s.replace('_', ' ')}
            </button>
          ))}
          <Input
            value={facilityFilter}
            onChange={(e) => setFacilityFilter(e.target.value)}
            placeholder="Filter by facility name..."
            className="max-w-xs"
            data-testid="hold-facility-filter"
          />
        </div>
      </CardHeader>

      <CardContent>
        {loading && rows.length === 0 && (
          <div className="text-center py-12">
            <Loader2 className="h-6 w-6 animate-spin mx-auto" />
          </div>
        )}

        {!loading && rows.length === 0 && (
          <div className="text-center py-12 text-sm text-muted-foreground" data-testid="holds-empty">
            No cleanout holds match the current filter.
          </div>
        )}

        <div className="space-y-3">
          {rows.map((r) => {
            const tone = STATUS_COLORS[r.status] || 'bg-slate-100 text-slate-800 border-slate-300';
            const isResolved = ['released', 'forfeited', 'captured'].includes(r.status);
            const isActioning = actionRowId === r.invoice_id;
            return (
              <div
                key={r.invoice_id}
                className="border rounded-lg p-4 hover:bg-slate-50 transition-colors w-full overflow-hidden"
                data-testid={`hold-row-${r.invoice_id}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="font-semibold text-sm break-words" data-testid={`hold-facility-${r.invoice_id}`}>
                        🏢 {r.facility_name || '—'}
                      </span>
                      {r.unit_number && (
                        <span className="text-xs text-muted-foreground">Unit #{r.unit_number}</span>
                      )}
                      <Badge className={`${tone} text-xs`} data-testid={`hold-status-${r.invoice_id}`}>
                        {r.status?.replace('_', ' ').toUpperCase()}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground space-y-0.5">
                      <div>Winner: <span className="font-medium text-foreground">{r.buyer_email || '—'}</span></div>
                      <div>Hold: <span className="font-bold text-foreground">${Number(r.amount_cad || 0).toFixed(2)} CAD</span></div>
                      <div>Invoice: <span className="font-mono">{r.invoice_id?.slice(0, 12)}…</span></div>
                      {r.clearance_requested_at && (
                        <div>Buyer marked cleared: {new Date(r.clearance_requested_at).toLocaleString()}</div>
                      )}
                    </div>
                  </div>
                </div>

                {!isResolved && (
                  <div className="mt-3 pt-3 border-t border-slate-200 space-y-2">
                    <Input
                      value={forfeitReason[r.invoice_id] || ''}
                      onChange={(e) => setForfeitReason({ ...forfeitReason, [r.invoice_id]: e.target.value })}
                      placeholder="Reason for forfeit (≥ 10 chars, required if forfeiting)…"
                      data-testid={`hold-forfeit-reason-${r.invoice_id}`}
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => handleApprove(r.invoice_id)}
                        disabled={isActioning}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        size="sm"
                        data-testid={`approve-cleanout-btn-${r.invoice_id}`}
                      >
                        {isActioning ? <Loader2 className="h-4 w-4 animate-spin" /> : '✅ Approve Cleanout'}
                      </Button>
                      <Button
                        onClick={() => handleForfeit(r.invoice_id)}
                        disabled={isActioning || (forfeitReason[r.invoice_id] || '').trim().length < 10}
                        variant="destructive"
                        size="sm"
                        data-testid={`forfeit-deposit-btn-${r.invoice_id}`}
                      >
                        {isActioning ? <Loader2 className="h-4 w-4 animate-spin" /> : '❌ Forfeit Deposit'}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
