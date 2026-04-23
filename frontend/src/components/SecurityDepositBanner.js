import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import API_BASE from '../config';
import { Alert, AlertDescription } from './ui/alert';
import { Button } from './ui/button';
import { Shield, Lock, CheckCircle2, Loader2 } from 'lucide-react';
import { depositHoldCopy, DEPOSIT_HOLD_AMOUNT } from '../constants/depositHoldCopy';

const API = API_BASE;
const DEPOSIT_THRESHOLD = 10000;
const DEPOSIT_AMOUNT = DEPOSIT_HOLD_AMOUNT; // $500 — matches backend default

/**
 * SecurityDepositBanner — Shown on listing detail pages for high-value auctions (>$10k).
 * Prompts the buyer to authorize a refundable $1,000 pre-auth hold before bidding.
 *
 * Props:
 *  - listingId: string
 *  - startingPrice: number
 *  - currency: string (CAD/USD)
 *  - onDepositStatusChange: (hasDeposit: boolean) => void
 */
const SecurityDepositBanner = ({ listingId, startingPrice, currency = 'CAD', onDepositStatusChange }) => {
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();
  const [depositStatus, setDepositStatus] = useState(null); // null = loading
  const [creating, setCreating] = useState(false);

  const requiresDeposit = startingPrice >= DEPOSIT_THRESHOLD;

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

  useEffect(() => {
    checkDeposit();
  }, [checkDeposit]);

  if (!requiresDeposit || !user) return null;

  const hasActiveDeposit = depositStatus?.has_deposit &&
    ['requires_capture', 'succeeded'].includes(depositStatus?.status);

  const handleCreateDeposit = async () => {
    setCreating(true);
    try {
      const res = await axios.post(
        `${API}/deposits/create`,
        { listing_id: listingId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      // The response includes a client_secret for Stripe Elements confirmation
      // For now we store the deposit as created and recheck status
      if (res.data.status === 'requires_confirmation') {
        // In production this would open Stripe Elements to confirm the PaymentIntent.
        // For the MVP, the deposit is recorded server-side and the user can proceed.
        await checkDeposit();
      } else {
        await checkDeposit();
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to create deposit';
      alert(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setCreating(false);
    }
  };

  const isFr = i18n.language === 'fr';
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
          onClick={handleCreateDeposit}
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
  );
};

export default SecurityDepositBanner;
