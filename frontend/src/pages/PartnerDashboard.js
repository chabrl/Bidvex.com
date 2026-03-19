import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  CreditCard, FileText, ExternalLink, Settings, Plus,
  BarChart3, Package, Gavel, AlertTriangle, CheckCircle,
  Clock, CalendarDays, DollarSign, ArrowRight, Loader2,
  Shield, TrendingUp, RefreshCw, XCircle
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PartnerDashboard() {
  const { user, token, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [billingLoading, setBillingLoading] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/partner/dashboard`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDashboard(res.data);
    } catch (err) {
      if (err.response?.status === 400) {
        navigate('/');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!user?.is_partner) {
      navigate('/');
      return;
    }
    fetchDashboard();
  }, [user, navigate, fetchDashboard]);

  useEffect(() => {
    const status = searchParams.get('partner_payment');
    if (status === 'success') {
      toast.success('Payment successful! Your partner account is now fully active.');
      if (refreshUser) refreshUser();
    } else if (status === 'cancelled') {
      toast.info('Payment was cancelled. You can complete it anytime from this dashboard.');
    }
  }, [searchParams, refreshUser]);

  const handleManageBilling = async () => {
    setBillingLoading(true);
    try {
      const res = await axios.post(`${API}/partner/manage-billing`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to open billing portal.');
    } finally {
      setBillingLoading(false);
    }
  };

  const handlePayNow = async () => {
    setCheckoutLoading(true);
    try {
      const res = await axios.post(`${API}/partner/create-checkout`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create payment session.');
    } finally {
      setCheckoutLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!dashboard) return null;

  const { partner, subscription, stats } = dashboard;
  const isFeePaid = partner.platform_fee_paid;
  const isActive = isFeePaid && subscription?.status === 'active';

  const formatDate = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-CA', { year: 'numeric', month: 'long', day: 'numeric' });
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="partner-dashboard">
      {/* Soft Lock Banner */}
      {!isFeePaid && (
        <div className="bg-amber-500 text-white" data-testid="partner-softlock-banner">
          <div className="max-w-6xl mx-auto px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-sm">Annual Partner Fee Required</p>
                <p className="text-xs text-amber-100">
                  Your partner fee of $100 CAD/year + taxes has not been paid. Listing capabilities are locked.
                </p>
              </div>
            </div>
            <Button
              onClick={handlePayNow}
              disabled={checkoutLoading}
              size="sm"
              className="bg-white text-amber-700 hover:bg-amber-50 font-semibold shrink-0"
              data-testid="softlock-pay-now-btn"
            >
              {checkoutLoading ? (
                <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Processing...</>
              ) : (
                <><CreditCard className="h-4 w-4 mr-1.5" /> Pay Now — $100 CAD/year</>
              )}
            </Button>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Partner Dashboard</h1>
              {isActive ? (
                <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200" data-testid="status-badge-active">
                  <CheckCircle className="h-3 w-3 mr-1" /> Active
                </Badge>
              ) : !isFeePaid ? (
                <Badge className="bg-amber-100 text-amber-700 border-amber-200" data-testid="status-badge-locked">
                  <XCircle className="h-3 w-3 mr-1" /> Payment Required
                </Badge>
              ) : (
                <Badge className="bg-blue-100 text-blue-700 border-blue-200" data-testid="status-badge-pending">
                  <Clock className="h-3 w-3 mr-1" /> Processing
                </Badge>
              )}
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {partner.company_name || 'Partner Account'} — Verified {formatDate(partner.verified_at)}
            </p>
          </div>
          {isFeePaid && (
            <Button
              onClick={() => navigate('/create-listing')}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="create-listing-btn"
            >
              <Plus className="h-4 w-4 mr-1.5" /> Create Listing
            </Button>
          )}
        </div>

        {/* Main Grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Column 1: Subscription & Billing (Priority 1) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Subscription Card */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm" data-testid="subscription-card">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg font-semibold flex items-center gap-2">
                      <CreditCard className="h-5 w-5 text-blue-600" />
                      Subscription & Billing
                    </CardTitle>
                    <CardDescription className="mt-1">Manage your annual partner fee and download tax receipts</CardDescription>
                  </div>
                  {isFeePaid && (
                    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs">
                      <CheckCircle className="h-3 w-3 mr-1" /> Fee Paid
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <Separator />
              <CardContent className="pt-5 space-y-5">
                {/* Subscription Details */}
                {subscription ? (
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Status</p>
                      <p className="text-sm font-semibold flex items-center gap-1.5">
                        {subscription.status === 'active' ? (
                          <><CheckCircle className="h-4 w-4 text-emerald-500" /> Active</>
                        ) : subscription.status === 'past_due' ? (
                          <><AlertTriangle className="h-4 w-4 text-amber-500" /> Past Due</>
                        ) : (
                          <><XCircle className="h-4 w-4 text-red-500" /> {subscription.status}</>
                        )}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Plan</p>
                      <p className="text-sm font-semibold">${subscription.plan_amount} {subscription.plan_currency.toUpperCase()}/{subscription.plan_interval}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Current Period</p>
                      <p className="text-sm">{formatDate(subscription.current_period_start)}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Next Billing</p>
                      <p className="text-sm font-semibold">
                        {subscription.cancel_at_period_end ? (
                          <span className="text-amber-600">Cancels on {formatDate(subscription.current_period_end)}</span>
                        ) : (
                          formatDate(subscription.current_period_end)
                        )}
                      </p>
                    </div>
                  </div>
                ) : isFeePaid ? (
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 text-center">
                    <p className="text-sm text-slate-500">Subscription details unavailable. Use the billing portal to view details.</p>
                  </div>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <p className="text-sm text-amber-700 font-medium">No active subscription. Complete your $100 CAD/year payment to activate.</p>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-3">
                  {isFeePaid ? (
                    <>
                      <Button
                        onClick={handleManageBilling}
                        disabled={billingLoading}
                        variant="default"
                        className="bg-blue-600 hover:bg-blue-700"
                        data-testid="manage-billing-btn"
                      >
                        {billingLoading ? (
                          <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Opening...</>
                        ) : (
                          <><FileText className="h-4 w-4 mr-1.5" /> View Invoices & Tax Receipts</>
                        )}
                      </Button>
                      <Button
                        onClick={handleManageBilling}
                        variant="outline"
                        disabled={billingLoading}
                        data-testid="update-payment-btn"
                      >
                        <CreditCard className="h-4 w-4 mr-1.5" /> Update Payment Method
                      </Button>
                    </>
                  ) : (
                    <Button
                      onClick={handlePayNow}
                      disabled={checkoutLoading}
                      className="bg-emerald-600 hover:bg-emerald-700"
                      data-testid="pay-annual-fee-btn"
                    >
                      {checkoutLoading ? (
                        <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Processing...</>
                      ) : (
                        <><CreditCard className="h-4 w-4 mr-1.5" /> Pay $100 CAD/year + taxes</>
                      )}
                    </Button>
                  )}
                </div>

                <p className="text-xs text-slate-400">
                  Your GST/QST tax receipts are available through the Stripe billing portal. Click "View Invoices & Tax Receipts" above.
                </p>
              </CardContent>
            </Card>

            {/* Recent Activity */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm" data-testid="recent-activity-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Clock className="h-5 w-5 text-slate-500" />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="pt-4">
                {(dashboard.recent_listings.length === 0 && dashboard.recent_multi_auctions.length === 0) ? (
                  <div className="text-center py-8">
                    <Package className="h-10 w-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-500">No listings yet.</p>
                    {isFeePaid && (
                      <Button onClick={() => navigate('/create-listing')} variant="link" className="mt-2 text-blue-600">
                        Create your first listing <ArrowRight className="h-3 w-3 ml-1" />
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {dashboard.recent_listings.map((item) => (
                      <div key={item.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                          <Package className="h-4 w-4 text-slate-400 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{item.title}</p>
                            <p className="text-xs text-slate-400">{formatDate(item.created_at)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {item.bid_count > 0 && (
                            <span className="text-xs text-slate-500">{item.bid_count} bids</span>
                          )}
                          <Badge variant="outline" className="text-[10px]">{item.status}</Badge>
                        </div>
                      </div>
                    ))}
                    {dashboard.recent_multi_auctions.map((item) => (
                      <div key={item.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                          <Gavel className="h-4 w-4 text-blue-400 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{item.title}</p>
                            <p className="text-xs text-slate-400">{item.lot_count} lots — {formatDate(item.created_at)}</p>
                          </div>
                        </div>
                        <Badge variant="outline" className="text-[10px]">{item.status}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Column 2: Stats & Account Info */}
          <div className="space-y-6">
            {/* Stats Cards */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm" data-testid="stats-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-blue-600" />
                  Listing Stats
                </CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="pt-5 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700 dark:text-blue-400">{stats.active_listings}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Active Listings</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-slate-700 dark:text-slate-300">{stats.total_listings}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Total Listings</p>
                  </div>
                  <div className="bg-emerald-50 dark:bg-emerald-950/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">{stats.total_bids_received}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Bids Received</p>
                  </div>
                  <div className="bg-purple-50 dark:bg-purple-950/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-purple-700 dark:text-purple-400">{stats.active_multi}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Multi-Lot Auctions</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Account Info */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm" data-testid="account-info-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Shield className="h-5 w-5 text-slate-500" />
                  Account Details
                </CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="pt-5">
                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Company</dt>
                    <dd className="font-medium text-right">{partner.company_name || '—'}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Platform Fee</dt>
                    <dd className="font-medium">
                      <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">3%</Badge>
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Buyer Premium</dt>
                    <dd className="font-medium">
                      {partner.custom_premium_rate
                        ? `${(partner.custom_premium_rate * 100).toFixed(1)}%`
                        : 'Not set'}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Stripe Connect</dt>
                    <dd className="font-medium">
                      {partner.stripe_connect_status === 'complete' ? (
                        <span className="text-emerald-600 flex items-center gap-1"><CheckCircle className="h-3 w-3" /> Connected</span>
                      ) : (
                        <span className="text-amber-600 flex items-center gap-1"><Clock className="h-3 w-3" /> Pending</span>
                      )}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Annual Fee</dt>
                    <dd className="font-medium">
                      {isFeePaid ? (
                        <span className="text-emerald-600 flex items-center gap-1"><CheckCircle className="h-3 w-3" /> Paid</span>
                      ) : (
                        <span className="text-amber-600 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Unpaid</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>

            {/* Quick Links */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardContent className="pt-5 space-y-2">
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => navigate('/seller/dashboard')}
                  data-testid="link-seller-dashboard"
                >
                  <TrendingUp className="h-4 w-4 mr-2 text-slate-500" /> Seller Dashboard
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => navigate('/settings')}
                  data-testid="link-settings"
                >
                  <Settings className="h-4 w-4 mr-2 text-slate-500" /> Account Settings
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => navigate('/create-multi-item-listing')}
                  disabled={!isFeePaid}
                  data-testid="link-create-multi"
                >
                  <Gavel className="h-4 w-4 mr-2 text-slate-500" /> Create Multi-Lot Auction
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
