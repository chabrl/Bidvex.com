/**
 * iter404 — PlatformTermsGateContext
 * ===================================
 * When a bid / auto-bid API call returns a Trust Gate 403 with `missing`
 * containing `'terms'`, we surface the platform-wide auction Terms &
 * Conditions in an inline modal — the user never leaves the auction page.
 *
 * On accept, we POST /api/users/me/accept-platform-terms and then
 * automatically re-invoke the exact bid function the user just attempted.
 *
 * Applies uniformly to:
 *   • single-item bid          (POST /api/bids)
 *   • lot bid                  (POST /api/multi-item-listings/:id/lots/:n/bid)
 *   • vehicle bid              (POST /api/vehicle-bids)
 *   • vehicle multi-lot bid    (POST /api/vehicle-multi-lot-auctions/:e/lots/:l/bid)
 *   • storage bid + auto-bid   (POST /api/storage-auctions/:id/bid)
 *   • auto-bid setup           (POST /api/bids/auto-bid, and the multi-lot / vehicle variants)
 *
 * Public API (via `usePlatformTermsGate()`):
 *
 *   runWithTermsGate(bidFn) => Promise<bidFn result>
 *     - Executes bidFn().
 *     - If bidFn throws a 403 with detail.error === 'trust_required'
 *       AND detail.missing includes 'terms', opens the modal and awaits
 *       the user's choice.
 *     - On Accept → posts terms acceptance, refreshes the user, then
 *       re-invokes bidFn and resolves / rejects with that retry outcome.
 *     - On Cancel → rejects with an error whose `.termsGateCancelled`
 *       flag is `true`. Callers should skip their generic error toast
 *       when they see this flag (the modal was the UX; no need to also
 *       show "Trust Status incomplete" as a toast).
 *     - Any other error is rethrown untouched.
 */
import API_BASE from '../config';
import React, {
  createContext, useCallback, useContext, useRef, useState,
} from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { ShieldCheck, Loader2, ExternalLink } from 'lucide-react';
import { useAuth } from './AuthContext';

const API = API_BASE;

const PlatformTermsGateContext = createContext(null);

/**
 * Detect whether an axios error is the Trust-Gate 403 with terms missing.
 * Backend contract (services/trust_gate.py):
 *   status: 403
 *   detail: { error: "trust_required", missing: [...], ... }
 */
const isTermsMissingError = (err) => {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  if (status !== 403) return false;
  if (!detail || typeof detail !== 'object') return false;
  if (detail.error !== 'trust_required') return false;
  const missing = Array.isArray(detail.missing) ? detail.missing : [];
  return missing.includes('terms');
};

