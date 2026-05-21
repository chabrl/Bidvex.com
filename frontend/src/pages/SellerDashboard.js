import API_BASE from '../config';
import ErrorBoundary from '../components/ErrorBoundary';
import FeaturedCountdownRibbon from '../components/FeaturedCountdownRibbon';
import DealerAnnualFeeBanner from '../components/DealerAnnualFeeBanner';
import DemoModeBanner from '../components/DemoModeBanner';
import CommissionPayoutMethodCard from '../components/CommissionPayoutMethodCard';
import { PayoutSummary } from '../components/PayoutSummary'; // iter210 Step 6
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import TaxInterviewModal from '../components/TaxInterviewModal';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Plus, DollarSign, Package, FileText, ShoppingBag, Heart, Eye, TrendingUp, BarChart3, Wallet, Info, AlertTriangle, Clock, Shield, Mail, Loader2, MapPin, Zap, Lock } from 'lucide-react';
import { toast } from 'sonner';
import SellerAnalyticsDashboard from '../components/SellerAnalyticsDashboard';
import SellerEarningsDashboard from '../components/SellerEarningsDashboard';
import { SellerEscrowPanel } from '../components/EscrowPickupPanel';
import VehicleSettlements from './seller/VehicleSettlements';
import PilotWelcomeBanner from './seller/PilotWelcomeBanner';
import { formatCurrency, formatPercent } from '../utils/currencyFormatter';
import { LoadingTimeout } from '../components/LoadingTimeout';
import InfoTip from '../components/InfoTip';
import PendingAiReviewBanner from '../components/PendingAiReviewBanner';

const API = API_BASE;

