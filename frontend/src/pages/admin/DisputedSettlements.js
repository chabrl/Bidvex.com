import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import {
  AlertTriangle, ShieldCheck, RefreshCw, Loader2, Paperclip, CheckCircle2,
} from 'lucide-react';

const API = API_BASE;

const RESOLUTIONS = [
  { value: 'settle_in_favor_of_dealer', label: 'Settle in favor of dealer' },
  { value: 'settle_in_favor_of_buyer',  label: 'Settle in favor of buyer' },
  { value: 'refund_platform_fee',       label: 'Refund platform fee to buyer' },
];

const DisputedSettlements = () => {
  const { token } = useAuth();
  const [data, setData] = useState({ total: 0, disputes: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [resolveModal, setResolveModal] = useState({ open: false, dispute: null });
  const [form, setForm] = useState({ resolution: 'settle_in_favor_of_dealer', admin_notes: '' });
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true); else setRefreshing(true);
    try {
      const res = await axios.get(`${API}/admin/vehicles/disputed-settlements`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (err) {
      toast.error('Failed to load disputed settlements');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openResolve = (d) => {
    setResolveModal({ open: true, dispute: d });
    setForm({ resolution: 'settle_in_favor_of_dealer', admin_notes: '' });
  };

  const handleResolve = async () => {
    const d = resolveModal.dispute;
    if (form.admin_notes.trim().length < 10) {
      toast.error('Admin notes must be at least 10 characters');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(
        `${API}/admin/vehicles/${d.auction_id}/resolve`,
        { resolution: form.resolution, admin_notes: form.admin_notes.trim() },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Dispute resolved — audit log updated');
      setResolveModal({ open: false, dispute: null });
      setData(prev => ({ ...prev, total: prev.total - 1, disputes: prev.disputes.filter(x => x.auction_id !== d.auction_id) }));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Resolve failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6" data-testid="disputed-settlements-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-rose-600" />
            Disputed Vehicle Settlements
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            Review and resolve disputes between buyers and dealers regarding vehicle settlements.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => fetchData(true)} disabled={refreshing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Open Disputes ({data.total})</CardTitle></CardHeader>
        <CardContent>
          {data.disputes.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground" data-testid="no-disputes-empty">
              <CheckCircle2 className="h-12 w-12 mx-auto mb-3 text-emerald-500 opacity-60" />
              <p className="font-medium">All clear — no disputed settlements.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.disputes.map(d => {
                const v = d.vehicle || {};
                const b = d.buyer || {};
                const s = d.seller || {};
                return (
                  <div key={d.auction_id} className="p-4 border border-rose-200 rounded-lg bg-rose-50/40 dark:bg-rose-950/20" data-testid={`dispute-${d.auction_id}`}>
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div>
                        <h3 className="font-semibold">
                          {v.year ? `${v.year} ` : ''}{v.make || ''} {v.model || ''} {!v.make && v.title ? v.title : ''}
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">Vehicle #{d.auction_id?.slice(0, 8)}</p>
                      </div>
                      <Badge variant="destructive">Disputed</Badge>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mt-3">
                      <div className="p-2 rounded bg-card border">
                        <p className="font-semibold">🛒 Buyer</p>
                        <p>{b.name || b.company_name || '—'} &lt;{b.email || '—'}&gt;</p>
                      </div>
                      <div className="p-2 rounded bg-card border">
                        <p className="font-semibold">🏢 Dealer</p>
                        <p>{s.name || s.company_name || '—'} &lt;{s.email || '—'}&gt;</p>
                      </div>
                    </div>
                    <div className="mt-3 p-3 rounded bg-rose-100 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200 text-sm">
                      <p className="font-semibold mb-1">Buyer's dispute reason:</p>
                      <p>{d.buyer_dispute_reason}</p>
                      <p className="text-[11px] mt-1 opacity-70">Opened {d.buyer_dispute_at ? new Date(d.buyer_dispute_at).toLocaleString() : '—'}</p>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button size="sm" onClick={() => openResolve(d)} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid={`resolve-${d.auction_id}`}>
                        <ShieldCheck className="h-4 w-4 mr-1" /> Resolve dispute
                      </Button>
                      {d.dealer_proof_file_id && (
                        <Button size="sm" variant="outline" onClick={() => window.open(`${API}/vehicles/settlement/${d.auction_id}/proof`, '_blank')}>
                          <Paperclip className="h-3.5 w-3.5 mr-1" /> Dealer's proof
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={resolveModal.open} onOpenChange={(open) => !submitting && setResolveModal({ open, dispute: resolveModal.dispute })}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" /> Resolve dispute
            </DialogTitle>
            <DialogDescription>
              This resolution will be recorded in the audit log. Both parties will be notified.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs">Resolution</Label>
              <Select value={form.resolution} onValueChange={v => setForm({ ...form, resolution: v })}>
                <SelectTrigger data-testid="resolution-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {RESOLUTIONS.map(r => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Admin notes (required — min 10 chars)</Label>
              <Textarea
                rows={4}
                value={form.admin_notes}
                onChange={e => setForm({ ...form, admin_notes: e.target.value })}
                placeholder="Detail your investigation findings and reasoning…"
                data-testid="admin-notes-textarea"
              />
              <p className="text-[11px] text-muted-foreground mt-1">{form.admin_notes.length} chars</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResolveModal({ open: false, dispute: null })} disabled={submitting}>Cancel</Button>
            <Button onClick={handleResolve} disabled={submitting || form.admin_notes.trim().length < 10} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="submit-resolve-btn">
              {submitting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <ShieldCheck className="h-4 w-4 mr-1" />}
              Resolve & notify
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DisputedSettlements;
