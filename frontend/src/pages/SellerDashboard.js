import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Plus, DollarSign, Package, FileText, ShoppingBag, Heart, Eye, TrendingUp, BarChart3, Wallet, Info, AlertTriangle, Clock, Shield } from 'lucide-react';
import { toast } from 'sonner';
import SellerAnalyticsDashboard from '../components/SellerAnalyticsDashboard';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SellerDashboard = () => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const { canCreateMultiLot } = useFeatureFlags();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('listings'); // 'listings' or 'analytics'
  const [deletionRequestModal, setDeletionRequestModal] = useState({ open: false, listing: null, isMultiItem: false });
  const [deletionReason, setDeletionReason] = useState('');

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/seller`);
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
    
    try {
      const { listing, isMultiItem } = deletionRequestModal;
      const endpoint = isMultiItem ? 'multi-item-listings' : 'listings';
      
      await axios.post(`${API}/${endpoint}/${listing.id}/request-deletion`, {
        reason: deletionReason
      });
      
      toast.success(t('dashboard.seller.deletionRequestSubmitted', 'Deletion request submitted. Admin will review shortly.'));
      setDeletionRequestModal({ open: false, listing: null, isMultiItem: false });
      setDeletionReason('');
      fetchDashboard();
    } catch (error) {
      toast.error(t('dashboard.seller.deletionRequestFailed', 'Failed to submit deletion request'));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="seller-dashboard">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">{t('dashboard.seller.title')}</h1>
            <p className="text-sm text-muted-foreground">
              {user.account_type === 'business' ? t('dashboard.seller.businessAccount') : t('dashboard.seller.personalAccount')} - 
              {t('dashboard.seller.commissionRate')}: {user.subscription_tier === 'vip' ? '2%' : user.subscription_tier === 'premium' ? '2.5%' : '4%'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              className="gradient-button text-white border-0"
              onClick={() => navigate('/create-listing')}
              data-testid="create-listing-btn"
            >
              <Plus className="mr-2 h-4 w-4" />
              {t('dashboard.seller.createListing')}
            </Button>
            {canCreateMultiLot(user) && (
              <Button
                variant="outline"
                onClick={() => navigate('/create-multi-item-listing')}
                data-testid="create-lot-btn"
              >
                <Package className="mr-2 h-4 w-4" />
                {t('dashboard.seller.createLot', 'Create Lot')}
              </Button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 dark:border-slate-700">
          <button
            onClick={() => setActiveTab('listings')}
            className={`px-6 py-3 font-medium text-sm transition-colors border-b-2 -mb-px ${
              activeTab === 'listings'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <Package className="h-4 w-4 inline mr-2" />
            {t('dashboard.seller.listings', 'Listings')}
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-6 py-3 font-medium text-sm transition-colors border-b-2 -mb-px ${
              activeTab === 'analytics'
                ? 'border-[#06B6D4] text-[#06B6D4]'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <BarChart3 className="h-4 w-4 inline mr-2" />
            {t('dashboard.seller.analytics', 'Analytics')}
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'analytics' ? (
          <SellerAnalyticsDashboard />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          <StatCard
            icon={<Package className="h-6 w-6" />}
            title={t('dashboard.seller.activeListings')}
            value={dashboard?.active_listings || 0}
            color="blue"
          />
          <StatCard
            icon={<ShoppingBag className="h-6 w-6" />}
            title={t('dashboard.seller.soldItems')}
            value={dashboard?.sold_listings || 0}
            color="green"
          />
          <StatCard
            icon={<FileText className="h-6 w-6" />}
            title={t('dashboard.seller.draftListings')}
            value={dashboard?.draft_listings || 0}
            color="orange"
          />
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title={t('dashboard.seller.totalSales')}
            value={`$${dashboard?.total_sales?.toFixed(2) || '0.00'}`}
            color="purple"
          />
          {/* Net Payout Card - Shows what seller will receive after commission */}
          <NetPayoutCard 
            totalSales={dashboard?.total_sales || 0}
            subscriptionTier={user?.subscription_tier || 'free'}
          />
        </div>

        {/* Fee Structure & 14-Day Payment Rule Info */}
        <Card className="border-2 border-blue-200 dark:border-blue-700 bg-gradient-to-r from-blue-50 to-slate-50 dark:from-blue-900/20 dark:to-slate-800/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2 text-blue-800 dark:text-blue-300">
              <Shield className="h-5 w-5" />
              Fee Structure & Payment Rules
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
                  {user?.subscription_tier === 'vip' ? '2%' : user?.subscription_tier === 'premium' ? '2.5%' : '4%'}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {user?.subscription_tier === 'vip' 
                    ? '✨ VIP discount (2% savings)!' 
                    : user?.subscription_tier === 'premium'
                    ? '✨ Premium discount (1.5% savings)!'
                    : 'Standard rate (Upgrade for savings!)'}
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
                  {t('fees.settlement', 'Fees must be settled after auction close')}
                </p>
              </div>

              {/* Late Payment Warning */}
              <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-300 dark:border-amber-700">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  <span className="font-semibold text-amber-800 dark:text-amber-300">{t('dashboard.seller.latePenalty')}</span>
                </div>
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">2%/month</p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  Interest on overdue balances
                </p>
              </div>
            </div>
            
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-4 text-center">
              <a href="/terms" className="text-blue-600 dark:text-blue-400 hover:underline">
                View complete Terms & Conditions →
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
                            <p className="text-xs text-muted-foreground">{itemCount} lots</p>
                          )}
                        </div>
                        <Badge variant={listing.status === 'active' ? 'default' : 'secondary'}>
                          {listing.status}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm mb-2">
                        <span className="text-green-600 font-semibold">
                          <DollarSign className="h-3 w-3 inline mr-1" />
                          ${displayPrice.toFixed(2)}
                        </span>
                        <span className="text-blue-600">
                          <TrendingUp className="h-3 w-3 inline mr-1" />
                          {totalBids} bids
                        </span>
                        <span className="text-gray-600">
                          <Eye className="h-3 w-3 inline mr-1" />
                          {listing.views} views
                        </span>
                        <span className="text-red-600">
                          <Heart className="h-3 w-3 inline mr-1 fill-current" />
                          {listing.wishlist_count || 0} wishlisted
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(isMultiItem ? `/lots/${listing.id}` : `/listing/${listing.id}`)}
                        >
                          View
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteListing(listing.id, isMultiItem)}
                          data-testid={`delete-listing-${listing.id}`}
                        >
                          {t('dashboard.seller.requestDeletion', 'Request Deletion')}
                        </Button>
                      </div>
                    </div>
                  </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12">
                <Package className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No listings yet</p>
                <Button onClick={() => navigate('/create-listing')} className="gradient-button text-white border-0">
                  Create Your First Listing
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
                  {deletionReason.length}/20 characters minimum
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
                  disabled={deletionReason.trim().length < 20}
                >
                  {t('dashboard.seller.submitRequest', 'Submit Request')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

const StatCard = ({ icon, title, value, color }) => (
  <Card className="glassmorphism">
    <CardContent className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold mb-1">{value}</p>
      <p className="text-sm text-muted-foreground">{title}</p>
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
const NetPayoutCard = ({ totalSales = 0, subscriptionTier = 'free' }) => {
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
              <p className="font-semibold mb-1">Net Payout Calculation</p>
              <p>Total Sales: ${totalSales.toFixed(2)}</p>
              <p>Commission ({(effectiveRate * 100).toFixed(1)}%): -${commissionAmount.toFixed(2)}</p>
              <p className="border-t border-gray-700 mt-1 pt-1 font-semibold">
                Your Bank: ${netPayout.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
        <p className="text-2xl font-bold mb-1 text-green-600">${netPayout.toFixed(2)}</p>
        <p className="text-sm text-muted-foreground">Net Payout</p>
        <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
          <span>After {(effectiveRate * 100).toFixed(1)}% commission</span>
          {subscriptionTier !== 'free' && (
            <Badge className="bg-green-100 text-green-700 text-xs ml-1">
              {subscriptionTier} rate
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default SellerDashboard;
