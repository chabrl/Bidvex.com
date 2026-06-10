/**
 * components/PickupConfirmButton.js — iter297 P1
 *
 * Self-contained CTA shown on any ended-with-winner listing detail
 * page or buyer-dashboard row. Drops in with one prop —
 * `listing` (the full listing object) — and gates itself on the
 * actor's role + the 7-day window.
 *
 * UI states:
 *   • Buyer, ≤7 days post-end       → primary "Confirm Pickup" CTA
 *   • Seller, >7 days post-end      → secondary "Mark Pickup Complete" CTA
 *   • Admin                         → admin force-confirm CTA
 *   • Already confirmed             → calm success badge
 *
 * Always-rendered: the rules-link describing the 7-day grace
 * window so buyers know what to expect.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { CheckCircle2, Clock, ShieldCheck, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PICKUP_WINDOW_DAYS = 7;

const _endpointFor = (listing) => {
  const kind = (listing.kind || listing.listing_type || '').toLowerCase();
  if (kind === 'storage' || listing.facility_id) return `/storage-auctions/${listing.id}/confirm-pickup`;
  if (kind === 'vehicle' || listing.vin)         return `/vehicles/${listing.id}/confirm-pickup`;
  return `/listings/${listing.id}/confirm-pickup`;
};

const _winnerId = (l) => l.winner_user_id || l.winner_id || l.highest_bidder_id;
const _sellerId = (l) => l.seller_id || l.seller_user_id || l.facility_id;

const _endedDate = (l) => {
  const v = l.ended_at || l.closed_at || l.sold_at || l.auction_end_date;
  if (!v) return null;
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d;
};

const PickupConfirmButton = ({ listing, currentUser, onConfirmed }) => {
  const [loading, setLoading] = useState(false);

  // iter297 — compute the view inline (no useMemo) because React's
  // purity rule trips on property reads inside useMemo callbacks.
  // eslint-disable-next-line
  let view = { kind: 'hidden' };
  if (listing && currentUser) {
    if (listing.pickup_confirmed) {
      view = { kind: 'done' };
    } else if (['ended', 'sold'].includes(listing.status) && _winnerId(listing)) {
      const ended = _endedDate(listing);
      // eslint-disable-next-line
      const daysSinceEnd = ended ? (Date.now() - ended.getTime()) / 86400000 : 0;
      const buyerWindowOpen = daysSinceEnd <= PICKUP_WINDOW_DAYS;

      // eslint-disable-next-line
      const role = currentUser.role || '';
      const isAdmin  = role === 'admin' || role === 'super_admin';
      const isBuyer  = currentUser.id === _winnerId(listing);
      const isSeller = currentUser.id === _sellerId(listing);

      if (isAdmin) {
        view = { kind: 'admin' };
      } else if (isBuyer) {
        view = { kind: 'buyer', buyerWindowOpen };
      } else if (isSeller && !buyerWindowOpen) {
        view = { kind: 'seller' };
      }
    }
  }

  const confirm = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const url = view.kind === 'admin'
        ? `/admin/listings/${listing.id}/force-confirm-pickup`
        : _endpointFor(listing);
      const r = await axios.post(`${API}${url}`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success('Pickup confirmed. Deposit release in progress.');
      if (onConfirmed) onConfirmed(r.data);
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'string' ? d : d?.reason || d?.error) || 'Confirmation failed';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (view.kind === 'hidden') return null;

  if (view.kind === 'done') {
    return (
      <div
        className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800"
        data-testid="pickup-confirmed-badge"
      >
        <CheckCircle2 className="h-4 w-4" />
        <span className="text-sm font-medium">Transaction Completed</span>
      </div>
    );
  }

  const isAdmin = view.kind === 'admin';
  const buttonLabel =
    view.kind === 'buyer'  ? 'Confirm Pickup / Item Received' :
    view.kind === 'seller' ? 'Mark Pickup Complete' :
                             'Force-Confirm (Admin)';
  const variant = isAdmin ? 'destructive' : 'default';
  const testid =
    view.kind === 'buyer'  ? 'pickup-confirm-buyer-btn' :
    view.kind === 'seller' ? 'pickup-confirm-seller-btn' :
                             'pickup-confirm-admin-btn';

  return (
    <div className="space-y-2" data-testid="pickup-confirm-block">
      <Button
        onClick={confirm}
        disabled={loading}
        variant={variant}
        className="bg-emerald-600 hover:bg-emerald-700 text-white"
        data-testid={testid}
      >
        {loading
          ? <Loader2 className="h-4 w-4 animate-spin mr-1" />
          : (isAdmin ? <ShieldCheck className="h-4 w-4 mr-1" /> : <CheckCircle2 className="h-4 w-4 mr-1" />)}
        {buttonLabel}
      </Button>
      {view.kind === 'buyer' && (
        <p className="text-xs text-slate-500 flex items-center gap-1" data-testid="pickup-buyer-rules">
          <Clock className="h-3 w-3" />
          You have {PICKUP_WINDOW_DAYS} days from auction end to confirm — after that the seller can confirm on your behalf.
        </p>
      )}
      {view.kind === 'seller' && (
        <p className="text-xs text-slate-500" data-testid="pickup-seller-rules">
          7-day buyer window has passed. Confirming closes the transaction and releases the deposit.
        </p>
      )}
    </div>
  );
};

export default PickupConfirmButton;
