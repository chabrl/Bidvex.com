/**
 * iter266 Mission 1 — Admin Oversight: Affiliate Payouts tab.
 *
 * Renders 4 summary cards + a paginated table with Approve / Reject
 * actions. Reuses the canonical Card/Badge/Button shadcn primitives
 * so it matches Disputes/Compliance/Auctions visually.
 */
import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import {
  DollarSign,
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  RefreshCw,
  Loader2,
} from 'lucide-react';

const API = API_BASE;

const STATUS_BADGES = {
  pending: { label: '🟡 Pending', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  paid: { label: '🟢 Paid', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  rejected: { label: '🔴 Rejected', cls: 'bg-rose-100 text-rose-800 border-rose-300' },
};

export default function AdminAffiliatePayouts() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({
    pending_total_cad: 0,
    paid_this_month_cad: 0,
    active_affiliates: 0,
    referrals_this_month: 0,
  });
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setRefreshing(true);
      const url = `${API}/admin/affiliate-payouts${statusFilter ? `?status=${statusFilter}` : ''}`;
      const r = await axios.get(url, { headers: { Authorization: `Bearer ${token}` } });
      setItems(r.data.items || []);
      setSummary(r.data.summary || {});
    } catch (e) {
      toast.error('Failed to load affiliate payouts');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleApprove = async (payout) => {
    if (!window.confirm(`Approve & pay $${Number(payout.amount).toFixed(2)} to ${payout.affiliate_email}?`)) return;
    try {
      setSubmitting(true);
      const r = await axios.patch(
        `${API}/admin/affiliate-payouts/${payout.id}/approve`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      // iter267 Mission 1 — Handle the "affiliate has no Stripe Connect" case.
      if (r.data?.success === false && r.data?.error === 'affiliate_no_stripe_connect') {
        const sendNow = window.confirm(
          `${r.data.message_en}\n\nSend the Stripe onboarding email now?`,
        );
        if (sendNow) {
          await axios.post(
            `${API}/admin/affiliates/${r.data.affiliate_id}/send-stripe-onboarding`,
            {},
            { headers: { Authorization: `Bearer ${token}` } },
          );
          toast.success('Stripe onboarding email sent to affiliate.');
        }
        return;
      }
      toast.success(
        r.data?.stripe_transfer_id
          ? `Transfer sent — Stripe ID ${r.data.stripe_transfer_id.slice(0, 14)}…`
          : 'Payout approved — affiliate notified by email.',
      );
      fetchData();
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.error === 'stripe_transfer_failed') {
        toast.error(`Stripe transfer failed: ${detail.stripe_error || 'unknown error'}`);
      } else {
        toast.error(typeof detail === 'string' ? detail : 'Approve failed');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendOnboarding = async (payout) => {
    try {
      setSubmitting(true);
      const affiliateId = payout.user_id || payout.affiliate_id;
      await axios.post(
        `${API}/admin/affiliates/${affiliateId}/send-stripe-onboarding`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Stripe onboarding link emailed to affiliate.');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to send onboarding link');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRejectSubmit = async () => {
    if (!rejectTarget || !rejectReason.trim() || rejectReason.trim().length < 2) {
      toast.error('Please provide a rejection reason (min 2 chars).');
      return;
    }
    try {
      setSubmitting(true);
      await axios.patch(
        `${API}/admin/affiliate-payouts/${rejectTarget.id}/reject`,
        { reason: rejectReason.trim() },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Payout rejected — affiliate notified by email.');
      setRejectTarget(null);
      setRejectReason('');
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reject failed');
    } finally {
      setSubmitting(false);
    }
  };

  const formatCurrency = (n) =>
    `$${Number(n || 0).toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="affiliate-payouts-loading">
        <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admin-affiliate-payouts">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            💰 Affiliate Payouts
          </h2>
          <p className="text-sm text-slate-500">
            Review, approve, or reject affiliate payout requests.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={fetchData}
          disabled={refreshing}
          data-testid="affiliate-payouts-refresh-btn"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card data-testid="payouts-card-pending">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase text-slate-500 font-semibold">Pending Payouts</p>
                <p className="text-2xl font-bold text-amber-600">{formatCurrency(summary.pending_total_cad)}</p>
              </div>
              <Clock className="h-8 w-8 text-amber-500" />
            </div>
          </CardContent>
        </Card>
        <Card data-testid="payouts-card-paid-month">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase text-slate-500 font-semibold">Paid This Month</p>
                <p className="text-2xl font-bold text-emerald-600">{formatCurrency(summary.paid_this_month_cad)}</p>
              </div>
              <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            </div>
          </CardContent>
        </Card>
        <Card data-testid="payouts-card-affiliates">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase text-slate-500 font-semibold">Active Affiliates</p>
                <p className="text-2xl font-bold">{summary.active_affiliates || 0}</p>
              </div>
              <Users className="h-8 w-8 text-indigo-500" />
            </div>
          </CardContent>
        </Card>
        <Card data-testid="payouts-card-referrals">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase text-slate-500 font-semibold">Referrals This Month</p>
                <p className="text-2xl font-bold">{summary.referrals_this_month || 0}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-cyan-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: '', label: 'All' },
          { id: 'pending', label: '🟡 Pending' },
          { id: 'paid', label: '🟢 Paid' },
          { id: 'rejected', label: '🔴 Rejected' },
        ].map((opt) => (
          <Button
            key={opt.id || 'all'}
            size="sm"
            variant={statusFilter === opt.id ? 'default' : 'outline'}
            onClick={() => setStatusFilter(opt.id)}
            data-testid={`payouts-filter-${opt.id || 'all'}`}
          >
            {opt.label}
          </Button>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            Payout Requests ({items.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="py-16 text-center text-slate-500" data-testid="payouts-empty">
              No affiliate payout requests in this view.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800 text-left">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Affiliate</th>
                    <th className="px-4 py-2 font-semibold">Email</th>
                    <th className="px-4 py-2 font-semibold text-center">Referrals</th>
                    <th className="px-4 py-2 font-semibold text-right">Amount</th>
                    <th className="px-4 py-2 font-semibold">Requested</th>
                    <th className="px-4 py-2 font-semibold">Status</th>
                    <th className="px-4 py-2 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((p) => {
                    const status = p.status_norm || 'pending';
                    const badge = STATUS_BADGES[status] || STATUS_BADGES.pending;
                    const requestedAt = p.requested_at || p.created_at;
                    return (
                      <tr
                        key={p.id}
                        className="border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50/50 dark:hover:bg-slate-800/40"
                        data-testid={`payout-row-${p.id}`}
                      >
                        <td className="px-4 py-3 font-medium">{p.affiliate_name}</td>
                        <td className="px-4 py-3 text-slate-600">{p.affiliate_email}</td>
                        <td className="px-4 py-3 text-center">{p.referrals_count || 0}</td>
                        <td className="px-4 py-3 text-right font-mono font-semibold">
                          {formatCurrency(p.amount)}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">
                          {requestedAt ? new Date(requestedAt).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <Badge className={`border ${badge.cls}`} data-testid={`payout-status-${p.id}`}>
                            {badge.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right space-x-2">
                          {status === 'pending' && (
                            <>
                              {p.has_stripe_connect ? (
                                <Button
                                  size="sm"
                                  onClick={() => handleApprove(p)}
                                  disabled={submitting}
                                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                                  data-testid={`payout-approve-${p.id}`}
                                >
                                  <CheckCircle2 className="h-3 w-3 mr-1" />
                                  Approve & Pay
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  onClick={() => handleSendOnboarding(p)}
                                  disabled={submitting}
                                  className="bg-amber-500 hover:bg-amber-600 text-white"
                                  data-testid={`payout-onboarding-${p.id}`}
                                  title="Affiliate has no Stripe account connected"
                                >
                                  ⚠️ Send Stripe Onboarding Link
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setRejectTarget(p)}
                                disabled={submitting}
                                className="border-rose-300 text-rose-700 hover:bg-rose-50"
                                data-testid={`payout-reject-${p.id}`}
                              >
                                <XCircle className="h-3 w-3 mr-1" />
                                Reject
                              </Button>
                            </>
                          )}
                          {status !== 'pending' && (
                            <span className="text-xs text-slate-400">
                              {p.paid_at || p.rejected_at
                                ? new Date(p.paid_at || p.rejected_at).toLocaleDateString()
                                : ''}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Reject modal */}
      <Dialog open={!!rejectTarget} onOpenChange={(o) => { if (!o) { setRejectTarget(null); setRejectReason(''); } }}>
        <DialogContent data-testid="payout-reject-dialog">
          <DialogHeader>
            <DialogTitle>Reject Payout</DialogTitle>
            <DialogDescription>
              Provide a reason. The affiliate will receive an email with this explanation.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>Rejection Reason</Label>
            <Textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Pending fraud review on referral cohort, please contact support."
              rows={4}
              data-testid="payout-reject-reason-input"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setRejectTarget(null); setRejectReason(''); }}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRejectSubmit}
              disabled={submitting || rejectReason.trim().length < 2}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="payout-reject-confirm-btn"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Confirm Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
