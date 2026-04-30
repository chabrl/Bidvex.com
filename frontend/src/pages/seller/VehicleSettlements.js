import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import {
  CheckCircle2, FileCheck2, Upload, Loader2, RefreshCw, Car,
  AlertTriangle, Clock, ShieldCheck, Paperclip,
} from 'lucide-react';

const API = API_BASE;

const METHOD_LABELS = {
  bank_wire: 'Bank wire',
  cheque: 'Cheque',
  cash: 'Cash',
  certified_draft: 'Certified bank draft',
  financing: 'Financing',
  other: 'Other',
};

const STATUS_META = {
  AWAITING_DEALER_CONFIRMATION: { color: 'bg-amber-50 text-amber-800 border-amber-300', label: 'Awaiting your confirmation' },
  DEALER_CONFIRMED:              { color: 'bg-blue-50 text-blue-800 border-blue-300', label: 'Confirmed — awaiting buyer' },
  FULLY_SETTLED:                 { color: 'bg-emerald-50 text-emerald-800 border-emerald-300', label: 'Fully settled' },
  DISPUTED:                      { color: 'bg-rose-50 text-rose-800 border-rose-300', label: 'Disputed' },
  ADMIN_RESOLVED:                { color: 'bg-slate-100 text-slate-700 border-slate-300', label: 'Admin resolved' },
};

