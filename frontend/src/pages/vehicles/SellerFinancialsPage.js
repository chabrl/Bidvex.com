import API_BASE from '../../config';
/**
 * Seller Financials Dashboard
 * Shows commission rates, pending payouts, and settlement history
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { useTranslation } from 'react-i18next';
import {
  DollarSign, TrendingUp, Clock, CheckCircle, AlertTriangle,
  ChevronLeft, Percent, Crown, Sparkles, ArrowUpRight,
  Calendar, Building2, CreditCard, FileText, Info
} from 'lucide-react';

const API = API_BASE;

const formatPrice = (amount) => {
  const { t } = useTranslation();
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(amount || 0);
};

const formatDate = (date) => {
  return new Date(date).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

// Tier info component
const TierInfoCard = ({ tier, commissionRate, savings }) => {
  const tierConfig = {
    basic: {
      name: 'Basic',
      icon: null,
      color: 'bg-slate-100 text-slate-700',
      description: 'Standard seller account'
    },
    premium: {
      name: 'Premium',
      icon: Sparkles,
      color: 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white',
      description: '1.5% commission discount'
    },
    vip_elite: {
      name: 'VIP Elite',
      icon: Crown,
      color: 'bg-gradient-to-r from-purple-500 to-pink-500 text-white',
      description: '2% commission discount'
    }
  };

  const config = tierConfig[tier] || tierConfig.basic;
  const Icon = config.icon;

  return (
    <Card className="overflow-hidden">
      <div className={`p-6 ${config.color}`}>
        <div className="flex items-center gap-3 mb-4">
          {Icon && <Icon className="h-8 w-8" />}
          <div>
            <h3 className="text-xl font-bold">{config.name} Seller</h3>
            <p className="text-sm opacity-90">{config.description}</p>
          </div>
        </div>
      </div>
      <CardContent className="p-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
            <Percent className="h-6 w-6 mx-auto text-blue-600 mb-2" />
            <p className="text-2xl font-bold text-blue-600">{commissionRate}</p>
            <p className="text-sm text-slate-500">Commission Rate</p>
          </div>
          <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <TrendingUp className="h-6 w-6 mx-auto text-green-600 mb-2" />
            <p className="text-2xl font-bold text-green-600">{savings}</p>
            <p className="text-sm text-slate-500">Savings vs Basic</p>
          </div>
        </div>
        
        {tier !== 'vip_elite' && (
          <Button className="w-full mt-4" variant="outline">
            <ArrowUpRight className="h-4 w-4 mr-2" />
            Upgrade to Save More
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

// Settlement item component
const SettlementItem = ({ settlement }) => {
  const statusConfig = {
    pending_buyer_payment: { color: 'bg-amber-100 text-amber-700', icon: Clock, label: 'Awaiting Buyer Payment' },
    ready: { color: 'bg-blue-100 text-blue-700', icon: CheckCircle, label: 'Ready for Settlement' },
    completed: { color: 'bg-green-100 text-green-700', icon: CheckCircle, label: 'Completed' }
  };

  const status = statusConfig[settlement.settlement_status] || statusConfig.pending_buyer_payment;
  const StatusIcon = status.icon;

  return (
    <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
      <div className="flex-1">
        <p className="font-medium text-slate-900 dark:text-white">
          {settlement.vehicle_title}
        </p>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-sm text-slate-500">
            {formatDate(settlement.created_at)}
          </span>
          <Badge className={status.color}>
            <StatusIcon className="h-3 w-3 mr-1" />
            {status.label}
          </Badge>
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold text-green-600">
          {formatPrice(settlement.net_payout)}
        </p>
        <p className="text-xs text-slate-500">
          Commission: {formatPrice(settlement.seller_commission)}
        </p>
      </div>
    </div>
  );
};

// Main seller financials page
const SellerFinancialsPage = () => {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [financials, setFinancials] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      navigate('/auth');
      return;
    }

    const fetchFinancials = async () => {
      try {
        const response = await axios.get(`${API}/vehicle-sellers/me/financials`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setFinancials(response.data);
      } catch (error) {
        console.error('Failed to fetch financials:', error);
        if (error.response?.status === 403) {
          navigate('/vehicle-auctions/seller/register');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchFinancials();
  }, [user, token, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!financials) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <Card className="text-center p-8">
          <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Seller Account Required</h2>
          <p className="text-slate-500 mb-4">
            You need to register as a vehicle seller to view financials.
          </p>
          <Button onClick={() => navigate('/vehicle-auctions/seller/register')}>
            Register as Seller
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="seller-financials-page">
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <Button 
            variant="ghost" 
            onClick={() => navigate('/vehicle-auctions/my-listings')}
            className="mb-4"
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to My Listings
          </Button>
          
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <DollarSign className="h-8 w-8 text-green-600" />
            Seller Financials
          </h1>
          <p className="text-slate-500 mt-1">
            Your commission rates, payouts, and settlement history
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left Column - Tier & Stats */}
          <div className="space-y-6">
            {/* Tier Info */}
            <TierInfoCard 
              tier={financials.subscription_tier}
              commissionRate={financials.commission_rate}
              savings={financials.commission_savings}
            />

            {/* Quick Stats */}
            <Card>
              <CardHeader>
                <CardTitle>{t("seller.financialOverview")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-amber-600" />
                    <span className="text-sm font-medium">Pending Payout</span>
                  </div>
                  <span className="font-bold text-amber-600">
                    {formatPrice(financials.financials?.pending_payout)}
                  </span>
                </div>

                <div className="flex justify-between items-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-green-600" />
                    <span className="text-sm font-medium">Total Earned</span>
                  </div>
                  <span className="font-bold text-green-600">
                    {formatPrice(financials.financials?.total_earned)}
                  </span>
                </div>

                <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Percent className="h-5 w-5 text-slate-600" />
                    <span className="text-sm font-medium">Commission Paid</span>
                  </div>
                  <span className="font-bold text-slate-600">
                    {formatPrice(financials.financials?.total_commission_paid)}
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Fee Structure Info */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="h-5 w-5" />
                  Fee Structure
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Basic Seller</span>
                  <span className="font-medium">4.0% commission</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Premium Seller</span>
                  <span className="font-medium text-blue-600">2.5% commission</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">VIP Elite Seller</span>
                  <span className="font-medium text-purple-600">2.0% commission</span>
                </div>
                <hr className="my-2" />
                <p className="text-xs text-slate-500">
                  Settlement deadline: 14 days after buyer payment
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Settlements */}
          <div className="lg:col-span-2 space-y-6">
            {/* Pending Settlements */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-amber-600" />
                    Pending Settlements
                  </span>
                  <Badge variant="secondary">
                    {financials.pending_settlements?.length || 0}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {financials.pending_settlements?.length > 0 ? (
                  <div className="space-y-3">
                    {financials.pending_settlements.map((settlement) => (
                      <SettlementItem key={settlement.id} settlement={settlement} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">
                    <CheckCircle className="h-12 w-12 mx-auto mb-2 text-green-500" />
                    <p>No pending settlements</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Recent Completed Settlements */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  Recent Completed Settlements
                </CardTitle>
              </CardHeader>
              <CardContent>
                {financials.recent_settlements?.length > 0 ? (
                  <div className="space-y-3">
                    {financials.recent_settlements.map((settlement) => (
                      <SettlementItem key={settlement.id} settlement={settlement} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">
                    <FileText className="h-12 w-12 mx-auto mb-2 text-slate-300" />
                    <p>No completed settlements yet</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SellerFinancialsPage;
