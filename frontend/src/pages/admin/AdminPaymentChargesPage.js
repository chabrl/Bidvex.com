import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { RefreshCw, AlertCircle, CheckCircle2, Ban, RotateCcw, Clock } from 'lucide-react';
import { formatMoney } from '../../components/MoneyLabel';

const API = API_BASE;

const STATUS_BADGE = {
  pending: { className: 'bg-amber-100 text-amber-900', icon: Clock },
  succeeded: { className: 'bg-green-100 text-green-900', icon: CheckCircle2 },
  failed: { className: 'bg-rose-100 text-rose-900', icon: AlertCircle },
  refunded: { className: 'bg-blue-100 text-blue-900', icon: RotateCcw },
  rolled_back: { className: 'bg-purple-100 text-purple-900', icon: RotateCcw },
  blocked_duplicate: { className: 'bg-slate-100 text-slate-900', icon: Ban },
};

const CHARGE_TYPE_LABELS = {
  deposit: 'Deposit · Dépôt',
  buyer_commission: 'Buyer Commission',
  buyer_full_payment: 'Buyer Full Payment',
  buy_now_payment: 'Buy Now',
  seller_commission: 'Seller Commission',
  seller_payout: 'Seller Payout',
};

/**
 * Admin > Strict Payment Charges Log
 * - Table of payment_charges (filterable by status / charge_type / auction_id / user_id)
 * - Summary tile of count + amount by status
 * - Sub-tab: events stream (DUPLICATE_CHARGE_BLOCKED, ROLLBACK_REFUND, WINNER_MISMATCH_BLOCKED)
 * - Sub-tab: deposit_refund_queue stats (60s SLA observability)
 */
