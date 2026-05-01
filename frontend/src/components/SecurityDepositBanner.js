import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import API_BASE from '../config';
import { Alert, AlertDescription } from './ui/alert';
import { Button } from './ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from './ui/dialog';
import { Shield, Lock, CheckCircle2, Loader2, CreditCard } from 'lucide-react';
import { depositHoldCopy, DEPOSIT_HOLD_AMOUNT } from '../constants/depositHoldCopy';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { toast } from 'sonner';

const API = API_BASE;
const DEPOSIT_THRESHOLD = 10000;
const DEPOSIT_AMOUNT = DEPOSIT_HOLD_AMOUNT; // $500 — matches backend default
const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

/**
 * SecurityDepositBanner — Shown on listing detail pages for high-value auctions (>$10k).
 * Prompts the buyer to authorize a refundable $500 pre-auth hold via Stripe Elements
 * before bidding (OPC compliance: capture_method=manual → hold only, no charge).
 */
const SecurityDepositBanner = ({ listingId, startingPrice, currency = 'CAD', onDepositStatusChange }) => {
  const { i18n } = useTranslation();
  const { user, token } = useAuth();
  const [depositStatus, setDepositStatus] = useState(null);
  const [creating, setCreating] = useState(false);
  const [modalState, setModalState] = useState(null); // { client_secret, deposit_id, payment_intent_id }

  const requiresDeposit = startingPrice >= DEPOSIT_THRESHOLD;
  const isFr = i18n.language === 'fr';

  const checkDeposit = useCallback(async () => {
    if (!token || !listingId || !requiresDeposit) return;
    try {
      const res = await axios.get(`${API}/deposits/status/${listingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDepositStatus(res.data);
      onDepositStatusChange?.(res.data.has_deposit && ['requires_capture', 'succeeded'].includes(res.data.status));
    } catch {
      setDepositStatus({ has_deposit: false, requires_deposit: true });
      onDepositStatusChange?.(false);
    }
  }, [token, listingId, requiresDeposit, onDepositStatusChange]);

  useEffect(() => { checkDeposit(); }, [checkDeposit]);

  if (!requiresDeposit || !user) return null;

  const hasActiveDeposit = depositStatus?.has_deposit &&
    ['requires_capture', 'succeeded'].includes(depositStatus?.status);

  const handleStart = async () => {
    setCreating(true);
    try {
      const res = await axios.post(
        `${API}/deposits/create`,
        { listing_id: listingId },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res.data?.client_secret) {
        setModalState({
          client_secret: res.data.client_secret,
          deposit_id: res.data.deposit_id,
          payment_intent_id: res.data.payment_intent_id,
        });
      } else {
        // Already held/succeeded
        await checkDeposit();
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : (isFr ? 'Échec de la création du dépôt' : 'Failed to create deposit'));
    } finally {
      setCreating(false);
    }
  };

  const formattedDeposit = new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', {
    style: 'currency',
    currency: currency || 'CAD',
  }).format(DEPOSIT_AMOUNT);

  if (hasActiveDeposit) {
    return (
      <Alert className="border-emerald-300 bg-emerald-50" data-testid="deposit-active-banner">
        <AlertDescription className="text-emerald-800 text-sm">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            <div className="space-y-1" data-testid="deposit-status-authorized">
              <p className="font-semibold leading-snug">{depositHoldCopy.authorized.en}</p>
              <p className="font-medium leading-snug text-emerald-900/80">{depositHoldCopy.authorized.fr}</p>
            </div>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <>
      <Alert className="border-amber-300 bg-amber-50" data-testid="deposit-required-banner">
        <AlertDescription className="space-y-3">
          <div className="flex items-start gap-2">
            <Shield className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm text-amber-900 space-y-1" data-testid="deposit-status-required">
              <p className="font-semibold leading-snug">{depositHoldCopy.required.en}</p>
              <p className="font-medium leading-snug text-amber-900/80">{depositHoldCopy.required.fr}</p>
              <p className="mt-2 text-amber-900/80">
                {isFr
                  ? "Cette somme est temporairement réservée sur votre carte (pré-autorisation — aucun débit). Elle est libérée automatiquement à la fin de l'enchère."
                  : "This amount is temporarily reserved on your card (pre-authorization — no charge). It is released automatically when the auction ends."}
              </p>
            </div>
          </div>
          <Button
            onClick={handleStart}
            disabled={creating}
            className="w-full bg-amber-600 hover:bg-amber-700 text-white"
            data-testid="authorize-deposit-btn"
          >
            {creating ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{isFr ? 'Traitement...' : 'Processing...'}</>
            ) : (
              <><Lock className="h-4 w-4 mr-2" />{isFr ? `Autoriser la retenue de ${formattedDeposit}` : `Authorize ${formattedDeposit} Hold`}</>
            )}
          </Button>
          <p className="text-xs text-amber-700 text-center">
            {isFr
              ? 'Votre carte sera pré-autorisée, pas débitée. Entièrement remboursable.'
              : 'Your card will be pre-authorized, not charged. Fully refundable.'}
          </p>
        </AlertDescription>
      </Alert>

      {modalState && (
        <Elements stripe={stripePromise}>
          <AuthorizeHoldDialog
            open={!!modalState}
            onClose={() => setModalState(null)}
            state={modalState}
            amount={DEPOSIT_AMOUNT}
            currency={currency}
            onSuccess={async () => {
              setModalState(null);
              await checkDeposit();
            }}
          />
        </Elements>
      )}
    </>
  );
};

// ───────────────────────────────────────
// Modal with Stripe CardElement (manual-capture confirmation)
// ───────────────────────────────────────
const AuthorizeHoldDialog = ({ open, onClose, state, amount, currency, onSuccess }) => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const isFr = i18n.language === 'fr';

  const formatted = new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', {
    style: 'currency',
    currency: currency || 'CAD',
  }).format(amount);

  const handleAuthorize = async () => {
    if (!stripe || !elements) return;
    setProcessing(true);
    try {
      const card = elements.getElement(CardElement);
      const result = await stripe.confirmCardPayment(state.client_secret, {
        payment_method: { card },
      });

      if (result.error) {
        toast.error(
          isFr
            ? `Échec : ${result.error.message}`
            : `Failed: ${result.error.message}`
        );
        setProcessing(false);
        return;
      }

      const pi = result.paymentIntent;
      // With capture_method=manual, successful auth lands in 'requires_capture'
      if (!['requires_capture', 'succeeded', 'processing'].includes(pi?.status)) {
        toast.error(isFr ? `Statut Stripe inattendu : ${pi?.status}` : `Unexpected Stripe status: ${pi?.status}`);
        setProcessing(false);
        return;
      }

      // Sync backend
      await axios.post(
        `${API}/deposits/confirm`,
        { deposit_id: state.deposit_id, payment_intent_id: state.payment_intent_id },
        { headers: { Authorization: `Bearer ${token}` } },
      );

      toast.success(
        isFr
          ? `Retenue de ${formatted} autorisée — aucun débit effectué`
          : `${formatted} hold authorized — no charge made`
      );
      onSuccess?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object' ? (isFr ? detail.message_fr : detail.message_en) : (detail || (isFr ? 'Échec' : 'Failed'));
      toast.error(msg);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md" data-testid="authorize-hold-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-amber-600" />
            {isFr
              ? `Autoriser ${formatted} · Authorize ${formatted}`
              : `Authorize ${formatted} · Autoriser ${formatted}`}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-semibold mb-1">
              {isFr
                ? 'Pré-autorisation, pas un débit · Pre-authorization, not a charge'
                : 'Pre-authorization, not a charge · Pré-autorisation, pas un débit'}
            </p>
            <p className="text-xs">
              {isFr
                ? "Votre carte sera retenue pour un montant de " + formatted + ". Aucun débit jusqu'à la fin de l'enchère. Libéré si vous perdez ; appliqué aux frais de plateforme si vous gagnez."
                : `Your card will be held for ${formatted}. No charge until the auction ends. Released if you lose; applied to platform fees if you win.`}
            </p>
          </div>

          <div className="rounded-md border border-slate-300 bg-white p-3">
            <label className="text-xs font-medium mb-2 block flex items-center gap-1">
              <CreditCard className="h-3 w-3" />
              {isFr ? 'Détails de la carte · Card details' : 'Card details · Détails de la carte'}
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
          <Button variant="outline" onClick={onClose} disabled={processing} data-testid="authorize-hold-cancel">
            {isFr ? 'Annuler · Cancel' : 'Cancel · Annuler'}
          </Button>
          <Button
            onClick={handleAuthorize}
            disabled={processing || !stripe}
            className="bg-amber-600 hover:bg-amber-700 text-white"
            data-testid="authorize-hold-submit"
          >
            {processing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Lock className="h-4 w-4 mr-1" />}
            {isFr ? `Autoriser ${formatted}` : `Authorize ${formatted}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SecurityDepositBanner;
