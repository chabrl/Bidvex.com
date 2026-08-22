/**
 * iter500 — Accept Below Reserve
 *
 * Renders a button on ended lots where status === 'reserve_not_met'
 * and the saved winning bid has a payment method on file. Confirms via
 * modal then hits POST /api/auctions/{id}/accept-below-reserve which
 * re-uses the existing bypass_reserve settlement path.
 *
 * Used from both the Seller Dashboard (ended listings view) and the
 * Admin Manage-All-Auctions panel.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from './ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { AlertTriangle, Loader2, CheckCircle } from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';
import API_BASE from '../config';

const API = API_BASE;

/**
 * Props
 *   auctionId : string
 *   lotNumber : number|null    // pass null/undefined for top-level auctions
 *   token     : string          // auth bearer
 *   onSuccess : function        // parent refresh callback
 *   variant   : 'seller' | 'admin'
 *   surface   : optional string used only for data-testid uniqueness
 */
const AcceptBelowReserveButton = ({
  auctionId,
  lotNumber = null,
  token,
  onSuccess,
  variant = 'seller',
  surface = 'seller-dashboard',
}) => {
  const [eligibility, setEligibility] = useState(null);
  const [loadingEligibility, setLoadingEligibility] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!auctionId || !token) {
        setLoadingEligibility(false);
        return;
      }
      try {
        const params = new URLSearchParams();
        if (lotNumber !== null && lotNumber !== undefined) {
          params.set('lot_number', String(lotNumber));
        }
        const url = `${API}/auctions/${auctionId}/reserve-not-met-eligibility${
          params.toString() ? `?${params.toString()}` : ''
        }`;
        const res = await axios.get(url, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (alive) setEligibility(res.data);
      } catch (_) {
        if (alive) setEligibility({ eligible: false, reason: 'fetch_failed' });
      } finally {
        if (alive) setLoadingEligibility(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [auctionId, lotNumber, token]);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      const body = {};
      if (lotNumber !== null && lotNumber !== undefined) {
        body.lot_number = lotNumber;
      }
      const res = await axios.post(
        `${API}/auctions/${auctionId}/accept-below-reserve`,
        body,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(
        variant === 'admin'
          ? 'Below-reserve sale accepted. Buyer will be charged.'
          : 'Sale accepted. The buyer will be charged and emailed.',
      );
      setConfirmOpen(false);
      setEligibility((prev) =>
        prev ? { ...prev, eligible: false, reason: 'accepted' } : prev,
      );
      if (onSuccess) onSuccess(res.data);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.message || error?.message || 'Failed to accept below reserve';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingEligibility) return null;
  if (!eligibility || !eligibility.eligible) return null;

  const currency = eligibility.currency || 'CAD';
  const hammerLabel = formatCurrency(eligibility.hammer_price || 0, currency);
  const lotLabel = eligibility.lot_number ? `Lot #${eligibility.lot_number}` : 'Auction';
  const buyer = eligibility.buyer_name || 'Winning bidder';
  const testidSuffix = lotNumber != null ? `${auctionId}-lot${lotNumber}` : auctionId;

  return (
    <>
      <Button
        size="sm"
        onClick={() => setConfirmOpen(true)}
        data-testid={`accept-below-reserve-btn-${surface}-${testidSuffix}`}
        className={
          variant === 'admin'
            ? 'w-full lg:w-auto bg-emerald-600 hover:bg-emerald-700 text-white border-0'
            : 'w-full lg:w-auto bg-emerald-600 hover:bg-emerald-700 text-white border-0'
        }
      >
        <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
        Accept Below Reserve — {hammerLabel}
      </Button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent data-testid={`accept-below-reserve-dialog-${testidSuffix}`}>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Accept sale below reserve?
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-3 gap-2 rounded-md border bg-slate-50 dark:bg-slate-900 p-3">
                  <div className="col-span-1 text-slate-500">Lot</div>
                  <div
                    className="col-span-2 font-medium"
                    data-testid="abr-dialog-lot"
                  >
                    {lotLabel}
                  </div>
                  <div className="col-span-1 text-slate-500">Item</div>
                  <div
                    className="col-span-2 font-medium truncate"
                    data-testid="abr-dialog-item"
                  >
                    {eligibility.item_name || '—'}
                  </div>
                  <div className="col-span-1 text-slate-500">Hammer</div>
                  <div
                    className="col-span-2 font-semibold text-emerald-700"
                    data-testid="abr-dialog-hammer"
                  >
                    {hammerLabel}
                  </div>
                  <div className="col-span-1 text-slate-500">Buyer</div>
                  <div
                    className="col-span-2 font-medium"
                    data-testid="abr-dialog-buyer"
                  >
                    {buyer}
                  </div>
                </div>
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    <div>
                      This will immediately charge the buyer&rsquo;s saved
                      card for the hammer price above and finalise the
                      settlement. The buyer and seller will receive their
                      standard settlement emails.
                    </div>
                  </div>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={submitting}
              data-testid={`abr-dialog-cancel-${testidSuffix}`}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={submitting}
              onClick={(e) => {
                e.preventDefault();
                handleConfirm();
              }}
              data-testid={`abr-dialog-confirm-${testidSuffix}`}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing…
                </>
              ) : (
                <>Charge Buyer &amp; Accept</>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default AcceptBelowReserveButton;
