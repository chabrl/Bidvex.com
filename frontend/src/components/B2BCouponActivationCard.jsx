/**
 * iter254 — B2B Partner Program Credit Activation Card
 *
 * A role-gated coupon activation card that lets professional B2B users
 * (Brokers, Vehicle Dealers, Storage Facilities, Partners) redeem a
 * `partner_launch_offer` coupon code from their dashboard/profile.
 *
 * Visibility rule: only renders when `isB2BUser(user) === true`.
 * Buyers / personal accounts never see this widget.
 *
 * On successful redemption, the user's session context picks up
 * `partner_offer_active=True` so every B2B dashboard surface across the
 * app can show a "Verified Partner Offer" badge.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Ticket, CheckCircle, Loader2, Sparkles } from 'lucide-react';
import { extractErrorMessage } from '../utils/errorHandler';

const API = API_BASE;

export const isB2BUser = (user) => {
  if (!user) return false;
  if (user.is_partner === true) return true;
  if (user.is_storage_facility === true) return true;
  const at = (user.account_type || '').toLowerCase();
  return ['partner', 'broker', 'vehicle_dealer', 'storage_facility'].includes(at);
};

const B2BCouponActivationCard = ({ className = '' }) => {
  const { user, refreshUser, token } = useAuth();
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Role-gate: hide entirely for regular buyers.
  if (!isB2BUser(user)) return null;

  const alreadyActive = !!user?.partner_offer_active;

  const handleActivate = async () => {
    const trimmed = (code || '').trim().toUpperCase();
    if (!trimmed) {
      toast.error('Please enter a coupon code');
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(
        `${API}/promotions/activate-to-account`,
        { coupon_code: trimmed },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res?.data?.activated) {
        toast.success(res.data.message_en || 'Verified Partner Offer activated!', {
          description: `Coupon ${res.data.coupon_code} now linked to your account.`,
        });
        setCode('');
        await refreshUser?.();
      } else {
        toast.error(res?.data?.message_en || 'Invalid coupon code');
      }
    } catch (e) {
      // iter409 — Trust Gate / cross-lookup 500s return
      // `{code, message_en, message_fr}` objects. Route through the
      // shared bilingual extractor so React never receives a raw object.
      toast.error(extractErrorMessage(e) || 'Could not activate coupon');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      className={`border border-amber-200 bg-gradient-to-br from-amber-50 to-white shadow-sm ${className}`}
      data-testid="b2b-coupon-activation-card"
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Ticket className="h-4 w-4 text-amber-600" />
          🎫 Activate Partner Program Credit
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        {alreadyActive ? (
          <div
            className="rounded-md border border-emerald-300 bg-emerald-50 p-3"
            data-testid="b2b-coupon-active-state"
          >
            <Badge className="bg-emerald-600 text-white border-0 mb-1.5">
              <CheckCircle className="h-3 w-3 mr-1" />
              Verified Partner Offer
            </Badge>
            <p className="text-xs font-semibold text-emerald-900">
              100% Free Listing Credit Applied
            </p>
            {user?.partner_offer_coupon_code && (
              <p className="text-[11px] text-emerald-700 mt-1">
                Coupon{' '}
                <code className="font-mono bg-white px-1 rounded">
                  {user.partner_offer_coupon_code}
                </code>{' '}
                will auto-apply on your next listing checkout.
              </p>
            )}
          </div>
        ) : (
          <>
            <p className="text-xs text-slate-600">
              Have an exclusive Partner Program coupon? Activate it here and it
              will auto-apply to every listing you create.
            </p>
            <div className="flex gap-2">
              <Input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Enter exclusive coupon code"
                className="flex-1 h-9 text-sm uppercase tracking-wide"
                disabled={submitting}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleActivate();
                }}
                data-testid="b2b-coupon-input"
              />
              <Button
                type="button"
                onClick={handleActivate}
                disabled={submitting || !code.trim()}
                className="h-9 px-4 bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0"
                data-testid="b2b-coupon-activate-btn"
              >
                {submitting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <>
                    <Sparkles className="h-3.5 w-3.5 mr-1" />
                    Activate Code
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default B2BCouponActivationCard;