export default function AdminPaymentChargesPage() {
  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const [tab, setTab] = useState('charges');
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [filters, setFilters] = useState({ status: '', charge_type: '', auction_id: '', user_id: '' });
  const [events, setEvents] = useState([]);
  const [queueStats, setQueueStats] = useState({ by_status: {}, failed_jobs: [] });
  const [loading, setLoading] = useState(false);

  const loadCharges = useCallback(async () => {
    setLoading(true);
    try {
      const params = Object.entries(filters)
        .filter(([, v]) => v)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&');
      const res = await axios.get(`${API}/admin/payment-charges${params ? '?' + params : ''}`, { headers });
      setRows(res.data?.rows || []);
      setSummary(res.data?.summary || {});
    } catch (e) {
      console.error('Failed to load charges', e);
    } finally {
      setLoading(false);
    }
  }, [filters, headers]);

  const loadEvents = async () => {
    try {
      const res = await axios.get(`${API}/admin/payment-charges/events`, { headers });
      setEvents(res.data?.events || []);
    } catch (e) {
      console.error('events load failed', e);
    }
  };

  const loadQueue = async () => {
    try {
      const res = await axios.get(`${API}/admin/payment-charges/refund-queue`, { headers });
      setQueueStats(res.data || { by_status: {}, failed_jobs: [] });
    } catch (e) {
      console.error('queue load failed', e);
    }
  };

  useEffect(() => {
    if (tab === 'charges') loadCharges();
    if (tab === 'events') loadEvents();
    if (tab === 'queue') loadQueue();
  }, [tab, loadCharges]);

  return (
    <div className="space-y-6 p-4" data-testid="admin-payment-charges-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Strict Payment Charges</h1>
          <p className="text-sm text-slate-500">
            Every Stripe charge and refund flows through here — duplicate charge guard + idempotency keys + 60s deposit SLA observability.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => (tab === 'charges' ? loadCharges() : tab === 'events' ? loadEvents() : loadQueue())} data-testid="refresh-btn">
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      <div className="flex gap-2 border-b" data-testid="charges-tabs">
        {[
          ['charges', 'Charges'],
          ['events', 'Events (Block / Rollback / Mismatch)'],
          ['queue', 'Deposit Refund Queue'],
        ].map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === k ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500'}`}
            data-testid={`tab-${k}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'charges' && (
        <>
          {/* Summary tiles */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
            {Object.entries(summary).map(([status, agg]) => {
              const meta = STATUS_BADGE[status] || { className: 'bg-slate-100 text-slate-900' };
              return (
                <Card key={status} className={`p-3 ${meta.className}`} data-testid={`summary-${status}`}>
                  <p className="text-xs uppercase">{status}</p>
                  <p className="text-lg font-bold">{agg.count}</p>
                  <p className="text-xs">${(agg.amount || 0).toFixed(2)}</p>
                </Card>
              );
            })}
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-2">
            <Input placeholder="status" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })} className="w-32" data-testid="filter-status" />
            <Input placeholder="charge_type" value={filters.charge_type} onChange={e => setFilters({ ...filters, charge_type: e.target.value })} className="w-44" data-testid="filter-charge-type" />
            <Input placeholder="auction_id" value={filters.auction_id} onChange={e => setFilters({ ...filters, auction_id: e.target.value })} className="w-56" data-testid="filter-auction-id" />
            <Input placeholder="user_id" value={filters.user_id} onChange={e => setFilters({ ...filters, user_id: e.target.value })} className="w-56" data-testid="filter-user-id" />
            <Button onClick={loadCharges} data-testid="apply-filters">Apply</Button>
          </div>

          {/* Table */}
          <Card>
            <CardHeader>
              <CardTitle>Charges ({rows.length})</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="charges-table">
                <thead className="bg-slate-50 text-left text-xs uppercase">
                  <tr>
                    <th className="p-2">Created</th>
                    <th className="p-2">Charge Type</th>
                    <th className="p-2">Auction</th>
                    <th className="p-2">User</th>
                    <th className="p-2">Amount</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Idempotency Key</th>
                    <th className="p-2">Stripe Object</th>
                    <th className="p-2">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && (<tr><td colSpan={9} className="p-4 text-center text-slate-500">Loading…</td></tr>)}
                  {!loading && rows.length === 0 && (
                    <tr><td colSpan={9} className="p-4 text-center text-slate-500">No charges match these filters.</td></tr>
                  )}
                  {rows.map(r => {
                    const meta = STATUS_BADGE[r.status] || { className: 'bg-slate-100 text-slate-900' };
                    return (
                      <tr key={r.id} className="border-t hover:bg-slate-50">
                        <td className="p-2 whitespace-nowrap text-xs">{(r.created_at || '').slice(0, 19)}</td>
                        <td className="p-2 text-xs">{CHARGE_TYPE_LABELS[r.charge_type] || r.charge_type}</td>
                        <td className="p-2 text-xs font-mono">{r.auction_id?.slice(0, 8)}…</td>
                        <td className="p-2 text-xs font-mono">{r.user_id?.slice(0, 8)}…</td>
                        <td className="p-2 font-semibold">{formatMoney(r.amount, r.currency)}</td>
                        <td className="p-2"><Badge className={meta.className}>{r.status}</Badge></td>
                        <td className="p-2 text-[10px] font-mono text-slate-500">{r.idempotency_key}</td>
                        <td className="p-2 text-[10px] font-mono">{r.stripe_object_id || '—'}</td>
                        <td className="p-2 text-xs text-rose-700">{r.error || ''}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}

      {tab === 'events' && (
        <Card>
          <CardHeader>
            <CardTitle>Payment Events (newest first)</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm" data-testid="events-table">
              <thead className="bg-slate-50 text-left text-xs uppercase">
                <tr>
                  <th className="p-2">When</th>
                  <th className="p-2">Event</th>
                  <th className="p-2">Auction</th>
                  <th className="p-2">User</th>
                  <th className="p-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 && (
                  <tr><td colSpan={5} className="p-4 text-center text-slate-500">No events yet — clean ledger.</td></tr>
                )}
                {events.map(ev => (
                  <tr key={ev.id} className="border-t">
                    <td className="p-2 text-xs">{(ev.created_at || '').slice(0, 19)}</td>
                    <td className="p-2"><Badge className="bg-rose-100 text-rose-900">{ev.event}</Badge></td>
                    <td className="p-2 text-xs font-mono">{ev.auction_id || '—'}</td>
                    <td className="p-2 text-xs font-mono">{ev.user_id || ev.requested_winner || '—'}</td>
                    <td className="p-2 text-xs">{ev.error || ev.charge_type || JSON.stringify(ev).slice(0, 200)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {tab === 'queue' && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(queueStats.by_status || {}).map(([s, agg]) => (
              <Card key={s} className="p-3" data-testid={`queue-${s}`}>
                <p className="text-xs uppercase text-slate-500">{s}</p>
                <p className="text-lg font-bold">{agg.count}</p>
                <p className="text-xs">${(agg.amount || 0).toFixed(2)}</p>
              </Card>
            ))}
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Failed refund jobs (need admin attention)</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase">
                  <tr>
                    <th className="p-2">When</th>
                    <th className="p-2">Auction</th>
                    <th className="p-2">User</th>
                    <th className="p-2">Amount</th>
                    <th className="p-2">PI</th>
                    <th className="p-2">Attempts</th>
                    <th className="p-2">Last Error</th>
                  </tr>
                </thead>
                <tbody>
                  {(queueStats.failed_jobs || []).length === 0 && (
                    <tr><td colSpan={7} className="p-4 text-center text-slate-500">No permanent failures. 60s SLA holding strong.</td></tr>
                  )}
                  {(queueStats.failed_jobs || []).map(j => (
                    <tr key={j.id} className="border-t">
                      <td className="p-2 text-xs">{(j.created_at || '').slice(0, 19)}</td>
                      <td className="p-2 text-xs font-mono">{j.auction_id?.slice(0, 8)}</td>
                      <td className="p-2 text-xs font-mono">{j.user_id?.slice(0, 8)}</td>
                      <td className="p-2">{formatMoney(j.amount, j.currency)}</td>
                      <td className="p-2 text-[10px] font-mono">{j.stripe_payment_intent_id}</td>
                      <td className="p-2">{j.attempts}</td>
                      <td className="p-2 text-xs text-rose-700">{j.last_error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
