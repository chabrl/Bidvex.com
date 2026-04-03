import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  CreditCard, FileText, ExternalLink, Settings, Plus,
  BarChart3, Package, Gavel, AlertTriangle, CheckCircle,
  Clock, CalendarDays, DollarSign, ArrowRight, Loader2,
  Shield, TrendingUp, RefreshCw, XCircle, PartyPopper
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import EmailCreditPurchase from '../components/EmailCreditPurchase';

const API = API_BASE;

export default function PartnerDashboard() {
  const { user, token, refreshUser } = useAuth();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [dashboard, setDashboard] = useState(null);
  const [partnerStats, setPartnerStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [billingLoading, setBillingLoading] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [showCelebration, setShowCelebration] = useState(false);
  const [invoiceLoading, setInvoiceLoading] = useState(false);

  const fetchDashboard = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [dashRes, statsRes] = await Promise.all([
        axios.get(`${API}/partner/dashboard`, { headers }),
        axios.get(`${API}/partner/stats`, { headers }).catch(() => null),
      ]);
      setDashboard(dashRes.data);
      if (statsRes?.data) setPartnerStats(statsRes.data);
    } catch (err) {
      if (err.response?.status === 400) {
        navigate('/');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!user?.is_partner && user?.role !== 'admin' && user?.role !== 'superadmin') {
      navigate('/');
      return;
    }
    fetchDashboard();
  }, [user, navigate, fetchDashboard]);

  useEffect(() => {
    const status = searchParams.get('partner_payment');
    const sessionId = searchParams.get('session_id');
    if (status === 'success') {
      setShowCelebration(true);
      if (refreshUser) refreshUser();
      // Clean URL params after showing celebration
      setSearchParams({}, { replace: true });
      // Auto-dismiss celebration after 8 seconds
      setTimeout(() => setShowCelebration(false), 8000);
    } else if (status === 'cancelled') {
      toast.info(t('partnerDashboard.paymentCancelled'));
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, refreshUser, setSearchParams]);

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
      toast.error(err.response?.data?.detail || t('partnerDashboard.billingFailed'));
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
      toast.error(err.response?.data?.detail || t('partnerDashboard.checkoutFailed'));
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

  const handleDownloadInvoice = async () => {
    setInvoiceLoading(true);
    try {
      const res = await axios.get(`${API}/invoices`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const invoices = res.data.invoices || [];
      if (invoices.length === 0) {
        toast.info(t('partnerDashboard.noInvoices'));
        return;
      }
      const latest = invoices[0];
      const url = latest.download_url;
      if (url) {
        window.open(`${API_BASE}${url}`, '_blank');
      } else {
        window.open(`${API}/invoices/${latest.id}/download`, '_blank');
      }
    } catch (err) {
      toast.error(t('partnerDashboard.invoiceFailed'));
    } finally {
      setInvoiceLoading(false);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '—';
    const locale = i18n.language === 'fr' ? 'fr-CA' : 'en-CA';
    return new Date(iso).toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' });
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="partner-dashboard">
      {/* Soft Lock Banner */}
      {!isFeePaid && !showCelebration && (
        <div className="bg-amber-500 text-white" data-testid="partner-softlock-banner">
          <div className="max-w-6xl mx-auto px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-sm">{t('partnerDashboard.feeRequired')}</p>
                <p className="text-xs text-amber-100">
                  {t('partnerDashboard.feeRequiredDesc')}
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
                <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> {t('partnerDashboard.processing')}</>
              ) : (
                <><CreditCard className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.payNow')}</>
              )}
            </Button>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Celebration Banner (one-time after successful payment) */}
        {showCelebration && (
          <div 
            className="mb-6 rounded-xl border-2 border-emerald-300 bg-gradient-to-r from-emerald-50 to-teal-50 p-6 shadow-lg animate-in fade-in slide-in-from-top-4 duration-500"
            data-testid="celebration-banner"
          >
            <div className="flex items-start gap-4">
              <div className="h-12 w-12 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                <PartyPopper className="h-6 w-6 text-emerald-600" />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-bold text-emerald-900">{t('partnerDashboard.accountActivated')}</h2>
                <p className="text-sm text-emerald-700 mt-1">
                  {t('partnerDashboard.accountActivatedDesc')}
                </p>
                <div className="flex items-center gap-3 mt-4">
                  <Button 
                    onClick={() => navigate('/create-listing')}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    size="sm"
                    data-testid="celebration-create-listing-btn"
                  >
                    <Plus className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.createFirstListing')}
                  </Button>
                  <Button 
                    onClick={() => setShowCelebration(false)}
                    variant="ghost"
                    size="sm"
                    className="text-emerald-600"
                  >
                    {t('partnerDashboard.dismiss')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{t('partnerDashboard.title')}</h1>
              {isActive ? (
                <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200" data-testid="status-badge-active">
                  <CheckCircle className="h-3 w-3 mr-1" /> {t('partnerDashboard.active')}
                </Badge>
              ) : !isFeePaid ? (
                <Badge className="bg-amber-100 text-amber-700 border-amber-200" data-testid="status-badge-locked">
                  <XCircle className="h-3 w-3 mr-1" /> {t('partnerDashboard.paymentRequired')}
                </Badge>
              ) : (
                <Badge className="bg-blue-100 text-blue-700 border-blue-200" data-testid="status-badge-pending">
                  <Clock className="h-3 w-3 mr-1" /> {t('partnerDashboard.processing')}
                </Badge>
              )}
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {partner.company_name || t('partnerDashboard.title')} — {t('partnerDashboard.verified')} {formatDate(partner.verified_at)}
            </p>
          </div>
          {isFeePaid && (
            <Button
              onClick={() => navigate('/create-listing')}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="create-listing-btn"
            >
              <Plus className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.createListing')}
            </Button>
          )}
        </div>

        {/* ─── SaaS Stats Grid (from /api/partner/stats) ─── */}
        {partnerStats && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8" data-testid="partner-stats-grid">
            <div className="relative overflow-hidden rounded-xl border border-blue-100 dark:border-blue-900/40 bg-gradient-to-br from-blue-50 to-white dark:from-blue-950/20 dark:to-slate-900 p-5 shadow-sm">
              <div className="absolute -top-4 -right-4 h-20 w-20 rounded-full" style={{ backgroundColor: 'rgba(37,99,235,0.06)' }} />
              <dt className="text-xs font-medium uppercase tracking-wider text-blue-600 dark:text-blue-400 mb-1">
                {t('partnerDashboard.activeListings', 'Active Listings')}
              </dt>
              <dd className="text-3xl font-bold text-slate-900 dark:text-white" data-testid="stat-active-listings">
                {partnerStats.my_active_listings}
              </dd>
              <p className="text-xs text-slate-400 mt-1">
                {partnerStats.my_total_listings} {t('partnerDashboard.totalListingsLabel', 'total')}
              </p>
            </div>

            <div className="relative overflow-hidden rounded-xl border border-emerald-100 dark:border-emerald-900/40 bg-gradient-to-br from-emerald-50 to-white dark:from-emerald-950/20 dark:to-slate-900 p-5 shadow-sm">
              <div className="absolute -top-4 -right-4 h-20 w-20 rounded-full" style={{ backgroundColor: 'rgba(16,185,129,0.06)' }} />
              <dt className="text-xs font-medium uppercase tracking-wider text-emerald-600 dark:text-emerald-400 mb-1">
                {t('partnerDashboard.bidsReceived', 'Bids Received')}
              </dt>
              <dd className="text-3xl font-bold text-slate-900 dark:text-white" data-testid="stat-bids-received">
                {partnerStats.my_total_bids_received}
              </dd>
              <p className="text-xs text-slate-400 mt-1">
                {t('partnerDashboard.acrossAllListings', 'across all listings')}
              </p>
            </div>

            <div className="relative overflow-hidden rounded-xl border border-amber-100 dark:border-amber-900/40 bg-gradient-to-br from-amber-50 to-white dark:from-amber-950/20 dark:to-slate-900 p-5 shadow-sm">
              <div className="absolute -top-4 -right-4 h-20 w-20 rounded-full" style={{ backgroundColor: 'rgba(245,158,11,0.06)' }} />
              <dt className="text-xs font-medium uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">
                {t('partnerDashboard.projectedRevenue', 'Projected Revenue')}
              </dt>
              <dd className="text-3xl font-bold text-slate-900 dark:text-white" data-testid="stat-projected-revenue">
                ${partnerStats.my_projected_revenue?.toLocaleString('en-CA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </dd>
              <p className="text-xs text-slate-400 mt-1">
                {t('partnerDashboard.basedOnHighestBids', 'based on current highest bids')}
              </p>
            </div>
          </div>
        )}

        {/* ─── Partner Benefit Summary Card ─── */}
        {partnerStats?.partner_benefit && isActive && (
          <Card className="mb-8 border-emerald-200 dark:border-emerald-900/40 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/20 dark:to-teal-950/20 shadow-sm" data-testid="partner-benefit-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center">
                    <TrendingUp className="h-5 w-5 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-emerald-900 dark:text-emerald-100 text-sm">
                      {i18n.language === 'fr' ? 'Avantage Partenaire' : 'Partner Benefit'}
                    </h3>
                    <p className="text-xs text-emerald-700 dark:text-emerald-300">
                      {i18n.language === 'fr'
                        ? `En tant que Partenaire BidVex, vous avez conservé ${new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(partnerStats.partner_benefit.premiums_retained_this_month)} en primes acheteurs ce mois-ci.`
                        : `As a BidVex Partner, you retained ${new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(partnerStats.partner_benefit.premiums_retained_this_month)} in Buyer Premiums this month.`}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-300" data-testid="partner-benefit-amount">
                    ${partnerStats.partner_benefit.premiums_retained_this_month?.toLocaleString('en-CA', { minimumFractionDigits: 2 })}
                  </p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">
                    {partnerStats.partner_benefit.transactions_this_month} {i18n.language === 'fr' ? 'transactions' : 'transactions'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

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
                      {t('partnerDashboard.subscriptionBilling')}
                    </CardTitle>
                    <CardDescription className="mt-1">{t('partnerDashboard.subscriptionBillingDesc')}</CardDescription>
                  </div>
                  {isFeePaid && (
                    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs">
                      <CheckCircle className="h-3 w-3 mr-1" /> {t('partnerDashboard.feePaid')}
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
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{t('partnerDashboard.status')}</p>
                      <p className="text-sm font-semibold flex items-center gap-1.5">
                        {subscription.status === 'active' ? (
                          <><CheckCircle className="h-4 w-4 text-emerald-500" /> {t('partnerDashboard.active')}</>
                        ) : subscription.status === 'past_due' ? (
                          <><AlertTriangle className="h-4 w-4 text-amber-500" /> {t('partnerDashboard.pastDue')}</>
                        ) : (
                          <><XCircle className="h-4 w-4 text-red-500" /> {subscription.status}</>
                        )}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{t('partnerDashboard.plan')}</p>
                      <p className="text-sm font-semibold">${subscription.plan_amount} {subscription.plan_currency.toUpperCase()}/{subscription.plan_interval}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{t('partnerDashboard.currentPeriod')}</p>
                      <p className="text-sm">{formatDate(subscription.current_period_start)}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{t('partnerDashboard.nextBilling')}</p>
                      <p className="text-sm font-semibold">
                        {subscription.cancel_at_period_end ? (
                          <span className="text-amber-600">{t('partnerDashboard.cancelsOn', { date: formatDate(subscription.current_period_end) })}</span>
                        ) : (
                          formatDate(subscription.current_period_end)
                        )}
                      </p>
                    </div>
                  </div>
                ) : isFeePaid ? (
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 text-center">
                    <p className="text-sm text-slate-500">{t('partnerDashboard.subDetailsUnavail')}</p>
                  </div>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <p className="text-sm text-amber-700 font-medium">{t('partnerDashboard.noActiveSub')}</p>
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
                          <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> {t('partnerDashboard.opening')}</>
                        ) : (
                          <><FileText className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.viewInvoicesTax')}</>
                        )}
                      </Button>
                      <Button
                        onClick={handleDownloadInvoice}
                        variant="outline"
                        disabled={invoiceLoading}
                        data-testid="download-invoice-btn"
                      >
                        {invoiceLoading ? (
                          <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> {t('partnerDashboard.loading')}</>
                        ) : (
                          <><DollarSign className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.downloadLatestInvoice')}</>
                        )}
                      </Button>
                      <Button
                        onClick={handleManageBilling}
                        variant="outline"
                        disabled={billingLoading}
                        data-testid="update-payment-btn"
                      >
                        <CreditCard className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.updatePaymentMethod')}
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
                        <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> {t('partnerDashboard.processing')}</>
                      ) : (
                        <><CreditCard className="h-4 w-4 mr-1.5" /> {t('partnerDashboard.payAnnualFee')}</>
                      )}
                    </Button>
                  )}
                </div>

                <p className="text-xs text-slate-400">
                  {t('partnerDashboard.taxReceiptNote')}
                </p>
              </CardContent>
            </Card>

            {/* Email Marketing Credits */}
            {isActive && <EmailCreditPurchase />}

            {/* Recent Activity */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm" data-testid="recent-activity-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Clock className="h-5 w-5 text-slate-500" />
                  {t('partnerDashboard.recentActivity')}
                </CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="pt-4">
                {(dashboard.recent_listings.length === 0 && dashboard.recent_multi_auctions.length === 0) ? (
                  <div className="text-center py-8">
                    <Package className="h-10 w-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-500">{t('partnerDashboard.noListingsYet')}</p>
                    {isFeePaid && (
                      <Button onClick={() => navigate('/create-listing')} variant="link" className="mt-2 text-blue-600">
                        {t('partnerDashboard.createFirstLink')} <ArrowRight className="h-3 w-3 ml-1" />
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
                  {t('partnerDashboard.listingStats')}
                </CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="pt-5 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700 dark:text-blue-400">{stats.active_listings}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{t('partnerDashboard.activeListings')}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-slate-700 dark:text-slate-300">{stats.total_listings}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{t('partnerDashboard.totalListings')}</p>
                  </div>
                  <div className="bg-emerald-50 dark:bg-emerald-950/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">{stats.total_bids_received}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{t('partnerDashboard.bidsReceived')}</p>
                  </div>
                  <div className="bg-purple-50 dark:bg-purple-950/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-purple-700 dark:text-purple-400">{stats.active_multi}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{t('partnerDashboard.multiLotAuctions')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Account Info */}
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm" data-testid="account-info-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Shield className="h-5 w-5 text-slate-500" />
                  {t('partnerDashboard.accountDetails')}
                </CardTitle>
              </CardHeader>
              <Separator />
              <CardContent className="pt-5">
                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{t('partnerDashboard.company')}</dt>
                    <dd className="font-medium text-right">{partner.company_name || '—'}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{t('partnerDashboard.platformFee')}</dt>
                    <dd className="font-medium">
                      <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">3%</Badge>
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{t('partnerDashboard.buyerPremium')}</dt>
                    <dd className="font-medium">
                      {partner.custom_premium_rate
                        ? `${(partner.custom_premium_rate * 100).toFixed(1)}%`
                        : t('partnerDashboard.notSet')}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{t('partnerDashboard.stripeConnect')}</dt>
                    <dd className="font-medium">
                      {partner.stripe_connect_status === 'complete' ? (
                        <span className="text-emerald-600 flex items-center gap-1"><CheckCircle className="h-3 w-3" /> {t('partnerDashboard.connected')}</span>
                      ) : (
                        <span className="text-amber-600 flex items-center gap-1"><Clock className="h-3 w-3" /> {t('partnerDashboard.pending')}</span>
                      )}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{t('partnerDashboard.annualFee')}</dt>
                    <dd className="font-medium">
                      {isFeePaid ? (
                        <span className="text-emerald-600 flex items-center gap-1"><CheckCircle className="h-3 w-3" /> {t('partnerDashboard.paid')}</span>
                      ) : (
                        <span className="text-amber-600 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> {t('partnerDashboard.unpaid')}</span>
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
                  <TrendingUp className="h-4 w-4 mr-2 text-slate-500" /> {t('partnerDashboard.sellerDashboard')}
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => navigate('/settings')}
                  data-testid="link-settings"
                >
                  <Settings className="h-4 w-4 mr-2 text-slate-500" /> {t('partnerDashboard.accountSettings')}
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => navigate('/create-multi-item-listing')}
                  disabled={!isFeePaid}
                  data-testid="link-create-multi"
                >
                  <Gavel className="h-4 w-4 mr-2 text-slate-500" /> {t('partnerDashboard.createMultiLot')}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
