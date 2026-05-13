/**
 * iter211 — Admin "Manual Settle" subscription modal.
 *
 * Used by PartnerManager, VehicleAdminManager > DealerSubscriptions, and the
 * Storage admin views. One reusable component to avoid drift.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from './ui/select';
import { Loader2, Banknote } from 'lucide-react';
import API_BASE from '../config';

const API = API_BASE;

const PAYMENT_METHODS = [
  { value: 'e_transfer', label_en: 'Interac e-Transfer', label_fr: 'Virement Interac' },
  { value: 'cheque',     label_en: 'Cheque',             label_fr: 'Chèque' },
  { value: 'wire',       label_en: 'Wire transfer',      label_fr: 'Virement bancaire' },
  { value: 'cash',       label_en: 'Cash',               label_fr: 'Espèces' },
];

const _todayPlus365 = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
};

const ManualSettleSubscriptionModal = ({
  open, onOpenChange,
  targetUserId, targetUserEmail,
  accountKind,        // "vehicle_dealer" | "partner" | "storage_facility"
  defaultAmount = 100,
  onSettled,
}) => {
  const [method, setMethod] = useState('e_transfer');
  const [reference, setReference] = useState('');
  const [amount, setAmount] = useState(defaultAmount);
  const [activeUntil, setActiveUntil] = useState(_todayPlus365());
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!reference.trim()) {
      toast.error('Reference # is required');
      return;
    }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/admin/manual-settle/subscription`, {
        target_user_id: targetUserId,
        account_kind: accountKind,
        payment_method: method,
        reference_number: reference.trim(),
        amount_cad: Number(amount) || 0,
        active_until: new Date(activeUntil).toISOString(),
        notes,
      });
      toast.success(`Subscription activated for ${targetUserEmail}. Receipt emailed.`);
      onSettled?.(r.data);
      onOpenChange(false);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to settle subscription';
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="manual-settle-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Banknote className="w-5 h-5 text-emerald-600" />
            Manual Subscription Settle
          </DialogTitle>
          <DialogDescription>
            Activate annual subscription for <strong>{targetUserEmail}</strong> via off-Stripe payment. Any open Stripe draft invoices for this subscription will be voided automatically.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label className="text-xs">Payment method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger data-testid="manual-settle-method"><SelectValue /></SelectTrigger>
              <SelectContent>
                {PAYMENT_METHODS.map(pm => (
                  <SelectItem key={pm.value} value={pm.value}>{pm.label_en}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Transaction reference #</Label>
            <Input
              value={reference}
              onChange={e => setReference(e.target.value)}
              placeholder="e-Transfer ref, cheque #, wire confirmation…"
              data-testid="manual-settle-ref"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-xs">Amount (CAD)</Label>
              <Input
                type="number"
                step="0.01"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                data-testid="manual-settle-amount"
              />
            </div>
            <div>
              <Label className="text-xs">Active until</Label>
              <Input
                type="date"
                value={activeUntil}
                onChange={e => setActiveUntil(e.target.value)}
                data-testid="manual-settle-active-until"
              />
            </div>
          </div>
          <div>
            <Label className="text-xs">Notes (optional)</Label>
            <Input
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Anything you want recorded in the ledger"
              data-testid="manual-settle-notes"
            />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
          <Button size="sm" onClick={submit} disabled={saving} data-testid="manual-settle-submit" className="bg-emerald-600 hover:bg-emerald-700 text-white">
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Banknote className="w-4 h-4 mr-2" />}
            Activate subscription
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ManualSettleSubscriptionModal;
export { ManualSettleSubscriptionModal };
