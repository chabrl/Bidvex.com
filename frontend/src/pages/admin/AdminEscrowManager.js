import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import API_BASE from '../../config';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import { AsyncButton } from '../../components/ui/async-button';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  Lock, CheckCircle2, AlertTriangle, Search, RefreshCw, Shield, Car, DollarSign, Unlock, Wallet, Download, Mail, ChevronDown, ChevronRight, History,
} from 'lucide-react';
import { depositHoldShortLabel } from '../../constants/depositHoldCopy';

const API = API_BASE;

const ESCROW_STATUS_COLORS = {
  held: 'bg-amber-100 text-amber-800',
  released: 'bg-green-100 text-green-800',
  auto_released: 'bg-blue-100 text-blue-800',
  disputed: 'bg-red-100 text-red-800',
  refunded: 'bg-slate-100 text-slate-800',
};

const DEPOSIT_STATUS_COLORS = {
  pending: 'bg-slate-100 text-slate-700',
  paid: 'bg-emerald-100 text-emerald-800',
  authorized: 'bg-emerald-100 text-emerald-800',
  released: 'bg-blue-100 text-blue-800',
  refunded: 'bg-blue-100 text-blue-800',
  captured: 'bg-rose-100 text-rose-800',
  expired: 'bg-slate-100 text-slate-500',
};

const PAGE_SIZE = 20;

function Paginator({ page, setPage, total }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between pt-3 text-sm">
      <span className="text-muted-foreground">
        Page {page + 1} of {pages} — {total} total
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page === 0}
          onClick={() => setPage(p => Math.max(0, p - 1))} data-testid="pager-prev">Prev</Button>
        <Button variant="outline" size="sm" disabled={page >= pages - 1}
          onClick={() => setPage(p => Math.min(pages - 1, p + 1))} data-testid="pager-next">Next</Button>
      </div>
    </div>
  );
}

