/**
 * StorageDepositBanner — iter178 (FIX 1)
 * =======================================
 * Matches the pattern of /app/frontend/src/components/SecurityDepositBanner.js
 * but for storage auctions (variable deposit_amount per auction).
 *
 * Flow: click "Pay Deposit" → open Stripe Elements modal → CardElement →
 * stripe.createPaymentMethod → POST /api/storage-auctions/{id}/deposit
 * with the PM id. Backend attaches the PM and confirms a manual-capture
 * PaymentIntent (hold, not charge).
 */
import API_BASE from '../../config';
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import {
  ShieldCheck, Lock, CreditCard, Loader2, CheckCircle2,
} from 'lucide-react';

const API = API_BASE;
const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

const StorageDepositBanner = ({ auction, onStatusChange }) => {
  const { token, user } = useAuth();
  const [status, setStatus] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  const amount = Number(auction?.deposit_amount || 0);
  const required = !!auction?.deposit_required && amount > 0;
  const auctionId = auction?.id;

  const fetchStatus = useCallback(async () => {
    if (!token || !auctionId || !required) return;
    try {
      const r = await axios.get(`${API}/storage-auctions/${auctionId}/deposit/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStatus(r.data);
      onStatusChange?.(!!r.data?.has_deposit);
    } catch {
      setStatus({ has_deposit: false });
      onStatusChange?.(false);
    }
  }, [token, auctionId, required, onStatusChange]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  if (!required || !user) return null;

  const hasDeposit = !!status?.has_deposit;

  if (hasDeposit) {
    return (
      <div
        data-testid="storage-deposit-active-banner"
        className="bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-300 rounded-lg p-3 mb-4 text-sm"
      >
        <p className="text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
          <CheckCircle2 className="h-4 w-4" />
          ✅ Deposit Authorized — ${amount.toFixed(2)} hold on your card
        </p>
        <p className="text-emerald-600 dark:text-emerald-500 text-xs italic mt-1">
          Retenue autorisée — {amount.toFixed(2)} $ réservés sur votre carte
        </p>
      </div>
    );
  }

  return (
    <>
      <div
        data-testid="storage-deposit-required-banner"
        className="bg-amber-50 dark:bg-amber-900/30 border-2 border-amber-400 rounded-xl p-4 mb-4"
      >
        <p className="font-bold text-amber-800 dark:text-amber-300 mb-1 flex items-center gap-1">
          <Lock className="h-4 w-4" />
          🔐 Security Deposit Required to Bid
        </p>
        <p className="font-bold text-amber-700 dark:text-amber-400 mb-3 text-sm italic">
          Dépôt de sécurité requis pour enchérir
        </p>
        <p className="text-sm text-amber-700 dark:text-amber-400 mb-1">
          This auction requires a refundable deposit of ${amount.toFixed(2)} to place bids. Your deposit will be automatically released if you do not win.
        </p>
        <p className="text-xs text-amber-600 dark:text-amber-500 mb-4 italic">
          Cette enchère nécessite un dépôt remboursable de {amount.toFixed(2)} $ pour enchérir. Votre dépôt sera automatiquement libéré si vous ne gagnez pas.
        </p>
        <button
          onClick={() => setModalOpen(true)}
          className="w-full bg-amber-500 hover:bg-amber-400 text-white font-bold py-3 px-6 rounded-xl transition-colors text-lg"
          data-testid="storage-deposit-pay-btn"
        >
          💳 Pay ${amount.toFixed(2)} Deposit to Unlock Bidding
          <br />
          <span className="text-sm font-normal opacity-90">
            Payer {amount.toFixed(2)} $ de dépôt pour débloquer les enchères
          </span>
        </button>
      </div>

      {modalOpen && (
        <Elements stripe={stripePromise}>
          <StorageDepositDialog
            auctionId={auctionId}
            amount={amount}
            open={modalOpen}
            onClose={() => setModalOpen(false)}
            onSuccess={async () => { setModalOpen(false); await fetchStatus(); }}
          />
        </Elements>
      )}
    </>
  );
};

const StorageDepositDialog = ({ auctionId, amount, open, onClose, onSuccess }) => {
  const stripe = useStripe();
  const elements = useElements();
  const { token } = useAuth();
  const [processing, setProcessing] = useState(false);

  const handleSubmit = async () => {
    if (!stripe || !elements) return;
    setProcessing(true);
    try {
      const card = elements.getElement(CardElement);
      const pmRes = await stripe.createPaymentMethod({ type: 'card', card });
      if (pmRes.error) {
        toast.error(pmRes.error.message);
        setProcessing(false);
        return;
      }
      await axios.post(
        `${API}/storage-auctions/${auctionId}/deposit`,
        { payment_method_id: pmRes.paymentMethod.id },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(`Deposit held · Dépôt retenu — $${amount.toFixed(2)}`);
      onSuccess?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object'
        ? (detail.message_en || JSON.stringify(detail))
        : (detail || 'Deposit authorization failed · Échec');
      toast.error(msg);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md" data-testid="storage-deposit-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-amber-600" />
            Authorize ${amount.toFixed(2)} Hold · Autoriser {amount.toFixed(2)} $
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
            <p className="font-semibold">Pre-authorization, not a charge · Pré-autorisation, pas un débit</p>
            <p className="mt-1">Your card is held for ${amount.toFixed(2)}. Released automatically if you don't win. · Votre carte est retenue pour {amount.toFixed(2)} $. Libérée automatiquement si vous ne gagnez pas.</p>
          </div>
          <div className="rounded-md border border-slate-300 bg-white p-3">
            <label className="text-xs font-medium mb-2 block flex items-center gap-1">
              <CreditCard className="h-3 w-3" />
              Card details · Détails de la carte
            </label>
            <CardElement
              options={{
                style: {
                  base: { fontSize: '15px', color: '#1e293b', '::placeholder': { color: '#94a3b8' } },
                  invalid: { color: '#dc2626' },
                },
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={processing} data-testid="storage-deposit-cancel-btn">
            Cancel · Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={processing || !stripe}
            className="bg-amber-600 hover:bg-amber-700 text-white"
            data-testid="storage-deposit-submit-btn"
          >
            {processing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Lock className="h-4 w-4 mr-1" />}
            Authorize ${amount.toFixed(2)} · Autoriser {amount.toFixed(2)} $
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default StorageDepositBanner;
