/**
 * iter211 Task 2 — Admin Pending Commissions queue.
 *
 * Shows every commission row that was flagged "Awaiting Manual Settlement"
 * (user opted into manual payouts). Admin can Mark-as-Paid with payment
 * method + reference; that voids any draft Stripe invoice and decrements
 * the user's outstanding balance.
 */
import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../../components/ui/dialog';
import { RefreshCw, CheckCircle2, Banknote, Loader2, AlertTriangle } from 'lucide-react';

const API = API_BASE;

const PAYMENT_METHODS = [
  { value: 'e_transfer', label: 'Interac e-Transfer' },
  { value: 'cheque',     label: 'Cheque' },
  { value: 'wire',       label: 'Wire transfer' },
  { value: 'cash',       label: 'Cash' },
];

const PendingCommissionsTab = () => {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({ count: 0, pending_count: 0, pending_total_cad: 0, threshold_cad: 500 });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [paying, setPaying] = useState(null);   // row.id while modal open
  const [payForm, setPayForm] = useState({ method: 'e_transfer', reference: '', notes: '' });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/pending-commissions?status=${statusFilter}`);
      setRows(r.data?.rows || []);
      setSummary(r.data?.summary || { count: 0, pending_count: 0, pending_total_cad: 0 });
    } catch (e) {
      toast.error('Failed to load pending commissions');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const submitPaid = async () => {
    if (!payForm.reference.trim()) {
      toast.error('Reference # is required');
      return;
    }
    try {
      await axios.post(`${API}/admin/pending-commissions/${paying}/mark-paid`, {
        payment_method: payForm.method,
        reference_number: payForm.reference.trim(),
        notes: payForm.notes,
      });
      toast.success('Commission marked paid. Receipt emailed to user.');
      setPaying(null);
      setPayForm({ method: 'e_transfer', reference: '', notes: '' });
      fetchData();
    } catch (e) {
      const msg = e.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : 'Failed to mark paid');
    }
  };

  const fmt = (cents) => `$${Number(cents || 0).toFixed(2)}`;
  const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';

  return (
    <div className="space-y-4" data-testid="pending-commissions-tab">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-slate-500">Pending Rows</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold" data-testid="pc-pending-count">{summary.pending_count || 0}</div></CardContent>
        </Card>
        <Card className="border-amber-200">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-amber-700">Pending Total</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-amber-700" data-testid="pc-pending-total">{fmt(summary.pending_total_cad)}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-slate-500">Block Threshold</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-slate-900">{fmt(summary.threshold_cad)}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-slate-500">Total Rows</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold">{summary.count || rows.length}</div></CardContent>
        </Card>
      </div>

      {/* Filter + refresh */}
      <div className="flex items-center gap-2">
        <div className="flex gap-1">
          {['pending', 'paid', 'all'].map(f => (
            <Button
              key={f}
              size="sm"
              variant={statusFilter === f ? 'default' : 'outline'}
              onClick={() => setStatusFilter(f)}
              className="capitalize"
              data-testid={`pc-filter-${f}`}
            >
              {f}
            </Button>
          ))}
        </div>
        <Button size="sm" variant="outline" onClick={fetchData} disabled={loading} data-testid="pc-refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-left">
                  <th className="px-4 py-3 font-medium text-slate-600">User</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Listing</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Amount</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Created</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Status</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">Loading…</td></tr>
                ) : rows.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500" data-testid="pc-empty">No commission rows match this filter.</td></tr>
                ) : rows.map(r => (
                  <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50/50" data-testid={`pc-row-${r.id}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{r.user_name || r.user_email || r.user_id}</div>
                      <div className="text-xs text-slate-500">{r.user_email}</div>
                      {r.user_outstanding_cad >= summary.threshold_cad && (
                        <Badge className="mt-1 bg-rose-100 text-rose-900 border border-rose-300 text-[10px]">
                          <AlertTriangle className="w-3 h-3 mr-1" />Gated · {fmt(r.user_outstanding_cad)}
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-700 text-xs">{r.listing_title || r.listing_id || '—'}</td>
                    <td className="px-4 py-3 font-mono">{fmt(r.commission_amount_cad)}</td>
                    <td className="px-4 py-3 text-slate-700 text-xs">{fmtDate(r.created_at)}</td>
                    <td className="px-4 py-3">
                      {r.status === 'paid' ? (
                        <Badge className="bg-emerald-100 text-emerald-900 border border-emerald-300">
                          <CheckCircle2 className="w-3 h-3 mr-1" />Paid · {r.payment_method}
                        </Badge>
                      ) : (
                        <Badge className="bg-amber-100 text-amber-900 border border-amber-300">
                          <Banknote className="w-3 h-3 mr-1" />Pending
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {r.status === 'pending' && (
                        <Button
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-700 text-white"
                          onClick={() => setPaying(r.id)}
                          data-testid={`pc-pay-btn-${r.id}`}
                        >
                          Mark as Paid
                        </Button>
                      )}
                      {r.status === 'paid' && (
                        <span className="text-xs text-slate-500 font-mono">{r.reference_number}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Mark-paid modal */}
      <Dialog open={!!paying} onOpenChange={(o) => { if (!o) setPaying(null); }}>
        <DialogContent className="max-w-md" data-testid="pc-mark-paid-modal">
          <DialogHeader>
            <DialogTitle>Mark Commission as Paid</DialogTitle>
            <DialogDescription>
              Record the off-Stripe payment received from the user. This will void any open Stripe draft invoice for this commission and decrement the user's outstanding balance.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Payment method</Label>
              <Select value={payForm.method} onValueChange={(v) => setPayForm({ ...payForm, method: v })}>
                <SelectTrigger data-testid="pc-method"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PAYMENT_METHODS.map(pm => (
                    <SelectItem key={pm.value} value={pm.value}>{pm.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Reference #</Label>
              <Input value={payForm.reference} onChange={e => setPayForm({ ...payForm, reference: e.target.value })} placeholder="e-Transfer ref, cheque #, wire confirmation…" data-testid="pc-ref" />
            </div>
            <div>
              <Label className="text-xs">Notes (optional)</Label>
              <Input value={payForm.notes} onChange={e => setPayForm({ ...payForm, notes: e.target.value })} data-testid="pc-notes" />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setPaying(null)}>Cancel</Button>
            <Button size="sm" onClick={submitPaid} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="pc-submit-paid">
              Confirm receipt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PendingCommissionsTab;
export { PendingCommissionsTab };