const VehicleSettlements = () => {
  const { token } = useAuth();
  const [data, setData] = useState({ total: 0, settlements: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [confirmModal, setConfirmModal] = useState({ open: false, settlement: null });
  const [form, setForm] = useState({
    dealer_amount_received: '',
    dealer_settlement_method: 'bank_wire',
    dealer_notes: '',
    attestation: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [uploadingProof, setUploadingProof] = useState(false);
  const [proofFile, setProofFile] = useState(null);

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true); else setRefreshing(true);
    try {
      const res = await axios.get(`${API}/vehicles/dealer/pending-settlements`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (err) {
      toast.error('Failed to load vehicle settlements');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openConfirm = (s) => {
    setConfirmModal({ open: true, settlement: s });
    setForm({
      dealer_amount_received: String(s.hammer_price ?? ''),
      dealer_settlement_method: 'bank_wire',
      dealer_notes: '',
      attestation: false,
    });
    setProofFile(null);
  };

  const handleConfirm = async () => {
    const s = confirmModal.settlement;
    const amount = parseFloat(form.dealer_amount_received);
    if (!form.attestation) {
      toast.error('You must attest the vehicle has been paid for in full and delivered');
      return;
    }
    if (!Number.isFinite(amount) || amount < 0) {
      toast.error('Enter a valid received amount');
      return;
    }
    setSubmitting(true);
    try {
      // 1. Confirm settlement (attestation required)
      await axios.post(
        `${API}/vehicles/${s.auction_id}/dealer-confirm`,
        {
          dealer_attestation: true,
          dealer_amount_received: amount,
          dealer_settlement_method: form.dealer_settlement_method,
          dealer_notes: form.dealer_notes || null,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );

      // 2. Upload optional proof file (if selected)
      if (proofFile) {
        setUploadingProof(true);
        const fd = new FormData();
        fd.append('file', proofFile);
        await axios.post(
          `${API}/vehicles/${s.auction_id}/proof-upload`,
          fd,
          { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' } },
        );
        setUploadingProof(false);
      }

      toast.success(`Settlement confirmed — buyer has been notified.`);
      setConfirmModal({ open: false, settlement: null });
      fetchData(true);
    } catch (err) {
      const msg = err?.response?.data?.detail?.message_en
        || err?.response?.data?.detail
        || 'Confirmation failed';
      toast.error(typeof msg === 'string' ? msg : 'Confirmation failed');
    } finally {
      setSubmitting(false);
      setUploadingProof(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  const pendingCount = data.settlements.filter(s => s.settlement_status === 'AWAITING_DEALER_CONFIRMATION').length;

  return (
    <div className="space-y-6" data-testid="vehicle-settlements-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-blue-600" />
            Vehicle Settlements
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            After the buyer pays the BidVex platform fee, confirm that the vehicle has been paid for in full and delivered. This creates the OPC audit trail.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => fetchData(true)} disabled={refreshing} data-testid="refresh-settlements-btn">
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {pendingCount > 0 && (
        <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950/40 dark:border-amber-900/50">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-amber-900 dark:text-amber-200">{pendingCount} vehicle{pendingCount > 1 ? 's' : ''} awaiting your confirmation</p>
            <p className="text-sm text-amber-800 dark:text-amber-300 mt-0.5">
              Please confirm each transaction within 14 days of the buyer paying the BidVex fee.
            </p>
          </div>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Settlements ({data.total})</CardTitle>
        </CardHeader>
        <CardContent>
          {data.settlements.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground" data-testid="no-settlements-empty">
              <Car className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p className="font-medium">No vehicle settlements yet.</p>
              <p className="text-sm mt-1">Once a buyer pays the BidVex platform fee on one of your vehicle auctions, it'll appear here for confirmation.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.settlements.map(s => {
                const meta = STATUS_META[s.settlement_status] || { color: 'bg-slate-100 text-slate-700 border-slate-300', label: s.settlement_status };
                const v = s.vehicle || {};
                const b = s.buyer || {};
                const canConfirm = s.settlement_status === 'AWAITING_DEALER_CONFIRMATION' || s.settlement_status === 'DISPUTED';
                return (
                  <div key={s.id || s.auction_id} className="flex flex-col md:flex-row gap-4 p-4 border rounded-lg bg-card hover:bg-accent/30 transition-colors" data-testid={`settlement-${s.auction_id}`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1.5">
                        <Badge variant="outline" className={`${meta.color} border text-[11px]`}>
                          {meta.label}
                        </Badge>
                        {s.settlement_status === 'DISPUTED' && (
                          <Badge variant="destructive" className="text-[11px]">Dispute opened</Badge>
                        )}
                      </div>
                      <h3 className="font-semibold text-base">
                        {v.year ? `${v.year} ` : ''}{v.make || ''} {v.model || ''} {!v.make && v.title ? v.title : ''}
                      </h3>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                        <span><strong>Buyer:</strong> {b.name || b.company_name || '—'} &lt;{b.email || '—'}&gt;</span>
                        <span><strong>Buyer phone:</strong> {b.phone || '—'}</span>
                        <span><strong>Hammer:</strong> ${Number(s.hammer_price || 0).toLocaleString()} CAD</span>
                        <span><strong>BidVex fee paid:</strong> {s.fee_paid_at ? new Date(s.fee_paid_at).toLocaleString() : '—'}</span>
                        {s.dealer_confirmed_at && (
                          <span><strong>Dealer confirmed:</strong> {new Date(s.dealer_confirmed_at).toLocaleString()}</span>
                        )}
                      </div>
                      {s.buyer_dispute_reason && (
                        <div className="mt-2 text-xs p-2 rounded bg-rose-50 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-900/50">
                          <strong>Buyer's dispute:</strong> {s.buyer_dispute_reason}
                        </div>
                      )}
                    </div>
                    <div className="flex md:flex-col gap-2 md:w-52 shrink-0">
                      {canConfirm ? (
                        <Button size="sm" onClick={() => openConfirm(s)} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid={`confirm-${s.auction_id}`}>
                          <CheckCircle2 className="h-4 w-4 mr-1" />
                          {s.settlement_status === 'DISPUTED' ? 'Re-confirm' : 'Mark as settled'}
                        </Button>
                      ) : (
                        <Badge variant="outline" className="justify-center py-1.5">
                          <FileCheck2 className="h-3.5 w-3.5 mr-1" /> {meta.label}
                        </Badge>
                      )}
                      {s.dealer_proof_file_id && (
                        <Button size="sm" variant="outline" onClick={() => window.open(`${API}/vehicles/settlement/${s.auction_id}/proof`, '_blank')}>
                          <Paperclip className="h-3.5 w-3.5 mr-1" /> View proof
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

      {/* CONFIRM MODAL */}
      <Dialog open={confirmModal.open} onOpenChange={(open) => !submitting && setConfirmModal({ open, settlement: confirmModal.settlement })}>
        <DialogContent className="max-w-xl" data-testid="confirm-settlement-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
              Confirm vehicle settlement
            </DialogTitle>
            <DialogDescription>
              This confirms the vehicle has been paid for in full and delivered to the buyer. The buyer will be notified via email.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto py-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="amount-received" className="text-xs">Amount received (CAD)</Label>
                <Input
                  id="amount-received"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={form.dealer_amount_received}
                  onChange={e => setForm({ ...form, dealer_amount_received: e.target.value })}
                  data-testid="amount-received-input"
                />
              </div>
              <div>
                <Label htmlFor="settlement-method" className="text-xs">Settlement method</Label>
                <Select value={form.dealer_settlement_method} onValueChange={v => setForm({ ...form, dealer_settlement_method: v })}>
                  <SelectTrigger id="settlement-method" data-testid="settlement-method-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(METHOD_LABELS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label htmlFor="dealer-notes" className="text-xs">Notes (optional)</Label>
              <Textarea
                id="dealer-notes"
                value={form.dealer_notes}
                onChange={e => setForm({ ...form, dealer_notes: e.target.value })}
                placeholder="e.g. Wire reference #, cheque number, financing institution..."
                rows={2}
              />
            </div>
            <div>
              <Label htmlFor="proof-file" className="text-xs flex items-center gap-1.5">
                <Upload className="h-3.5 w-3.5" /> Upload proof (optional — Bill of Sale PDF, wire receipt, cheque scan)
              </Label>
              <Input
                id="proof-file"
                type="file"
                accept="application/pdf,image/png,image/jpeg,image/webp"
                onChange={e => setProofFile(e.target.files?.[0] || null)}
                data-testid="proof-file-input"
              />
              {proofFile && (
                <p className="text-xs text-muted-foreground mt-1">
                  Selected: {proofFile.name} ({Math.round(proofFile.size / 1024)} KB)
                </p>
              )}
              <p className="text-[11px] text-muted-foreground mt-1">Max 10 MB. Optional but strongly recommended for OPC audit trail.</p>
            </div>
            <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded">
              <Checkbox
                id="attestation"
                checked={form.attestation}
                onCheckedChange={v => setForm({ ...form, attestation: v === true })}
                className="mt-0.5"
                data-testid="attestation-checkbox"
              />
              <label htmlFor="attestation" className="text-xs leading-snug text-amber-900 dark:text-amber-200 cursor-pointer">
                <strong>I legally attest</strong> that this vehicle has been paid for in full and delivered to the buyer. I understand this attestation is recorded in BidVex's audit trail and may be used in OPC compliance reviews.
                <br/><span className="text-[10px]">Je atteste légalement que ce véhicule a été payé en totalité et livré à l'acheteur.</span>
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmModal({ open: false, settlement: null })} disabled={submitting}>Cancel</Button>
            <Button onClick={handleConfirm} disabled={submitting || !form.attestation} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="submit-confirmation-btn">
              {(submitting || uploadingProof) ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <ShieldCheck className="h-4 w-4 mr-1" />}
              {uploadingProof ? 'Uploading proof…' : 'Confirm & notify buyer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default VehicleSettlements;