const SellerDashboard = () => {
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();
  const { canCreateMultiLot } = useFeatureFlags();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('listings');
  const [deletionRequestModal, setDeletionRequestModal] = useState({ open: false, listing: null, isMultiItem: false });
  const [deletionReason, setDeletionReason] = useState('');
  const [deletionSubmitting, setDeletionSubmitting] = useState(false);
  const [showTaxModal, setShowTaxModal] = useState(false);
  const [dealerSubStatus, setDealerSubStatus] = useState(null);

  useEffect(() => {
    fetchDashboard();
    // iter211 P3 — fetch dealer subscription status to gate listing creation
    if (user?.is_vehicle_dealer) {
      axios.get(`${API}/dealer-subscription/status`)
        .then(r => setDealerSubStatus(r.data))
        .catch(() => setDealerSubStatus(null));
    }
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/seller`, { timeout: 15000 });
      setDashboard(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
      toast.error(t('dashboard.seller.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteListing = async (listingId, isMultiItem = false) => {
    // Sellers can only REQUEST deletion, not delete directly
    setDeletionRequestModal({ 
      open: true, 
      listing: { id: listingId, isMultiItem },
      isMultiItem 
    });
  };
  
  const handleSubmitDeletionRequest = async () => {
    if (deletionReason.trim().length < 20) {
      toast.error(t('dashboard.seller.deletionReasonTooShort', 'Please provide a reason (minimum 20 characters)'));
      return;
    }
    
    setDeletionSubmitting(true);
    try {
      const { listing, isMultiItem } = deletionRequestModal;
      const endpoint = isMultiItem ? 'multi-item-listings' : 'listings';
      
      await axios.post(`${API}/${endpoint}/${listing.id}/request-deletion`, {
        reason: deletionReason
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(t('dashboard.seller.deletionRequestSubmitted', 'Deletion request submitted. Admin will review shortly.'));
      setDeletionRequestModal({ open: false, listing: null, isMultiItem: false });
      setDeletionReason('');
      fetchDashboard();
    } catch (error) {
      console.error('Deletion request failed:', error);
      toast.error(error.response?.data?.detail || t('dashboard.seller.deletionRequestFailed', 'Failed to submit deletion request'));
    } finally {
      setDeletionSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen py-8 px-4">
        <div className="max-w-7xl mx-auto">
          <LoadingTimeout rows={6} variant="cards" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-4 sm:py-8 px-3 sm:px-4 pb-24 lg:pb-8" data-testid="seller-dashboard">
      <div className="max-w-7xl mx-auto space-y-5 sm:space-y-8">
        {/* iter211 P4 — Demo mode banner (renders only for is_demo_account users) */}
        <DemoModeBanner user={user} />

        {/* iter197 — Pilot Welcome Banner (auto-hides after 7 days post-approval or on dismiss) */}
        <PilotWelcomeBanner user={user} token={token} />

        {/* iter211 P3 — Vehicle Dealer Annual Fee Banner (only renders if user.is_vehicle_dealer) */}
        <DealerAnnualFeeBanner user={user} />

        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-4">
          <div className="w-full sm:w-auto">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-bold">{t('dashboard.seller.title')}</h1>
              {/* Tax Status Badge */}
              {user.tax_onboarding_completed && (
                <Badge className={
                  user.tax_verification_status === 'verified' 
                    ? 'bg-green-500 text-white'
                    : user.tax_verification_status === 'action_required'
                    ? 'bg-red-500 text-white'
                    : 'bg-yellow-500 text-white'
                }>
                  {user.tax_verification_status === 'verified' && t('dashboard.seller.taxVerified')}
                  {user.tax_verification_status === 'pending' && t('dashboard.seller.taxPending')}
                  {user.tax_verification_status === 'action_required' && t('dashboard.seller.taxActionRequired')}
                </Badge>
              )}
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground flex items-center gap-1.5 flex-wrap">
              <span>
                {user.account_type === 'business' ? t('dashboard.seller.businessAccount') : t('dashboard.seller.personalAccount')} - 
                {t('dashboard.seller.commissionRate')}: {user.subscription_tier === 'vip' ? '2%' : user.subscription_tier === 'premium' ? '2.5%' : '4%'}
              </span>
              <InfoTip
                en="Your commission rate is BidVex's percentage of each successful sale. VIP and Premium tiers pay lower rates. No commission is charged on unsold items."
                fr="Votre taux de commission est le pourcentage que BidVex prélève sur chaque vente réussie. Les abonnés VIP et Premium paient un taux réduit. Aucune commission n'est facturée sur les articles invendus."
              />
            </p>
          </div>
          <div className="flex flex-wrap gap-2 w-full sm:w-auto">
            {(() => {
              // iter211 P3 — Gate "Create Listing" when dealer has no active subscription
              const isDealerLocked = user?.is_vehicle_dealer
                && dealerSubStatus !== null
                && dealerSubStatus?.active !== true;
              return (
                <Button
                  className="gradient-button text-white border-0 flex-1 sm:flex-initial min-w-0"
                  onClick={() => {
                    if (isDealerLocked) {
                      const fr = (i18n.language || 'en').startsWith('fr');
                      toast.error(fr ? 'Payez vos frais annuels pour commencer' : 'Pay your annual fee to start listing');
                      return;
                    }
                    navigate('/create-listing');
                  }}
                  disabled={isDealerLocked}
                  title={isDealerLocked ? ((i18n.language || 'en').startsWith('fr') ? 'Payez vos frais annuels pour commencer' : 'Pay your annual fee to start listing') : undefined}
                  data-testid="create-listing-btn"
                >
                  {isDealerLocked ? <Lock className="mr-1.5 sm:mr-2 h-4 w-4 flex-shrink-0" /> : <Plus className="mr-1.5 sm:mr-2 h-4 w-4 flex-shrink-0" />}
                  <span className="truncate">{t('dashboard.seller.createListing')}</span>
                </Button>
              );
            })()}
            {canCreateMultiLot(user) && (
              <Button
                variant="outline"
                className="flex-1 sm:flex-initial min-w-0"
                onClick={() => navigate('/create-multi-item-listing')}
                data-testid="create-lot-btn"
              >
                <Package className="mr-1.5 sm:mr-2 h-4 w-4 flex-shrink-0" />
                <span className="truncate">{t('dashboard.seller.createLot', 'Create Lot')}</span>
              </Button>
            )}
            <Button
              variant="outline"
              className="flex-1 sm:flex-initial min-w-0"
              onClick={() => navigate('/client-marketing')}
              data-testid="client-marketing-btn"
            >
              <Mail className="mr-1.5 sm:mr-2 h-4 w-4 flex-shrink-0" />
              <span className="truncate">{t('dashboard.seller.clientMarketing', 'Marketing')}</span>
            </Button>
          </div>
        </div>

        {/* Tab Navigation — horizontally scrollable on mobile */}
        <div className="border-b border-slate-200 dark:border-slate-700 -mx-4 sm:mx-0 px-4 sm:px-0">
          <div className="flex overflow-x-auto no-scrollbar -mb-px scroll-smooth" data-testid="seller-tabs">
          <button
            onClick={() => setActiveTab('listings')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'listings'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="tab-listings"
          >
            <Package className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            {t('dashboard.seller.listings', 'Listings')}
          </button>
          <button
            onClick={() => setActiveTab('earnings')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'earnings'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="earnings-tab"
          >
            <Wallet className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            {t('dashboard.seller.earnings', 'Earnings & Payouts')}
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'analytics'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="tab-analytics"
          >
            <BarChart3 className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            {t('dashboard.seller.analytics', 'Analytics')}
          </button>
          <button
            onClick={() => setActiveTab('ratings')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'ratings'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="ratings-tab"
          >
            <TrendingUp className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            Ratings & Reviews
          </button>
          <button
            onClick={() => setActiveTab('trends')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'trends'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="trends-tab"
          >
            <MapPin className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            Market Trends
          </button>
          <button
            onClick={() => setActiveTab('escrow')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'escrow'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="escrow-tab"
          >
            <Lock className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            {t('dashboard.seller.escrow', 'Escrow & Pickup')}
          </button>
          <button
            onClick={() => setActiveTab('vehicle-settlements')}
            className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0 ${
              activeTab === 'vehicle-settlements'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid="vehicle-settlements-tab"
          >
            <Shield className="h-4 w-4 inline mr-1.5 sm:mr-2" />
            Vehicle Settlements
          </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'earnings' ? (
          <div className="space-y-6">
            {/* iter211 Task 2 — Commission payout method toggle (only for eligible accounts) */}
            <CommissionPayoutMethodCard user={user} />
            <SellerEarningsDashboard />
          </div>
        ) : activeTab === 'analytics' ? (
          <SellerAnalyticsDashboard />
        ) : activeTab === 'ratings' ? (
          <SellerRatingsPanel userId={user?.id} token={token} />
        ) : activeTab === 'trends' ? (
          <RegionalTrendsPanel token={token} />
        ) : activeTab === 'escrow' ? (
          <SellerEscrowPanel />
        ) : activeTab === 'vehicle-settlements' ? (
          <VehicleSettlements />
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-6">
          <StatCard
            icon={<Package className="h-6 w-6" />}
            title={t('dashboard.seller.activeListings')}
            value={dashboard?.active_listings || 0}
            color="blue"
            tip={{ en: "Items currently live and accepting bids.", fr: "Articles actuellement en ligne et acceptant des enchères." }}
          />
          <StatCard
            icon={<ShoppingBag className="h-6 w-6" />}
            title={t('dashboard.seller.soldItems')}
            value={dashboard?.sold_listings || 0}
            color="green"
            tip={{ en: "Total items successfully sold through auctions.", fr: "Total des articles vendus avec succès via les enchères." }}
          />
          <StatCard
            icon={<FileText className="h-6 w-6" />}
            title={t('dashboard.seller.draftListings')}
            value={dashboard?.draft_listings || 0}
            color="orange"
            tip={{ en: "Listings saved but not yet published.", fr: "Annonces enregistrées mais pas encore publiées." }}
          />
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title={t('dashboard.seller.totalSales')}
            value={formatCurrency(dashboard?.total_sales || 0)}
            color="purple"
            tip={{ en: "Gross revenue from all completed sales before fees.", fr: "Revenus bruts de toutes les ventes complétées avant les frais." }}
          />
          {/* Net Payout Card - Shows what seller will receive after commission */}
          <NetPayoutCard 
            totalSales={dashboard?.total_sales || 0}
            subscriptionTier={user?.subscription_tier || 'free'}
            taxVerified={user?.tax_verification_status === 'verified'}
          />
        </div>

        {/* Tax Verification Warning */}
        {user?.tax_verification_status !== 'verified' && user?.tax_onboarding_completed && (
          <Card className="border-2 border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-6 w-6 text-yellow-600 flex-shrink-0" />
                <div>
                  <p className="font-semibold text-yellow-900 dark:text-yellow-100 mb-1">
                    {t('dashboard.seller.payoutsOnHold')}
                  </p>
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    {t('dashboard.seller.payoutsOnHoldDesc')}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tax Information Management Card */}
        <Card className="border-2 border-blue-200 dark:border-blue-800">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Shield className="h-6 w-6 text-blue-600" />
                <CardTitle>
                  {t('dashboard.seller.taxInfo')}
                </CardTitle>
              </div>
              {user?.tax_onboarding_completed && (
                <Badge className={
                  user.tax_verification_status === 'verified' 
                    ? 'bg-green-500 text-white'
                    : user.tax_verification_status === 'action_required'
                    ? 'bg-red-500 text-white'
                    : 'bg-yellow-500 text-white'
                }>
                  {user.tax_verification_status === 'verified' && t('dashboard.seller.verified')}
                  {user.tax_verification_status === 'pending' && t('dashboard.seller.pendingReview')}
                  {user.tax_verification_status === 'action_required' && t('dashboard.seller.actionRequired')}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {user?.tax_onboarding_completed ? (
              <>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">
                      {t('dashboard.seller.sellerType')}
                    </p>
                    <p className="font-semibold text-slate-900 dark:text-slate-100">
                      {user.seller_type === 'business' 
                        ? t('dashboard.seller.registeredBusiness')
                        : t('dashboard.seller.individualSeller')}
                    </p>
                  </div>
                  {user.business_province && (
                    <div>
                      <p className="text-muted-foreground">
                        {t('dashboard.seller.province')}
                      </p>
                      <p className="font-semibold text-slate-900 dark:text-slate-100">{user.business_province}</p>
                    </div>
                  )}
                  {user.legal_business_name && (
                    <div className="md:col-span-2">
                      <p className="text-muted-foreground">
                        {t('dashboard.seller.legalBusinessName')}
                      </p>
                      <p className="font-semibold text-slate-900 dark:text-slate-100">{user.legal_business_name}</p>
                    </div>
                  )}
                </div>
                
                <Button
                  variant="outline"
                  onClick={() => setShowTaxModal(true)}
                  className="w-full"
                >
                  {t('dashboard.seller.updateTaxInfo')}
                </Button>
                
                <p className="text-xs text-muted-foreground text-center">
                  {t('dashboard.seller.updateTaxDesc')}
                </p>
              </>
            ) : (
              <>
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                  <p className="text-sm text-blue-900 dark:text-blue-100 mb-3">
                    {t('dashboard.seller.taxRequired')}
                  </p>
                </div>
                
                <Button
                  onClick={() => setShowTaxModal(true)}
                  className="w-full gradient-button text-white"
                >
                  {t('dashboard.seller.completeTaxProfile')}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Fee Structure & 14-Day Payment Rule Info */}
        <Card className="border-2 border-blue-200 dark:border-blue-700 bg-gradient-to-r from-blue-50 to-slate-50 dark:from-blue-900/20 dark:to-slate-800/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2 text-blue-800 dark:text-blue-300">
              <Shield className="h-5 w-5" />
              {t('dashboard.seller.feeStructureTitle')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Seller Commission */}
              <div className="p-4 bg-white dark:bg-slate-800 rounded-lg border border-blue-200 dark:border-blue-700">
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign className="h-5 w-5 text-blue-600" />
                  <span className="font-semibold text-slate-900 dark:text-white">{t('dashboard.seller.yourCommission')}</span>
                </div>
                <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                  {user?.subscription_tier === 'vip' ? '2%' : user?.subscription_tier === 'premium' ? '2.5%' : user?.subscription_tier === 'partner_pro' ? '3%' : '4%'}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {user?.subscription_tier === 'vip' 
                    ? t('dashboard.seller.vipDiscount')
                    : user?.subscription_tier === 'premium'
                    ? t('dashboard.seller.premiumDiscount')
                    : user?.subscription_tier === 'partner_pro'
                    ? t('dashboard.seller.partnerProDiscount')
                    : t('dashboard.seller.standardRate')}
                </p>
              </div>

              {/* 14-Day Payment Rule */}
              <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border-2 border-red-300 dark:border-red-700">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="h-5 w-5 text-red-600 dark:text-red-400" />
                  <span className="font-semibold text-red-800 dark:text-red-300">{t('dashboard.seller.paymentDeadline')}</span>
                </div>
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">{t('dashboard.seller.fourteenDays')}</p>
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                  {t('fees.settlement')}
                </p>
              </div>

              {/* Late Payment Warning */}
              <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-300 dark:border-amber-700">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  <span className="font-semibold text-amber-800 dark:text-amber-300">{t('dashboard.seller.latePenalty')}</span>
                </div>
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">2%/{t('time.month', 'month')}</p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  {t('dashboard.seller.interestOverdue')}
                </p>
              </div>
            </div>
            
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-4 text-center">
              <a href="/terms-of-service" className="text-blue-600 dark:text-blue-400 hover:underline">
                {t('dashboard.seller.viewTerms')} →
              </a>
            </p>
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>{t('dashboard.seller.yourListings')}</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard?.all_listings && dashboard.all_listings.length > 0 ? (
              <div className="space-y-4">
                {dashboard.all_listings.map((listing) => {
                  // Check if this is a multi-item listing or single listing
                  const isMultiItem = listing.lots && listing.lots.length > 0;
                  const displayPrice = isMultiItem 
                    ? listing.lots.reduce((sum, lot) => sum + (lot.starting_price || 0), 0)
                    : listing.current_price;
                  const totalBids = isMultiItem
                    ? listing.lots.reduce((sum, lot) => sum + (lot.bid_count || 0), 0)
                    : listing.bid_count;
                  const itemCount = isMultiItem ? listing.lots.length : 1;
                  
                  return (
                  <div
                    key={listing.id}
                    className="flex flex-col sm:flex-row gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                    data-testid={`listing-item-${listing.id}`}
                  >
                    <div className="w-full sm:w-24 h-24 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                      {listing.images && listing.images[0] ? (
                        <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                      ) : isMultiItem && listing.lots[0]?.images?.[0] ? (
                        <img src={listing.lots[0].images[0]} alt={listing.title} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          {isMultiItem ? '📦' : '📦'}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div>
                          <h3 className="font-semibold truncate">{listing.title}</h3>
                          {isMultiItem && (
                            <p className="text-xs text-muted-foreground">{itemCount} {t('dashboard.seller.lots')}</p>
                          )}
                        </div>
                        <Badge
                          variant={
                            listing.status === 'active' ? 'default' :
                            listing.status === 'pending_review' ? 'destructive' :
                            listing.status === 'pending_admin_review' || listing.status === 'pending_ai_review' ? 'outline' :
                            'secondary'
                          }
                          className={
                            (listing.status === 'pending_admin_review' || listing.status === 'pending_ai_review')
                              ? 'border-amber-400 bg-amber-100 text-amber-900 font-semibold'
                              : undefined
                          }
                          data-testid={`listing-status-${listing.id}`}
                        >
                          {(listing.status === 'pending_admin_review' || listing.status === 'pending_ai_review')
                            ? '⏳ Under Review — Verification takes 5–50 minutes.'
                            : t(`dashboard.seller.status${listing.status.charAt(0).toUpperCase() + listing.status.slice(1)}`, listing.status)}
                        </Badge>
                      </div>

                      {/* iter211 — Featured countdown ribbon (seller-only, hidden when no active promotion) */}
                      {listing.status === 'active' && (listing.promoted_until || listing.is_featured) && (
                        <div className="mb-2" data-testid={`featured-ribbon-${listing.id}`}>
                          <FeaturedCountdownRibbon
                            featuredUntil={listing.promoted_until}
                            tier={listing.promotion_tier}
                          />
                        </div>
                      )}

                      {/* iter211 P4 — Demo listing badge (seller-only) */}
                      {listing.is_demo && (
                        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-amber-100 border border-amber-300 px-2.5 py-0.5 text-[11px] font-medium text-amber-900" data-testid={`demo-badge-${listing.id}`}>
                          <span>🎭</span>
                          <span>{(i18n.language || 'en').startsWith('fr') ? 'DÉMO — Non visible au public' : 'DEMO — Not visible to public'}</span>
                        </div>
                      )}

                      {/* iter206 — Surface compliance pause reason directly to the seller */}
                      {listing.status === 'pending_review' && (listing.compliance_signals || listing.paused_reason) && (
                        <div
                          className="mb-2 rounded-md border border-rose-300 bg-rose-50 p-2.5 text-xs"
                          data-testid={`listing-pause-reason-${listing.id}`}
                        >
                          <div className="flex items-start gap-2">
                            <span className="text-rose-600 font-bold">⛔</span>
                            <div className="min-w-0">
                              <p className="font-semibold text-rose-900">
                                {t('dashboard.seller.pausedTitle', 'This listing was paused for compliance review')}
                              </p>
                              <p className="text-rose-700 mt-0.5">
                                {listing.paused_reason === 'vehicle_listing_by_non_dealer'
                                  ? t('dashboard.seller.pausedVehicleNonDealer',
                                      'Vehicle listings are restricted to verified provincial dealers (OMVIC, AMVIC, VSA, SAAQ, FCAA, etc.). Please verify your dealer licence or wait for an admin to approve this listing.')
                                  : (listing.paused_reason || t('dashboard.seller.pausedGeneric', 'A moderator is reviewing this listing.'))}
                              </p>
                              {listing.compliance_signals && listing.compliance_signals.length > 0 && (
                                <p className="text-[10px] font-mono text-rose-600 mt-1">
                                  {t('dashboard.seller.detected', 'Detected')}: {listing.compliance_signals.slice(0, 5).join(', ')}
                                </p>
                              )}
                              <button
                                type="button"
                                onClick={() => navigate('/vehicle-auctions/dealer-license')}
                                className="mt-1.5 text-[11px] font-semibold text-rose-700 hover:text-rose-900 underline"
                                data-testid={`listing-verify-license-${listing.id}`}
                              >
                                {t('dashboard.seller.verifyLicence', 'Verify dealer licence →')}
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {listing.status === 'rejected' && (
                        <div className="mb-2 rounded-md border border-slate-300 bg-slate-50 p-2.5 text-xs"
                             data-testid={`listing-rejected-${listing.id}`}>
                          <p className="font-semibold text-slate-800">
                            ❌ {t('dashboard.seller.rejectedTitle', 'Listing rejected by moderator')}
                          </p>
                          {listing.rejection_note && (
                            <p className="text-slate-600 mt-0.5">{listing.rejection_note}</p>
                          )}
                        </div>
                      )}

                      {/* FEATURE PATCH v9 / Feature 3 + Phase 6.0 — Pending review banner */}
                      {(listing.status === 'pending_ai_review' || listing.status === 'pending_admin_review') && (
                        <PendingAiReviewBanner listing={listing} onActionDone={fetchDashboard} />
                      )}

                      <div className="flex flex-wrap gap-4 text-sm mb-2">
                        <span className="text-green-600 font-semibold">
                          <DollarSign className="h-3 w-3 inline mr-1" />
                          {formatCurrency(displayPrice)}
                        </span>
                        <span className="text-blue-600">
                          <TrendingUp className="h-3 w-3 inline mr-1" />
                          {totalBids} {t('dashboard.seller.bids')}
                        </span>
                        <span className="text-gray-600">
                          <Eye className="h-3 w-3 inline mr-1" />
                          {listing.views} {t('dashboard.seller.views')}
                        </span>
                        <span className="text-red-600">
                          <Heart className="h-3 w-3 inline mr-1 fill-current" />
                          {listing.wishlist_count || 0} {t('dashboard.seller.wishlisted')}
                        </span>
                      </div>
                      <div className="flex flex-col lg:flex-row gap-2">
                        {/* Phase 6.0 hotfix — fully locked card while under admin review: no view, edit, or delete affordances. */}
                        {(listing.status === 'pending_admin_review' || listing.status === 'pending_ai_review') ? (
                          <div
                            className="w-full text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
                            data-testid={`locked-card-notice-${listing.id}`}
                          >
                            🔒 {(i18n.language || 'en').startsWith('fr')
                                ? 'Annonce verrouillée pendant la révision — aucune modification possible.'
                                : 'Listing locked while under review — no edits, deletions or public view.'}
                          </div>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => navigate(isMultiItem ? `/lots/${listing.id}` : `/listing/${listing.id}`)}
                              data-testid={`view-listing-row-${listing.id}`}
                              className="w-full lg:w-auto"
                            >
                              {t('dashboard.seller.view')}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDeleteListing(listing.id, isMultiItem)}
                              data-testid={`delete-listing-${listing.id}`}
                              className="w-full lg:w-auto"
                            >
                              {t('dashboard.seller.requestDeletion', 'Request Deletion')}
                            </Button>
                          </>
                        )}
                      </div>

                      {/* Post-Sale Contact Info — Buyer */}
                      {listing.status === 'sold' && listing.buyer_contact && (
                        <div className="mt-3 p-4 rounded-lg border border-emerald-200 bg-emerald-50 dark:bg-emerald-950 dark:border-emerald-800" data-testid={`contact-buyer-${listing.id}`}>
                          <p className="text-xs uppercase font-semibold text-emerald-800 dark:text-emerald-300 mb-2">Contact Buyer / Contacter l'acheteur</p>
                          <dl className="text-sm space-y-1">
                            <div className="flex justify-between"><dt className="text-muted-foreground">Name</dt><dd className="font-medium">{listing.buyer_contact.name || '—'}</dd></div>
                            <div className="flex justify-between"><dt className="text-muted-foreground">Email</dt><dd className="font-medium"><a className="text-emerald-700 hover:underline" href={`mailto:${listing.buyer_contact.email}`}>{listing.buyer_contact.email || '—'}</a></dd></div>
                            <div className="flex justify-between"><dt className="text-muted-foreground">Phone</dt><dd className="font-medium">{listing.buyer_contact.phone ? <a className="text-emerald-700 hover:underline" href={`tel:${listing.buyer_contact.phone}`}>{listing.buyer_contact.phone}</a> : '—'}</dd></div>
                          </dl>
                        </div>
                      )}

                      {/* iter210 Step 6 — Payout Summary for SOLD listings */}
                      {listing.status === 'sold' && (listing.current_price || listing.starting_price) && (
                        <div className="mt-3" data-testid={`payout-summary-${listing.id}`}>
                          <p className="text-xs uppercase font-semibold text-slate-600 dark:text-slate-300 mb-2">Payout Summary</p>
                          <PayoutSummary
                            hammerPrice={listing.current_price || listing.starting_price}
                            auctionType={listing.category_type || 'lots'}
                            sellerAccountType={
                              user?.is_partner ? 'partner' :
                              user?.is_vehicle_dealer ? 'vehicle_dealer' :
                              user?.is_storage_facility ? 'storage_facility' : 'individual'
                            }
                            sellerUserId={user?.id}
                            sellerTier={user?.subscription_tier || 'standard'}
                            partnerBpRate={user?.custom_premium_rate}
                            paymentMethod={(listing.payment_method || 'stripe').replace('-', '_')}
                            currency={listing.currency || 'CAD'}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12">
                <Package className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">{t('dashboard.seller.noListingsYet')}</p>
                <Button onClick={() => navigate('/create-listing')} className="gradient-button text-white border-0">
                  {t('dashboard.seller.createFirstListing')}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
          </>
        )}
      </div>
      
      {/* Deletion Request Modal */}
      {deletionRequestModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="text-red-600">
                {t('dashboard.seller.requestDeletion', 'Request Deletion')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t('dashboard.seller.deletionRequestDesc', 'Please provide a reason for requesting deletion. An admin will review your request.')}
              </p>
              <div>
                <label className="text-sm font-medium mb-2 block text-slate-900 dark:text-slate-100">
                  {t('dashboard.seller.reasonForDeletion', 'Reason for Deletion')} *
                </label>
                <textarea
                  value={deletionReason}
                  onChange={(e) => setDeletionReason(e.target.value)}
                  placeholder={t('dashboard.seller.deletionReasonPlaceholder', 'Explain why you need to delete this auction (minimum 20 characters)...')}
                  className="w-full px-3 py-2 border rounded-md min-h-[100px] text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800"
                  minLength={20}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {deletionReason.length}/20 {t('dashboard.seller.charsMinimum')}
                </p>
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setDeletionRequestModal({ open: false, listing: null, isMultiItem: false });
                    setDeletionReason('');
                  }}
                >
                  {t('common.cancel', 'Cancel')}
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleSubmitDeletionRequest}
                  disabled={deletionReason.trim().length < 20 || deletionSubmitting}
                  data-testid="submit-deletion-btn"
                >
                  {deletionSubmitting ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Submitting...</>
                  ) : (
                    t('dashboard.seller.submitRequest', 'Submit Request')
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Tax Interview Modal - For Editing */}
      {showTaxModal && (
        <TaxInterviewModal 
          user={user} 
          onComplete={() => {
            setShowTaxModal(false);
            window.location.reload();
          }}
          onCancel={() => setShowTaxModal(false)}
        />
      )}
    </div>
  );
};

const StatCard = ({ icon, title, value, color, tip }) => (
  <Card className="glassmorphism">
    <CardContent className="p-3 sm:p-6">
      <div className="flex items-center justify-between mb-2 sm:mb-4">
        <div className={`p-2 sm:p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
        {tip && <InfoTip en={tip.en} fr={tip.fr} />}
      </div>
      <p className="text-xl sm:text-2xl font-bold mb-0.5 sm:mb-1">{value}</p>
      <p className="text-xs sm:text-sm text-muted-foreground leading-tight">{title}</p>
    </CardContent>
  </Card>
);

/**
 * NetPayoutCard - Shows seller's net earnings after BidVex commission
 * Implements "Seller Dashboard Net Payout" from the Disruptor Protocol
 * 
 * Commission rates (NO CAP - percentage only):
 * - Free tier: 4%
 * - Premium tier: 2.5% (1.5% savings)
 * - VIP tier: 2% (2% savings)
 */
const NetPayoutCard = ({ totalSales = 0, subscriptionTier = 'free', taxVerified = false }) => {
  const { t } = useTranslation();
  // Calculate commission based on subscription tier
  const getCommissionRate = () => {
    switch (subscriptionTier) {
      case 'vip':
        return 0.02; // 2% for VIP
      case 'premium':
        return 0.025; // 2.5% for premium
      default:
        return 0.04; // 4% for free tier
    }
  };

  const effectiveRate = getCommissionRate();
  const commissionAmount = totalSales * effectiveRate;
  const netPayout = totalSales - commissionAmount;

  return (
    <Card className="glassmorphism border-2 border-green-200 dark:border-green-900/50">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-green-100 to-emerald-100 dark:from-green-900/30 dark:to-emerald-900/30">
            <Wallet className="h-6 w-6 text-green-600" />
          </div>
          <div className="group relative">
            <Info className="h-4 w-4 text-muted-foreground cursor-help" />
            <div className="absolute right-0 top-6 w-64 bg-gray-900 text-white text-xs p-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
              <p className="font-semibold mb-1">{t('dashboard.seller.netPayoutCalc')}</p>
              <p>{t('dashboard.seller.totalSalesLabel')}: {formatCurrency(totalSales)}</p>
              <p>{t('dashboard.seller.commission')} ({formatPercent(effectiveRate * 100, 1)}): -{formatCurrency(commissionAmount)}</p>
              <p className="border-t border-gray-700 mt-1 pt-1 font-semibold">
                {t('dashboard.seller.yourBank')}: {formatCurrency(netPayout)}
              </p>
            </div>
          </div>
        </div>
        <p className="text-2xl font-bold mb-1 text-green-600">{formatCurrency(netPayout)}</p>
        <p className="text-sm text-muted-foreground">{t('dashboard.seller.netPayout')}</p>
        <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
          <span>{t('dashboard.seller.afterCommission', { rate: formatPercent(effectiveRate * 100, 1) })}</span>
          {subscriptionTier !== 'free' && (
            <Badge className="bg-green-100 text-green-700 text-xs ml-1">
              {t(`dashboard.seller.tier${subscriptionTier.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')}`, subscriptionTier)} {t('dashboard.seller.rate')}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default function SellerDashboardWithErrorBoundary(props) {
  return (
    <ErrorBoundary scope="seller-dashboard">
      <SellerDashboard {...props} />
    </ErrorBoundary>
  );
}

// ========== Seller Ratings Panel ==========
const SellerRatingsPanel = ({ userId, token }) => {
  const [ratings, setRatings] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) return;
    const fetchRatings = async () => {
      try {
        const res = await axios.get(`${API}/users/${userId}/ratings`);
        setRatings(res.data);
      } catch (err) {
        console.error('Failed to load ratings', err);
      } finally {
        setLoading(false);
      }
    };
    fetchRatings();
  }, [userId]);

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;

  if (!ratings || ratings.total_ratings === 0) {
    return (
      <Card data-testid="ratings-empty">
        <CardContent className="py-12 text-center">
          <TrendingUp className="h-10 w-10 mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500">No ratings yet. Complete transactions to build your reputation.</p>
        </CardContent>
      </Card>
    );
  }

  const stars = [5, 4, 3, 2, 1];

  return (
    <div className="space-y-6" data-testid="ratings-panel">
      {/* Summary Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Seller Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <p className="text-4xl font-bold text-amber-500">{ratings.average_rating}</p>
              <div className="flex gap-0.5 mt-1">
                {[1,2,3,4,5].map(s => (
                  <span key={s} className={`text-lg ${s <= Math.round(ratings.average_rating) ? 'text-amber-400' : 'text-slate-200'}`}>&#9733;</span>
                ))}
              </div>
              <p className="text-sm text-muted-foreground mt-1">{ratings.total_ratings} reviews</p>
            </div>
            <div className="flex-1 space-y-1.5">
              {stars.map(star => {
                const count = ratings.ratings_breakdown?.[String(star)] || 0;
                const pct = ratings.total_ratings > 0 ? (count / ratings.total_ratings) * 100 : 0;
                return (
                  <div key={star} className="flex items-center gap-2 text-sm">
                    <span className="w-8 text-right text-muted-foreground">{star}&#9733;</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-amber-400 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-8 text-xs text-muted-foreground">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Individual Reviews */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Reviews</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(ratings.recent_ratings || []).map((review, idx) => (
            <div key={idx} className="border-b border-slate-100 pb-4 last:border-0">
              <div className="flex items-center justify-between mb-1">
                <div className="flex gap-0.5">
                  {[1,2,3,4,5].map(s => (
                    <span key={s} className={`text-sm ${s <= review.rating ? 'text-amber-400' : 'text-slate-200'}`}>&#9733;</span>
                  ))}
                </div>
                <span className="text-xs text-muted-foreground">
                  {review.timestamp ? new Date(review.timestamp).toLocaleDateString() : ''}
                </span>
              </div>
              {review.comment && <p className="text-sm text-slate-600">{review.comment}</p>}
              <p className="text-xs text-muted-foreground mt-1">
                Auction: {review.auction_id?.slice(0, 8)}... ({review.auction_type})
              </p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
};


const RegionalTrendsPanel = ({ token }) => {
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrends = async () => {
      try {
        const res = await axios.get(`${API}/insights/regional-trends`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setTrends(res.data);
      } catch {
        setTrends({ top_categories: [], top_regions: [], insights: [] });
      } finally {
        setLoading(false);
      }
    };
    if (token) fetchTrends();
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-cyan-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 py-6" data-testid="regional-trends-panel">
      {/* Insights Cards */}
      {trends?.insights?.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold flex items-center gap-2 text-slate-900 dark:text-white">
            <Zap className="h-5 w-5 text-amber-500" /> Key Insights
          </h3>
          {trends.insights.map((insight, idx) => (
            <Card key={idx} className="border-l-4 border-l-amber-400 bg-gradient-to-r from-amber-50/50 to-white dark:from-slate-800 dark:to-slate-800">
              <CardContent className="py-4 px-5">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-200" data-testid={`insight-message-${idx}`}>
                  {insight.message}
                </p>
                {insight.category && (
                  <Badge className="mt-2 bg-amber-100 text-amber-800 text-xs">{insight.category}</Badge>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top Categories */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-cyan-500" /> Top Performing Categories
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trends?.top_categories?.length > 0 ? (
              <div className="space-y-3">
                {trends.top_categories.map((cat, idx) => {
                  const maxCount = trends.top_categories[0]?.count || 1;
                  const pct = Math.round((cat.count / maxCount) * 100);
                  return (
                    <div key={idx} data-testid={`top-category-${idx}`}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium text-slate-700 dark:text-slate-300">{cat.category || 'General'}</span>
                        <span className="text-muted-foreground">{cat.count} views</span>
                      </div>
                      <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">No category data yet. Activity builds over time.</p>
            )}
          </CardContent>
        </Card>

        {/* Top Regions */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <MapPin className="h-4 w-4 text-emerald-500" /> Active Regions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trends?.top_regions?.length > 0 ? (
              <div className="space-y-3">
                {trends.top_regions.map((reg, idx) => {
                  const maxCount = trends.top_regions[0]?.count || 1;
                  const pct = Math.round((reg.count / maxCount) * 100);
                  return (
                    <div key={idx} data-testid={`top-region-${idx}`}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium text-slate-700 dark:text-slate-300">{reg.region || 'Unknown'}</span>
                        <span className="text-muted-foreground">{reg.count} interactions</span>
                      </div>
                      <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">No regional data yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
