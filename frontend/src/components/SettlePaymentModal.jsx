/**
 * SettlePaymentModal — iter302 Directive 2.
 *
 * Buyer-facing "Settle Payment" flow from My Purchases. Pulls the
 * itemized invoice + saved-card context from
 * GET /api/settlement/settle-context/{listingId} (winner-gated), then
 * charges the saved card off-session via POST /api/settlement/settle.
 * On success, the 8-character pickup code is shown prominently.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { CreditCard, Loader2, CheckCircle2, ShieldCheck, KeyRound } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from './ui/dialog';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency } from '../utils/currencyFormatter';
import API_BASE from '../config';

const SettlePaymentModal = ({ listingId, open, onOpenChange, onPaid }) => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const fr = (i18n.language || 'en').startsWith('fr');
  const [ctx, setCtx] = useState(null);
  const [loading, setLoading] = useState(false);
  const [paying, setPaying] = useState(false);
  const [result, setResult] = useState(null);

  const fetchContext = useCallback(async () => {
    if (!token || !listingId) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await axios.get(`${API_BASE}/settlement/settle-context/${listingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCtx(r.data);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : (fr ? 'Impossible de charger la facture' : 'Could not load the invoice'));
      onOpenChange(false);
    } finally {
      setLoading(false);
    }
  }, [token, listingId]);

  useEffect(() => {
    if (open && listingId) fetchContext();
    if (!open) { setCtx(null); setResult(null); }
  }, [open, listingId, fetchContext]);

  const handlePay = async () => {
    setPaying(true);
    try {
      const r = await axios.post(`${API_BASE}/settlement/settle/${listingId}`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setResult(r.data);
      toast.success(fr ? 'Paiement réglé avec succès !' : 'Payment settled successfully!');
      if (onPaid) onPaid();
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' && d) ? (fr ? d.message_fr : d.message_en) : d;
      toast.error(msg || (fr ? 'Le paiement a échoué. Veuillez réessayer.' : 'Payment failed. Please retry.'));
    } finally {
      setPaying(false);
    }
  };

  const pickupCode = result?.pickup_code || (ctx?.already_paid ? ctx.pickup_code : null);
  const showSuccess = !!result?.success || !!ctx?.already_paid;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="settle-payment-modal">
        <DialogHeader>
          <DialogTitle>
            {showSuccess
              ? (fr ? 'Paiement confirmé' : 'Payment Confirmed')
              : (fr ? 'Régler le paiement' : 'Settle Payment')}
          </DialogTitle>
          {!showSuccess && ctx?.title && (
            <DialogDescription className="truncate">{ctx.title}</DialogDescription>
          )}
        </DialogHeader>

        {loading && (
          <div className="py-8 flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            {fr ? 'Chargement…' : 'Loading…'}
          </div>
        )}

        {!loading && showSuccess && (
          <div className="space-y-4 py-2" data-testid="settle-success-view">
            <div className="flex flex-col items-center gap-2 text-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-500" />
              <p className="text-sm text-muted-foreground">
                {fr
                  ? 'Votre paiement a été encaissé. Présentez ce code lors de la collecte de votre article.'
                  : 'Your payment was collected. Present this code when picking up your item.'}
              </p>
            </div>
            {pickupCode && (
              <div className="p-4 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border-2 border-indigo-200 text-center">
                <p className="text-xs uppercase font-semibold text-indigo-700 dark:text-indigo-300 flex items-center justify-center gap-1.5 mb-1">
                  <KeyRound className="h-3.5 w-3.5" />
                  {fr ? 'Code de collecte' : 'Pickup Code'}
                </p>
                <p className="text-3xl font-mono font-bold tracking-[0.3em] text-indigo-800 dark:text-indigo-200" data-testid="settle-pickup-code">
                  {pickupCode}
                </p>
              </div>
            )}
            <Button className="w-full" onClick={() => onOpenChange(false)} data-testid="settle-close-btn">
              {fr ? 'Fermer' : 'Close'}
            </Button>
          </div>
        )}

        {!loading && !showSuccess && ctx && (
          <div className="space-y-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Prix d\u2019adjudication' : 'Hammer price'}</span>
                <span>{formatCurrency(ctx.hammer_price)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Frais de plateforme (2,5 %)' : 'Platform fee (2.5%)'}</span>
                <span>{formatCurrency(ctx.platform_fee)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Taxes' : 'Taxes'}</span>
                <span>{formatCurrency(ctx.taxes)}</span>
              </div>
              <Separator />
              <div className="flex justify-between font-bold text-base">
                <span>{fr ? 'Total à payer' : 'Total due'}</span>
                <span data-testid="settle-total">{formatCurrency(ctx.total_due)} CAD</span>
              </div>
              <p className="text-xs text-muted-foreground flex items-start gap-1.5 pt-1" data-testid="settle-escrow-note">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0 mt-0.5" />
                {fr
                  ? "Les fonds sont détenus par BidVex Inc. jusqu'à la confirmation de la collecte"
                  : 'Funds are held securely by BidVex Inc. until pickup is confirmed'}
              </p>
            </div>

            {ctx.saved_card ? (
              <div className="flex items-center gap-2 p-3 rounded-lg border bg-slate-50 dark:bg-slate-800/60 text-sm" data-testid="settle-saved-card">
                <CreditCard className="h-4 w-4 text-slate-500 flex-shrink-0" />
                <span className="font-medium capitalize">{ctx.saved_card.brand || (fr ? 'Carte' : 'Card')}</span>
                <span className="text-muted-foreground">•••• {ctx.saved_card.last4 || '????'}</span>
              </div>
            ) : (
              <div className="p-3 rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 text-sm space-y-2" data-testid="settle-no-card-warning">
                <p className="text-amber-800 dark:text-amber-300">
                  {fr
                    ? 'Aucune carte enregistrée. Ajoutez un moyen de paiement pour régler.'
                    : 'No saved card on file. Add a payment method to settle.'}
                </p>
                <Button size="sm" variant="outline" onClick={() => navigate('/settings?tab=payments')} data-testid="settle-add-card-btn">
                  {fr ? 'Ajouter une carte' : 'Add a card'}
                </Button>
              </div>
            )}

            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white border-0 font-semibold"
              onClick={handlePay}
              disabled={paying || !ctx.saved_card}
              data-testid="settle-confirm-btn"
            >
              {paying
                ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                : <CreditCard className="h-4 w-4 mr-2" />}
              {fr
                ? `Payer ${formatCurrency(ctx.total_due)} maintenant`
                : `Pay ${formatCurrency(ctx.total_due)} now`}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default SettlePaymentModal;