function TableSkeleton({ rows = 5 }) {
  return (
    <div className="space-y-2" data-testid="table-skeleton">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

function EmptyState({ icon: Icon, label }) {
  return (
    <Card>
      <CardContent className="py-12 text-center">
        <Icon className="h-10 w-10 text-slate-300 mx-auto mb-3" />
        <p className="text-muted-foreground">{label}</p>
        <p className="text-xs text-muted-foreground/70">Aucun résultat trouvé</p>
      </CardContent>
    </Card>
  );
}

export default function AdminEscrowManager() {
  const { token } = useAuth();
  const [escrows, setEscrows] = useState([]);
  const [penalties, setPenalties] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [deposits, setDeposits] = useState([]);
  // iter498 — Pending seller payouts (seller_payouts rows awaiting Ops action)
  const [pendingPayouts, setPendingPayouts] = useState([]);
  // iter499 — Payout history (sent) rows + filters
  const [payoutHistory, setPayoutHistory] = useState([]);
  const [payoutStatusFilter, setPayoutStatusFilter] = useState('all'); // all | pending | requires_review | sent
  const [payoutMinAmount, setPayoutMinAmount] = useState('');
  const [payoutMaxAmount, setPayoutMaxAmount] = useState('');
  const [payoutExporting, setPayoutExporting] = useState(false);
  const [expandedPayoutId, setExpandedPayoutId] = useState(null);
  const [payoutTimeline, setPayoutTimeline] = useState(null); // { payout_id, events, loading, error }
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('deposits');
  const [statusFilter, setStatusFilter] = useState('all');
  const [depositStatusFilter, setDepositStatusFilter] = useState('authorized');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [confirm, setConfirm] = useState(null);
  const [penaltyOpen, setPenaltyOpen] = useState(false);

  const headers = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const errors = [];
    const safeFetch = async (url, fallback) => {
      try { return (await axios.get(url, { headers })).data; }
      catch (e) { errors.push(`${url}: ${e?.response?.status || e.message}`); return fallback; }
    };
    // iter499 — server-side filters on pending payouts. Compose querystring
    // so we never yank the whole collection into the browser to filter it.
    const pendingParams = new URLSearchParams({ limit: '200' });
    // For the pending queue we honor the status filter only when it is
    // ``pending`` or ``requires_review``. When the user picks ``sent`` we
    // leave the pending queue query at its default (both pending states).
    if (['pending', 'requires_review'].includes(payoutStatusFilter)) {
      pendingParams.set('status', payoutStatusFilter);
    }
    if (payoutMinAmount) pendingParams.set('min_amount', String(payoutMinAmount));
    if (payoutMaxAmount) pendingParams.set('max_amount', String(payoutMaxAmount));
    if (searchQuery)    pendingParams.set('search', searchQuery);

    const historyParams = new URLSearchParams({ limit: '200', status: 'sent' });
    if (payoutMinAmount) historyParams.set('min_amount', String(payoutMinAmount));
    if (payoutMaxAmount) historyParams.set('max_amount', String(payoutMaxAmount));
    if (searchQuery)     historyParams.set('search', searchQuery);

    const [escrowRes, penaltyRes, disputeRes, depositRes, payoutsRes, historyRes] = await Promise.all([
      safeFetch(`${API}/escrow/admin/escrow/transactions`, []),
      safeFetch(`${API}/escrow/admin/escrow/penalties`, []),
      safeFetch(`${API}/escrow/admin/escrow/disputes`, []),
      safeFetch(`${API}/admin/vehicle-deposits?limit=200`, { deposits: [] }),
      safeFetch(`${API}/admin/payouts/pending?${pendingParams.toString()}`, { rows: [] }),
      safeFetch(`${API}/admin/payouts/history?${historyParams.toString()}`, { rows: [] }),
    ]);
    setEscrows(Array.isArray(escrowRes) ? escrowRes : []);
    setPenalties(Array.isArray(penaltyRes) ? penaltyRes : []);
    setDisputes(Array.isArray(disputeRes) ? disputeRes : []);
    setDeposits(Array.isArray(depositRes?.deposits) ? depositRes.deposits : []);
    setPendingPayouts(Array.isArray(payoutsRes?.rows) ? payoutsRes.rows : []);
    setPayoutHistory(Array.isArray(historyRes?.rows) ? historyRes.rows : []);
    if (errors.length) {
      toast.error(`Some admin endpoints failed to load (${errors.length}). Refresh to retry.`);
      console.warn('[AdminEscrow] fetch errors:', errors);
    }
    setLoading(false);
  }, [headers, payoutStatusFilter, payoutMinAmount, payoutMaxAmount, searchQuery]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { setPage(0); }, [tab, statusFilter, depositStatusFilter, searchQuery,
                                     payoutStatusFilter, payoutMinAmount, payoutMaxAmount]);

  // ── Escrow-transactions filter ──
  const filteredEscrows = escrows.filter(e => {
    if (statusFilter !== 'all' && e.escrow_status !== statusFilter) return false;
    if (searchQuery && !JSON.stringify(e).toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });
  const pagedEscrows = filteredEscrows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // ── Deposits filter ──
  const filteredDeposits = deposits.filter(d => {
    if (depositStatusFilter !== 'all' && d.status !== depositStatusFilter) return false;
    if (searchQuery && !JSON.stringify(d).toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });
  const pagedDeposits = filteredDeposits.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // ── Deposit actions ──
  const releaseDeposit = async (dep) => {
    await axios.post(`${API}/admin/vehicle-deposits/${dep.id}/release`, null, {
      headers, params: { reason: 'admin_manual_release' },
    });
    await fetchAll();
  };

  const captureDeposit = async (dep) => {
    await axios.post(`${API}/admin/vehicle-deposits/${dep.id}/capture`, null, {
      headers, params: { reason: 'admin_manual_capture' },
    });
    await fetchAll();
  };

  // iter498 — Manual release for a pending seller payout row.
  // Re-runs the Stripe Connect transfer via the existing service and
  // returns a structured envelope. Any failure is surfaced through the
  // toast so ops can see the underlying reason (typically "seller has
  // not onboarded Stripe Connect yet").
  const releasePendingPayout = async (payoutId) => {
    const res = await axios.post(
      `${API}/admin/payouts/${payoutId}/release`,
      null,
      { headers },
    );
    const status = res.data?.status;
    if (status === 'sent') {
      toast.success(`Payout sent — Stripe transfer ${res.data.stripe_transfer_id}`);
    } else if (status === 'already_sent') {
      toast.info('Payout was already sent — refreshing list.');
    } else {
      toast.error(`Payout still pending: ${res.data?.error || 'unknown reason'}`);
      throw new Error(res.data?.error || 'still_pending');
    }
    await fetchAll();
  };

  // iter499 — Send Stripe Connect onboarding link to the seller for a
  // stuck payout. Reuses the same AccountLink pattern already in the
  // codebase (see routes/admin_oversight.send_stripe_onboarding_link).
  const sendConnectOnboarding = async (payoutId) => {
    try {
      const res = await axios.post(
        `${API}/admin/payouts/${payoutId}/send-connect-onboarding`,
        null,
        { headers },
      );
      const s = res.data?.status;
      if (s === 'sent') {
        toast.success(res.data?.email_dispatched
          ? 'Onboarding link emailed to the seller.'
          : 'Onboarding link generated (email dispatch failed — check logs).');
      } else if (s === 'already_connected') {
        toast.info('Seller already has an active Stripe Connect account.');
      } else {
        toast.error(`Onboarding link failed: ${res.data?.error || 'unknown reason'}`);
      }
      await fetchAll();
    } catch (e) {
      toast.error(`Onboarding request failed: ${e?.response?.data?.detail || e.message}`);
    }
  };

  // iter499 — CSV export via the streaming endpoint. We hit the
  // authenticated endpoint with axios in blob mode so the browser can
  // save the file without exposing the JWT via a naked <a> URL.
  const exportPayoutsCsv = async (scope /* 'pending' | 'history' */) => {
    setPayoutExporting(true);
    try {
      const params = new URLSearchParams({ scope, limit: '5000' });
      if (['pending', 'requires_review', 'sent'].includes(payoutStatusFilter)) {
        params.set('status', payoutStatusFilter);
      }
      if (payoutMinAmount) params.set('min_amount', String(payoutMinAmount));
      if (payoutMaxAmount) params.set('max_amount', String(payoutMaxAmount));
      if (searchQuery)     params.set('search', searchQuery);
      const res = await axios.get(
        `${API}/admin/payouts/export.csv?${params.toString()}`,
        { headers, responseType: 'blob' },
      );
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
      const cd = res.headers?.['content-disposition'] || '';
      const m = cd.match(/filename="?([^";]+)"?/i);
      const filename = m ? m[1] : `bidvex_payouts_${scope}.csv`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`Exported ${filename}`);
    } catch (e) {
      toast.error(`CSV export failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setPayoutExporting(false);
    }
  };

  // iter499 — Load the audit timeline for a payout on-demand when a
  // history row is expanded. Skipped when the same row is already open.
  const loadPayoutTimeline = async (payoutId) => {
    if (expandedPayoutId === payoutId) {
      setExpandedPayoutId(null);
      setPayoutTimeline(null);
      return;
    }
    setExpandedPayoutId(payoutId);
    setPayoutTimeline({ payout_id: payoutId, events: [], loading: true });
    try {
      const res = await axios.get(
        `${API}/admin/payouts/${payoutId}/timeline`,
        { headers },
      );
      setPayoutTimeline({
        payout_id: payoutId,
        events: Array.isArray(res.data?.events) ? res.data.events : [],
        loading: false,
      });
    } catch (e) {
      setPayoutTimeline({
        payout_id: payoutId,
        events: [],
        loading: false,
        error: e?.response?.data?.detail || e.message,
      });
    }
  };

  const amountDollars = (d) =>
    typeof d.amount === 'number' ? d.amount : (d.amount_cents || 0) / 100;

  return (
    <div className="space-y-6" data-testid="admin-escrow-manager">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <Card data-testid="stat-deposits">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-emerald-600">
              {deposits.filter(d => ['paid','authorized'].includes(d.status)).length}
            </p>
            <p className="text-xs text-muted-foreground">Active Holds</p>
          </CardContent>
        </Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold">{escrows.length}</p><p className="text-xs text-muted-foreground">Total Escrows</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-amber-600">{escrows.filter(e => e.escrow_status === 'held').length}</p><p className="text-xs text-muted-foreground">Held</p></CardContent></Card>
        <Card data-testid="stat-pending-payouts">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-indigo-600">{pendingPayouts.length}</p>
            <p className="text-xs text-muted-foreground">Pending Payouts</p>
          </CardContent>
        </Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-red-600">{disputes.length}</p><p className="text-xs text-muted-foreground">Disputes</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-purple-600">{penalties.length}</p><p className="text-xs text-muted-foreground">Penalties</p></CardContent></Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2 flex-wrap items-center">
        {[
          { key: 'deposits', label: 'Vehicle Deposits' },
          { key: 'escrows',  label: 'Escrow Transactions' },
          { key: 'payouts',  label: 'Pending Payouts' },
          { key: 'history',  label: 'Payout History' },
          { key: 'disputes', label: 'Disputes' },
          { key: 'penalties', label: 'Penalty Log' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${tab === t.key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
            data-testid={`admin-tab-${t.key}`}>
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          {tab === 'penalties' && (
            <Button variant="outline" size="sm" onClick={() => setPenaltyOpen(true)} data-testid="new-penalty-btn">
              <DollarSign className="h-4 w-4 mr-1" /> Manual Penalty
            </Button>
          )}
          <AsyncButton variant="outline" size="sm" onAction={fetchAll} data-testid="refresh-btn"
            successMessage="Refreshed" loadingText="Refreshing…">
            <RefreshCw className="h-4 w-4" />
          </AsyncButton>
        </div>
      </div>

      {/* Vehicle Deposits Tab (NEW) */}
      {tab === 'deposits' && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search by vehicle, buyer email…" className="pl-9" data-testid="deposit-search" />
            </div>
            <Select value={depositStatusFilter} onValueChange={setDepositStatusFilter}>
              <SelectTrigger className="w-48" data-testid="deposit-status-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="authorized">Authorized (Hold Active)</SelectItem>
                <SelectItem value="paid">Paid (legacy)</SelectItem>
                <SelectItem value="released">Released</SelectItem>
                <SelectItem value="captured">Captured (penalty)</SelectItem>
                <SelectItem value="refunded">Refunded</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {loading ? <TableSkeleton /> :
            filteredDeposits.length === 0 ? <EmptyState icon={Car} label="No vehicle deposits match your filters." /> : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="deposit-table">
                  <thead><tr className="border-b bg-muted/50">
                    <th className="p-3 text-left">Vehicle</th>
                    <th className="p-3 text-left">Buyer</th>
                    <th className="p-3 text-left">Amount</th>
                    <th className="p-3 text-left">Status</th>
                    <th className="p-3 text-left">PI</th>
                    <th className="p-3 text-left">Authorized</th>
                    <th className="p-3 text-left">Actions</th>
                  </tr></thead>
                  <tbody>
                    {pagedDeposits.map(d => {
                      const canAct = ['paid', 'authorized'].includes(d.status);
                      const shortLabel = depositHoldShortLabel[
                        d.status === 'paid' ? 'authorized'
                        : d.status === 'refunded' ? 'released'
                        : d.status] || null;
                      return (
                        <tr key={d.id} className="border-b hover:bg-muted/30" data-testid={`deposit-row-${d.id}`}>
                          <td className="p-3">
                            <div className="text-xs font-medium">{d.vehicle_title || '—'}</div>
                            <div className="text-[11px] text-muted-foreground font-mono">{d.vehicle_id?.slice(0, 8)}…</div>
                          </td>
                          <td className="p-3">
                            <div className="text-xs">{d.buyer_email || '—'}</div>
                            <div className="text-[11px] text-muted-foreground font-mono">{d.bidder_id?.slice(0, 8)}…</div>
                          </td>
                          <td className="p-3 font-semibold">${amountDollars(d).toFixed(2)}</td>
                          <td className="p-3">
                            <Badge className={DEPOSIT_STATUS_COLORS[d.status] || ''}>{d.status}</Badge>
                            {shortLabel && (
                              <div className="mt-1 text-[11px] leading-tight text-muted-foreground">
                                <div>{shortLabel.en}</div>
                                <div className="opacity-75">{shortLabel.fr}</div>
                              </div>
                            )}
                          </td>
                          <td className="p-3 font-mono text-[11px]">{d.stripe_payment_intent_id?.slice(0, 14) || '—'}</td>
                          <td className="p-3 text-xs">{d.authorized_at ? new Date(d.authorized_at).toLocaleDateString() : (d.paid_at ? new Date(d.paid_at).toLocaleDateString() : '—')}</td>
                          <td className="p-3">
                            <div className="flex gap-1">
                              <Button
                                variant="outline" size="sm" disabled={!canAct}
                                data-testid={`release-btn-${d.id}`}
                                onClick={() => setConfirm({
                                  title: 'Release deposit hold?',
                                  description: `Cancel the $${amountDollars(d).toFixed(2)} Stripe hold for ${d.buyer_email || 'this buyer'}.\n\nNo funds will move — the card authorization is simply voided. This is the correct action for non-winners or for winners who have paid their platform fee.`,
                                  confirmText: 'Release Hold',
                                  onConfirm: () => releaseDeposit(d),
                                  successMessage: `Hold released — $${amountDollars(d).toFixed(2)} returned to buyer's card`,
                                })}
                              >
                                <Unlock className="h-3.5 w-3.5 mr-1" /> Release
                              </Button>
                              <Button
                                variant="outline" size="sm" disabled={!canAct}
                                data-testid={`capture-btn-${d.id}`}
                                className={canAct ? 'text-rose-700 border-rose-300 hover:bg-rose-50' : ''}
                                onClick={() => setConfirm({
                                  title: 'Capture deposit as penalty?',
                                  description: `Charge $${amountDollars(d).toFixed(2)} to ${d.buyer_email || 'this buyer'} because they missed their platform-fee deadline.\n\nThis IS a charge — money will move from the buyer's card to BidVex. Only use this when the fee invoice is past due.`,
                                  variant: 'destructive',
                                  confirmText: 'Capture $' + amountDollars(d).toFixed(2),
                                  onConfirm: () => captureDeposit(d),
                                  successMessage: `Hold captured — $${amountDollars(d).toFixed(2)} charged`,
                                })}
                              >
                                <Lock className="h-3.5 w-3.5 mr-1" /> Capture
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Paginator page={page} setPage={setPage} total={filteredDeposits.length} />
            </>
          )}
        </div>
      )}

      {/* Escrow Transactions Tab */}
      {tab === 'escrows' && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search by ID, buyer, seller…" className="pl-9" data-testid="escrow-search" />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="held">Held</SelectItem>
                <SelectItem value="released">Released</SelectItem>
                <SelectItem value="auto_released">Auto-Released</SelectItem>
                <SelectItem value="disputed">Disputed</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {loading ? <TableSkeleton /> :
          filteredEscrows.length === 0 ? <EmptyState icon={Shield} label="No escrow transactions found." /> : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="escrow-table">
                  <thead><tr className="border-b bg-muted/50">
                    <th className="p-3 text-left">Auction</th>
                    <th className="p-3 text-left">Buyer</th>
                    <th className="p-3 text-left">Seller</th>
                    <th className="p-3 text-left">Amount</th>
                    <th className="p-3 text-left">Status</th>
                    <th className="p-3 text-left">Code</th>
                    <th className="p-3 text-left">Created</th>
                    <th className="p-3 text-left">Released</th>
                  </tr></thead>
                  <tbody>
                    {pagedEscrows.map(e => (
                      <tr key={e.auction_id} className="border-b hover:bg-muted/30" data-testid={`escrow-row-${e.auction_id}`}>
                        <td className="p-3 font-mono text-xs">{e.auction_id?.slice(0, 8)}…</td>
                        <td className="p-3 font-mono text-xs">{e.buyer_id?.slice(0, 8)}…</td>
                        <td className="p-3 font-mono text-xs">{e.seller_id?.slice(0, 8)}…</td>
                        <td className="p-3 font-semibold">${((e.total_charged_cents || 0) / 100).toFixed(2)}</td>
                        <td className="p-3"><Badge className={ESCROW_STATUS_COLORS[e.escrow_status] || ''}>{e.escrow_status}</Badge></td>
                        <td className="p-3 font-mono">{e.pickup_code || '—'}</td>
                        <td className="p-3 text-xs">{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                        <td className="p-3 text-xs">{e.funds_released_at ? new Date(e.funds_released_at).toLocaleDateString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Paginator page={page} setPage={setPage} total={filteredEscrows.length} />
            </>
          )}
        </div>
      )}

      {/* Pending Payouts Tab (iter498, filters+CSV+onboarding iter499) */}
      {tab === 'payouts' && (
        <div className="space-y-4">
          {/* Filters row */}
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[260px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search by auction id, seller id, title…"
                className="pl-9"
                data-testid="pending-payout-search"
              />
            </div>
            <Select value={payoutStatusFilter} onValueChange={setPayoutStatusFilter}>
              <SelectTrigger className="w-52" data-testid="payout-status-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Pending</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="requires_review">Requires Review</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="number" min="0" step="0.01"
              value={payoutMinAmount}
              onChange={e => setPayoutMinAmount(e.target.value)}
              placeholder="Min $"
              className="w-28"
              data-testid="payout-min-amount"
            />
            <Input
              type="number" min="0" step="0.01"
              value={payoutMaxAmount}
              onChange={e => setPayoutMaxAmount(e.target.value)}
              placeholder="Max $"
              className="w-28"
              data-testid="payout-max-amount"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={payoutExporting}
              onClick={() => exportPayoutsCsv('pending')}
              data-testid="payout-export-csv-btn"
            >
              <Download className="h-4 w-4 mr-1" />
              {payoutExporting ? 'Exporting…' : 'Export CSV'}
            </Button>
          </div>

          {loading ? <TableSkeleton /> :
            (pendingPayouts.length === 0
              ? <EmptyState icon={Wallet} label="No pending payouts match your filters." />
              : (() => {
                const paged = pendingPayouts.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
                return (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm" data-testid="pending-payouts-table">
                        <thead>
                          <tr className="border-b bg-muted/50">
                            <th className="p-3 text-left">Auction ID</th>
                            <th className="p-3 text-left">Seller</th>
                            <th className="p-3 text-left">Amount</th>
                            <th className="p-3 text-left">Status</th>
                            <th className="p-3 text-left">Created</th>
                            <th className="p-3 text-left">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {paged.map(p => {
                            const created = p.created_at ? new Date(p.created_at) : null;
                            const badgeClass = p.status === 'requires_review'
                              ? 'bg-rose-100 text-rose-800'
                              : 'bg-amber-100 text-amber-800';
                            return (
                              <tr
                                key={p.payout_id}
                                className="border-b hover:bg-muted/30"
                                data-testid={`pending-payout-row-${p.payout_id}`}
                              >
                                <td className="p-3">
                                  <div className="text-xs font-medium">{p.listing_title || '—'}</div>
                                  <div
                                    className="text-[11px] text-muted-foreground font-mono"
                                    data-testid={`pending-payout-auction-${p.payout_id}`}
                                  >
                                    {p.listing_id || '—'}
                                    {p.lot_number ? ` · lot ${p.lot_number}` : ''}
                                  </div>
                                </td>
                                <td className="p-3">
                                  <div
                                    className="text-xs font-medium"
                                    data-testid={`pending-payout-seller-${p.payout_id}`}
                                  >
                                    {p.seller_name || '—'}
                                  </div>
                                  <div className="text-[11px] text-muted-foreground">
                                    {p.seller_email || (p.seller_id ? `${p.seller_id.slice(0, 8)}…` : '—')}
                                  </div>
                                  {!p.seller_has_connect && (
                                    <div className="mt-1 text-[11px] text-rose-600 font-medium">
                                      No Stripe Connect
                                    </div>
                                  )}
                                </td>
                                <td
                                  className="p-3 font-semibold"
                                  data-testid={`pending-payout-amount-${p.payout_id}`}
                                >
                                  ${Number(p.amount || 0).toFixed(2)} {p.currency || 'CAD'}
                                </td>
                                <td className="p-3">
                                  <Badge className={badgeClass}>{p.status}</Badge>
                                </td>
                                <td
                                  className="p-3 text-xs"
                                  data-testid={`pending-payout-created-${p.payout_id}`}
                                >
                                  {created ? created.toLocaleString() : '—'}
                                </td>
                                <td className="p-3">
                                  <div className="flex gap-1 flex-wrap">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      disabled={!p.seller_has_connect}
                                      data-testid={`release-payout-btn-${p.payout_id}`}
                                      onClick={() => setConfirm({
                                        title: 'Release payout?',
                                        description:
                                          `Send $${Number(p.amount || 0).toFixed(2)} ${p.currency || 'CAD'} to `
                                          + `${p.seller_name || p.seller_email || 'the seller'} `
                                          + `via Stripe Connect for auction ${p.listing_id}.`,
                                        confirmText: 'Release Payout',
                                        onConfirm: () => releasePendingPayout(p.payout_id),
                                        successMessage: null,
                                      })}
                                    >
                                      <DollarSign className="h-3.5 w-3.5 mr-1" />
                                      Release Payout
                                    </Button>
                                    {!p.seller_has_connect && (
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        data-testid={`send-onboarding-btn-${p.payout_id}`}
                                        onClick={() => setConfirm({
                                          title: 'Send Stripe onboarding link?',
                                          description:
                                            `Email ${p.seller_name || p.seller_email || 'the seller'} a `
                                            + `secure Stripe Connect onboarding link so their `
                                            + `$${Number(p.amount || 0).toFixed(2)} ${p.currency || 'CAD'} `
                                            + `payout can be released once they finish setup.`,
                                          confirmText: 'Send onboarding link',
                                          onConfirm: () => sendConnectOnboarding(p.payout_id),
                                          successMessage: null,
                                        })}
                                      >
                                        <Mail className="h-3.5 w-3.5 mr-1" />
                                        Send onboarding link
                                      </Button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <Paginator page={page} setPage={setPage} total={pendingPayouts.length} />
                  </>
                );
              })()
            )
          }
        </div>
      )}

      {/* Payout History Tab (iter499) */}
      {tab === 'history' && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[260px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search by auction id, seller id, transfer id…"
                className="pl-9"
                data-testid="history-payout-search"
              />
            </div>
            <Input
              type="number" min="0" step="0.01"
              value={payoutMinAmount}
              onChange={e => setPayoutMinAmount(e.target.value)}
              placeholder="Min $"
              className="w-28"
              data-testid="history-min-amount"
            />
            <Input
              type="number" min="0" step="0.01"
              value={payoutMaxAmount}
              onChange={e => setPayoutMaxAmount(e.target.value)}
              placeholder="Max $"
              className="w-28"
              data-testid="history-max-amount"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={payoutExporting}
              onClick={() => exportPayoutsCsv('history')}
              data-testid="history-export-csv-btn"
            >
              <Download className="h-4 w-4 mr-1" />
              {payoutExporting ? 'Exporting…' : 'Export CSV'}
            </Button>
          </div>
          {loading ? <TableSkeleton /> :
            (payoutHistory.length === 0
              ? <EmptyState icon={History} label="No sent payouts match your filters." />
              : (() => {
                const paged = payoutHistory.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
                return (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm" data-testid="payout-history-table">
                        <thead>
                          <tr className="border-b bg-muted/50">
                            <th className="p-3 text-left w-8"></th>
                            <th className="p-3 text-left">Auction ID</th>
                            <th className="p-3 text-left">Seller</th>
                            <th className="p-3 text-left">Amount</th>
                            <th className="p-3 text-left">Status</th>
                            <th className="p-3 text-left">Created</th>
                            <th className="p-3 text-left">Sent At</th>
                            <th className="p-3 text-left">Released By</th>
                          </tr>
                        </thead>
                        <tbody>
                          {paged.map(p => {
                            const isOpen = expandedPayoutId === p.payout_id;
                            const created = p.created_at ? new Date(p.created_at) : null;
                            const sent = p.sent_at ? new Date(p.sent_at) : null;
                            const releasedBy = p.released_by_admin_id
                              ? {
                                  id:    p.released_by_admin_id,
                                  email: p.released_by_admin_email,
                                }
                              : null;
                            return (
                              <React.Fragment key={p.payout_id}>
                                <tr
                                  className="border-b hover:bg-muted/30 cursor-pointer"
                                  data-testid={`payout-history-row-${p.payout_id}`}
                                  onClick={() => loadPayoutTimeline(p.payout_id)}
                                >
                                  <td className="p-3">
                                    {isOpen
                                      ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                      : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                                  </td>
                                  <td className="p-3">
                                    <div className="text-xs font-medium">{p.listing_title || '—'}</div>
                                    <div className="text-[11px] text-muted-foreground font-mono">
                                      {p.listing_id || '—'}
                                      {p.lot_number ? ` · lot ${p.lot_number}` : ''}
                                    </div>
                                  </td>
                                  <td className="p-3">
                                    <div className="text-xs font-medium">{p.seller_name || '—'}</div>
                                    <div className="text-[11px] text-muted-foreground">
                                      {p.seller_email || '—'}
                                    </div>
                                  </td>
                                  <td className="p-3 font-semibold">
                                    ${Number(p.amount || 0).toFixed(2)} {p.currency || 'CAD'}
                                  </td>
                                  <td className="p-3">
                                    <Badge className="bg-emerald-100 text-emerald-800">{p.status}</Badge>
                                  </td>
                                  <td className="p-3 text-xs">{created ? created.toLocaleString() : '—'}</td>
                                  <td className="p-3 text-xs">{sent ? sent.toLocaleString() : '—'}</td>
                                  <td className="p-3 text-xs" data-testid={`released-by-${p.payout_id}`}>
                                    {releasedBy ? (
                                      <>
                                        <div className="font-medium">{releasedBy.email || '—'}</div>
                                        <div className="text-[11px] text-muted-foreground font-mono">
                                          {releasedBy.id?.slice(0, 8)}…
                                        </div>
                                      </>
                                    ) : (
                                      <span className="text-muted-foreground">System / Automatic</span>
                                    )}
                                  </td>
                                </tr>
                                {isOpen && (
                                  <tr className="bg-muted/20">
                                    <td colSpan={8} className="p-3">
                                      <div
                                        className="rounded-md border border-slate-200 bg-white p-3"
                                        data-testid={`payout-timeline-${p.payout_id}`}
                                      >
                                        <div className="text-xs font-semibold mb-2 flex items-center gap-1">
                                          <History className="h-3.5 w-3.5" />
                                          Audit timeline
                                        </div>
                                        {payoutTimeline?.loading && <div className="text-xs text-muted-foreground">Loading…</div>}
                                        {payoutTimeline?.error && <div className="text-xs text-rose-600">{payoutTimeline.error}</div>}
                                        {payoutTimeline?.events?.length === 0 && !payoutTimeline?.loading && (
                                          <div className="text-xs text-muted-foreground">No timeline entries recorded.</div>
                                        )}
                                        <ol className="space-y-2">
                                          {(payoutTimeline?.events || []).map((ev, i) => (
                                            <li key={i} className="text-xs flex gap-3 items-start">
                                              <span className="text-muted-foreground font-mono whitespace-nowrap">
                                                {new Date(ev.at).toLocaleString()}
                                              </span>
                                              <span className="font-medium text-slate-800">{ev.kind}</span>
                                              <span className="text-muted-foreground truncate">
                                                {ev.actor_email && (
                                                  <span className="mr-2">by {ev.actor_email}</span>
                                                )}
                                                {ev.detail}
                                              </span>
                                            </li>
                                          ))}
                                        </ol>
                                      </div>
                                    </td>
                                  </tr>
                                )}
                              </React.Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <Paginator page={page} setPage={setPage} total={payoutHistory.length} />
                  </>
                );
              })()
            )
          }
        </div>
      )}

      {/* Disputes Tab */}
      {tab === 'disputes' && (
        <div>
          {loading ? <TableSkeleton /> :
          disputes.length === 0 ? <EmptyState icon={AlertTriangle} label="No disputes found." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="dispute-table">
                <thead><tr className="border-b bg-muted/50">
                  <th className="p-3 text-left">Auction ID</th>
                  <th className="p-3 text-left">Initiated By</th>
                  <th className="p-3 text-left">Reason</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Created</th>
                </tr></thead>
                <tbody>
                  {disputes.map((d, i) => (
                    <tr key={i} className="border-b hover:bg-muted/30">
                      <td className="p-3 font-mono text-xs">{d.auction_id?.slice(0, 8)}…</td>
                      <td className="p-3 font-mono text-xs">{d.initiated_by?.slice(0, 8)}…</td>
                      <td className="p-3">{d.reason}</td>
                      <td className="p-3"><Badge className="bg-red-100 text-red-800">{d.status}</Badge></td>
                      <td className="p-3 text-xs">{d.created_at ? new Date(d.created_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Penalties Tab */}
      {tab === 'penalties' && (
        <div>
          {loading ? <TableSkeleton /> :
          penalties.length === 0 ? <EmptyState icon={Lock} label="No penalties issued." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="penalty-table">
                <thead><tr className="border-b bg-muted/50">
                  <th className="p-3 text-left">Seller ID</th>
                  <th className="p-3 text-left">Listing</th>
                  <th className="p-3 text-left">Amount</th>
                  <th className="p-3 text-left">Reason</th>
                  <th className="p-3 text-left">Stripe PI</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Date</th>
                </tr></thead>
                <tbody>
                  {penalties.map((p, i) => (
                    <tr key={i} className="border-b hover:bg-muted/30">
                      <td className="p-3 font-mono text-xs">{p.seller_id?.slice(0, 8)}…</td>
                      <td className="p-3 font-mono text-xs">{p.listing_id?.slice(0, 8)}…</td>
                      <td className="p-3 font-semibold text-red-600">${((p.amount_cents || 0) / 100).toFixed(2)}</td>
                      <td className="p-3">{p.reason}</td>
                      <td className="p-3 font-mono text-xs">{p.stripe_payment_intent?.slice(0, 12) || '—'}</td>
                      <td className="p-3"><Badge className={p.status === 'succeeded' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>{p.status}</Badge></td>
                      <td className="p-3 text-xs">{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Confirm modal for release/capture */}
      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />

      {/* Manual penalty modal */}
      <ManualPenaltyDialog open={penaltyOpen} onClose={() => setPenaltyOpen(false)} onDone={fetchAll} headers={headers} />
    </div>
  );
}

function ManualPenaltyDialog({ open, onClose, onDone, headers }) {
  const [sellerId, setSellerId] = useState('');
  const [listingId, setListingId] = useState('');
  const [reason, setReason] = useState('');

  const reset = () => { setSellerId(''); setListingId(''); setReason(''); };
  const submit = async () => {
    if (!sellerId || !listingId) {
      toast.error('Seller ID and Listing ID are required / Champs requis');
      throw new Error('validation');
    }
    await axios.post(`${API}/escrow/admin/charge-penalty`, {
      seller_id: sellerId, listing_id: listingId, reason: reason || 'Non-delivery after auction close',
    }, { headers });
    reset();
    await onDone();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent data-testid="manual-penalty-dialog">
        <DialogHeader>
          <DialogTitle>Create Manual Penalty</DialogTitle>
          <DialogDescription>
            Charge a seller $50 cancellation penalty via Stripe.
            <br /><span className="text-xs">Facturer au vendeur une pénalité d&apos;annulation de 50 $.</span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <Input placeholder="Seller ID" value={sellerId} onChange={e => setSellerId(e.target.value)} data-testid="penalty-seller-id" />
          <Input placeholder="Listing ID" value={listingId} onChange={e => setListingId(e.target.value)} data-testid="penalty-listing-id" />
          <Input placeholder="Reason (optional)" value={reason} onChange={e => setReason(e.target.value)} data-testid="penalty-reason" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <AsyncButton onAction={submit} successMessage="Penalty charged" data-testid="penalty-submit-btn"
            className="bg-red-600 hover:bg-red-700 text-white">
            Charge $50 Penalty
          </AsyncButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
