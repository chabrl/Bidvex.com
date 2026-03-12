import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Crown, Star, Calendar, AlertTriangle, RefreshCw, XCircle, ArrowUpCircle } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIER_CONFIG = {
  free: { label: 'Starter', icon: Star, color: 'text-slate-500', bg: 'bg-slate-100 dark:bg-slate-800' },
  premium: { label: 'Premium', icon: Crown, color: 'text-amber-500', bg: 'bg-amber-50 dark:bg-amber-900/20' },
  vip: { label: 'VIP Elite', icon: Crown, color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-900/20' },
};

const SubscriptionManagement = () => {
  const [sub, setSub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const fetchStatus = async () => {
    try {
      const token = localStorage.getItem('token');
      const { data } = await axios.get(`${API}/subscriptions/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSub(data);
    } catch {
      // User may not have a subscription
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      const token = localStorage.getItem('token');
      const { data } = await axios.post(`${API}/subscriptions/cancel`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(data.message);
      setShowConfirm(false);
      fetchStatus();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Cancellation failed');
    } finally {
      setCancelling(false);
    }
  };

  if (loading) return null;
  if (!sub || sub.tier === 'free' || !sub.stripe_subscription_id) return null;

  const tier = TIER_CONFIG[sub.tier] || TIER_CONFIG.free;
  const TierIcon = tier.icon;
  const endDate = sub.end_date ? new Date(sub.end_date).toLocaleDateString('en-CA', { year: 'numeric', month: 'long', day: 'numeric' }) : '—';
  const isCancelling = sub.cancel_at_period_end;

  return (
    <div className="mb-6 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden" data-testid="subscription-management">
      {/* Header */}
      <div className={`px-5 py-4 ${tier.bg} flex items-center justify-between`}>
        <div className="flex items-center gap-3">
          <TierIcon className={`h-5 w-5 ${tier.color}`} />
          <div>
            <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
              {tier.label} Plan
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">Yearly Subscription</p>
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
          isCancelling
            ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
            : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
        }`} data-testid="subscription-status-badge">
          {isCancelling ? 'Cancels at Period End' : 'Active'}
        </span>
      </div>

      {/* Details */}
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            {isCancelling ? 'Access until' : 'Next renewal'}
          </span>
          <span className="font-medium text-slate-900 dark:text-white" data-testid="subscription-end-date">{endDate}</span>
        </div>

        {/* Cancellation notice */}
        {isCancelling && (
          <div className="p-3 rounded-lg bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-800">
            <p className="text-xs text-orange-700 dark:text-orange-300 leading-relaxed">
              Your benefits will remain active until <strong>{endDate}</strong>. No further charges will be made. We do not offer pro-rated refunds for unused time.
            </p>
          </div>
        )}

        {/* Cancel Confirmation Dialog */}
        {showConfirm && !isCancelling && (
          <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-700 dark:text-red-300 leading-relaxed">
                Your benefits will remain active until <strong>{endDate}</strong>. No further charges will be made. We do not offer pro-rated refunds for unused time.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="destructive"
                onClick={handleCancel}
                disabled={cancelling}
                data-testid="confirm-cancel-btn"
                className="text-xs"
              >
                {cancelling ? <><RefreshCw className="h-3 w-3 animate-spin mr-1" /> Cancelling...</> : 'Confirm Cancellation'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowConfirm(false)}
                className="text-xs"
                data-testid="keep-plan-btn"
              >
                Keep My Plan
              </Button>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        {!isCancelling && !showConfirm && (
          <div className="flex gap-2 pt-1">
            {sub.tier === 'premium' && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs gap-1.5 border-purple-300 text-purple-600 hover:bg-purple-50 dark:border-purple-700 dark:text-purple-400"
                onClick={() => {
                  const event = new CustomEvent('scrollToPlans');
                  window.dispatchEvent(event);
                }}
                data-testid="upgrade-to-vip-btn"
              >
                <ArrowUpCircle className="h-3.5 w-3.5" />
                Upgrade to VIP
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="text-xs gap-1.5 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/10 ml-auto"
              onClick={() => setShowConfirm(true)}
              data-testid="cancel-subscription-btn"
            >
              <XCircle className="h-3.5 w-3.5" />
              Cancel Plan
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SubscriptionManagement;
