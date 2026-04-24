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
  Lock, CheckCircle2, AlertTriangle, Search, RefreshCw, Shield, Car, DollarSign, Unlock,
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
    const [escrowRes, penaltyRes, disputeRes, depositRes] = await Promise.all([
      safeFetch(`${API}/escrow/admin/escrow/transactions`, []),
      safeFetch(`${API}/escrow/admin/escrow/penalties`, []),
      safeFetch(`${API}/escrow/admin/escrow/disputes`, []),
      safeFetch(`${API}/admin/vehicle-deposits?limit=200`, { deposits: [] }),
    ]);
    setEscrows(Array.isArray(escrowRes) ? escrowRes : []);
    setPenalties(Array.isArray(penaltyRes) ? penaltyRes : []);
    setDisputes(Array.isArray(disputeRes) ? disputeRes : []);
    setDeposits(Array.isArray(depositRes?.deposits) ? depositRes.deposits : []);
    if (errors.length) {
      toast.error(`Some admin endpoints failed to load (${errors.length}). Refresh to retry.`);
      console.warn('[AdminEscrow] fetch errors:', errors);
    }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { setPage(0); }, [tab, statusFilter, depositStatusFilter, searchQuery]);

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

  const amountDollars = (d) =>
    typeof d.amount === 'number' ? d.amount : (d.amount_cents || 0) / 100;

  return (
    <div className="space-y-6" data-testid="admin-escrow-manager">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
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
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-red-600">{disputes.length}</p><p className="text-xs text-muted-foreground">Disputes</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-purple-600">{penalties.length}</p><p className="text-xs text-muted-foreground">Penalties</p></CardContent></Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2 flex-wrap items-center">
        {[
          { key: 'deposits', label: 'Vehicle Deposits' },
          { key: 'escrows',  label: 'Escrow Transactions' },
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
            <br /><span className="text-xs">Facturer au vendeur une pénalité d'annulation de 50 $.</span>
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