export const PlatformTermsGateProvider = ({ children }) => {
  const { t, i18n } = useTranslation();
  const { refreshUser } = useAuth();
  const isFr = String(i18n.language || '').toLowerCase().startsWith('fr');

  const [open, setOpen] = useState(false);
  const [accepting, setAccepting] = useState(false);
  // Deferred promise resolvers for the currently-open gate flow.
  const pendingRef = useRef(null);  // { bidFn, resolve, reject, originalError }

  const closeAndSettle = useCallback((mode, payload) => {
    const p = pendingRef.current;
    pendingRef.current = null;
    setOpen(false);
    setAccepting(false);
    if (!p) return;
    if (mode === 'resolve') p.resolve(payload);
    else p.reject(payload);
  }, []);

  const handleCancel = useCallback(() => {
    const p = pendingRef.current;
    if (!p) { setOpen(false); return; }
    // Bubble the original 403 back to the caller with a `termsGateCancelled`
    // flag so its catch block can short-circuit its own toast.
    const cancelErr = p.originalError || new Error('terms_gate_cancelled');
    try { cancelErr.termsGateCancelled = true; } catch (_) { /* frozen */ }
    closeAndSettle('reject', cancelErr);
  }, [closeAndSettle]);

  const handleAccept = useCallback(async () => {
    const p = pendingRef.current;
    if (!p) return;
    setAccepting(true);
    try {
      const token = typeof localStorage !== 'undefined'
        ? localStorage.getItem('token')
        : null;
      await axios.post(
        `${API}/users/me/accept-platform-terms`,
        { version: 'v1' },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      // Refresh the auth user so downstream Trust Gate checks see the new stamp.
      try { await refreshUser?.(); } catch (_) { /* non-fatal */ }
    } catch (acceptErr) {
      // If acceptance itself fails, keep the modal open and surface a
      // toast — do NOT settle the outer promise yet, the user can retry.
      setAccepting(false);
      const msg = acceptErr?.response?.data?.detail
        || (isFr ? "L'acceptation a échoué. Réessayez." : 'Acceptance failed. Please try again.');
      toast.error(typeof msg === 'string' ? msg : (isFr ? 'Erreur' : 'Error'));
      return;
    }

    // Re-invoke the exact bid the user attempted a moment ago.
    try {
      const result = await p.bidFn();
      closeAndSettle('resolve', result);
    } catch (retryErr) {
      // Retry failed (e.g., phone still unverified, bid too low, auction ended).
      // Close the modal and let the caller's normal catch handle the error.
      closeAndSettle('reject', retryErr);
    }
  }, [refreshUser, closeAndSettle, isFr]);

  const runWithTermsGate = useCallback(async (bidFn) => {
    try {
      return await bidFn();
    } catch (err) {
      if (!isTermsMissingError(err)) throw err;
      // Terms are the (or one of the) blocker(s). Open the modal and
      // return a promise that resolves/rejects when the user acts.
      return new Promise((resolve, reject) => {
        pendingRef.current = { bidFn, resolve, reject, originalError: err };
        setOpen(true);
      });
    }
  }, []);

  const ctxValue = { runWithTermsGate };

  return (
    <PlatformTermsGateContext.Provider value={ctxValue}>
      {children}
      <Dialog
        open={open}
        onOpenChange={(next) => { if (!next && !accepting) handleCancel(); }}
      >
        <DialogContent
          className="sm:max-w-lg"
          data-testid="platform-terms-gate-modal"
          onEscapeKeyDown={(e) => { if (accepting) e.preventDefault(); }}
          onInteractOutside={(e) => { if (accepting) e.preventDefault(); }}
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              {isFr
                ? "Acceptez les conditions générales pour enchérir"
                : 'Accept the auction Terms & Conditions to bid'}
            </DialogTitle>
            <DialogDescription>
              {isFr
                ? "Avant votre première enchère, nous devons enregistrer votre acceptation des conditions générales de la plateforme BidVex. Cela ne prend qu'un instant — vous reviendrez ensuite à cette enchère."
                : 'Before your first bid, we need to record your acceptance of the BidVex platform Terms & Conditions. It takes just a moment — you\'ll come right back to this auction.'}
            </DialogDescription>
          </DialogHeader>

          <div className="py-2">
            <ScrollArea className="h-56 rounded-md border p-4 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
              {isFr ? (
                <>
                  <p className="font-semibold mb-2">Conditions générales BidVex — Résumé</p>
                  <ul className="list-disc pl-5 space-y-1.5">
                    <li>
                      <strong>Contrat contraignant :</strong> chaque enchère placée est une offre ferme d&apos;achat au prix indiqué.
                    </li>
                    <li>
                      <strong>Paiement :</strong> le lot est débité automatiquement sur votre carte enregistrée dans les 24 heures suivant la victoire.
                    </li>
                    <li>
                      <strong>Politique « tel quel, où qu&apos;il soit » :</strong> les articles sont vendus dans l&apos;état où ils se trouvent; l&apos;inspection avant enchère est fortement recommandée.
                    </li>
                    <li>
                      <strong>Frais :</strong> une prime d&apos;acheteur peut s&apos;appliquer et sera affichée avant confirmation de l&apos;enchère.
                    </li>
                    <li>
                      <strong>Litiges :</strong> régis par les lois du Québec; procédure d&apos;escalade détaillée dans les conditions complètes.
                    </li>
                  </ul>
                  <p className="mt-3 text-xs text-slate-500">
                    Cette acceptation est enregistrée une seule fois pour l&apos;ensemble de vos enchères futures sur BidVex.
                  </p>
                </>
              ) : (
                <>
                  <p className="font-semibold mb-2">BidVex Auction Terms & Conditions — Summary</p>
                  <ul className="list-disc pl-5 space-y-1.5">
                    <li>
                      <strong>Binding contract:</strong> each bid you place is a firm offer to purchase at the stated amount.
                    </li>
                    <li>
                      <strong>Payment:</strong> the winning lot is auto-charged to your card on file within 24 hours of winning.
                    </li>
                    <li>
                      <strong>&quot;As-is, where-is&quot;:</strong> items are sold in their current condition; pre-bid inspection is strongly encouraged.
                    </li>
                    <li>
                      <strong>Fees:</strong> a buyer&apos;s premium may apply and will be shown before you confirm the bid.
                    </li>
                    <li>
                      <strong>Disputes:</strong> governed by the laws of Québec; full escalation process is described in the complete Terms.
                    </li>
                  </ul>
                  <p className="mt-3 text-xs text-slate-500">
                    This acceptance is recorded once and covers all future bids you place on BidVex.
                  </p>
                </>
              )}
            </ScrollArea>
            <a
              href="/legal#terms"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
              data-testid="platform-terms-gate-full-link"
            >
              {isFr ? 'Lire les conditions complètes' : 'Read the full Terms'}
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={accepting}
              data-testid="platform-terms-gate-cancel-btn"
            >
              {isFr ? 'Annuler' : 'Cancel'}
            </Button>
            <Button
              onClick={handleAccept}
              disabled={accepting}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="platform-terms-gate-accept-btn"
            >
              {accepting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {isFr ? 'Enregistrement…' : 'Saving…'}
                </>
              ) : (
                <>
                  <ShieldCheck className="h-4 w-4 mr-2" />
                  {isFr ? 'Accepter et placer mon enchère' : 'Accept & Place My Bid'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PlatformTermsGateContext.Provider>
  );
};

/**
 * usePlatformTermsGate — hook consumers call from any bid entry point.
 *
 * Usage:
 *   const { runWithTermsGate } = usePlatformTermsGate();
 *   try {
 *     await runWithTermsGate(() => axios.post(`${API}/bids`, payload));
 *   } catch (err) {
 *     if (err?.termsGateCancelled) return; // modal was dismissed; stay silent
 *     // existing error-handling code…
 *   }
 */
export const usePlatformTermsGate = () => {
  const ctx = useContext(PlatformTermsGateContext);
  if (!ctx) {
    // Safe fallback when the provider is missing (e.g. isolated stories/tests):
    // just pass the call through unchanged.
    return { runWithTermsGate: async (fn) => fn() };
  }
  return ctx;
};

export default PlatformTermsGateContext;
