import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Crown, Star, Zap, Shield, TrendingUp, Percent, Megaphone, Headphones, Check, Sparkles, RefreshCw, Store, FileSpreadsheet, BarChart3 } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

/**
 * TrendySubscriptionCards - Premium glassmorphism subscription UI
 * Features:
 * - Dynamic pricing from Admin Pricing Engine API
 * - Three distinct cards with glassmorphism effect
 * - Premium card slightly larger with glowing "Best Value" badge
 * - VIP card with dark/gold luxury theme
 * - Interactive hover effects with elevation
 */
const TrendySubscriptionCards = ({ currentTier = 'free', onUpgrade }) => {
  const { t } = useTranslation();
  const [hoveredCard, setHoveredCard] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [breakdowns, setBreakdowns] = useState({});
  const [expandedBreakdown, setExpandedBreakdown] = useState(null);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/subscription-plans`);
      if (response.data.success) {
        setPlans(response.data.plans || []);
        // Fetch price breakdowns for paid plans
        const bdMap = {};
        for (const planId of ['premium', 'partner_pro', 'vip']) {
          try {
            const bd = await axios.get(`${API}/subscriptions/price-breakdown?plan_id=${planId}`);
            bdMap[planId] = bd.data;
          } catch { /* skip */ }
        }
        setBreakdowns(bdMap);
      }
    } catch (error) {
      console.error('Error fetching plans:', error);
    } finally {
      setLoading(false);
    }
  };

  // Get plan price from API data
  const getPlanPrice = (planId) => {
    const plan = plans.find(p => p.plan_id === planId);
    return plan?.price_yearly || 0;
  };

  // Get original price for strikethrough display
  const getOriginalPrice = (planId) => {
    const plan = plans.find(p => p.plan_id === planId);
    const original = plan?.original_price_yearly || 0;
    const current = plan?.price_yearly || 0;
    return original > current ? original : null;
  };

  // Calculate savings percentage
  const getSavingsPercent = (planId) => {
    const original = getOriginalPrice(planId);
    const current = getPlanPrice(planId);
    if (!original || original <= current) return null;
    return Math.round((1 - current / original) * 100);
  };

  const formatPrice = (amount) => {
    return new Intl.NumberFormat('en-CA', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    }).format(amount || 0);
  };

  const tiers = [
    {
      id: 'free',
      name: 'Starter',
      period: 'Forever Free',
      description: 'Perfect for occasional bidders',
      icon: Zap,
      iconBg: 'bg-slate-100 dark:bg-slate-800',
      iconColor: 'text-slate-600 dark:text-slate-400',
      cardClass: 'bg-white/70 dark:bg-slate-800/70 border-slate-200 dark:border-slate-700',
      hoverClass: 'hover:bg-white/90 dark:hover:bg-slate-800/90 hover:shadow-xl hover:shadow-slate-200/50 dark:hover:shadow-slate-900/50',
      features: [
        { icon: Check, text: 'Standard Bidding', included: true },
        { icon: Check, text: 'Wishlist Access', included: true },
        { icon: Percent, text: '4% Seller / 5% Buyer Fees', included: true },
        { icon: TrendingUp, text: 'Basic Listing Visibility', included: true },
      ],
      cta: 'Current Plan',
      ctaDisabled: true,
    },
    {
      id: 'premium',
      name: 'Premium',
      period: '/year',
      description: 'For serious buyers & sellers',
      icon: Star,
      iconBg: 'bg-purple-100 dark:bg-purple-900/50',
      iconColor: 'text-purple-600 dark:text-purple-400',
      cardClass: 'bg-gradient-to-br from-purple-50/80 via-white/80 to-blue-50/80 dark:from-purple-900/30 dark:via-slate-800/80 dark:to-blue-900/30 border-purple-300 dark:border-purple-700',
      hoverClass: 'hover:shadow-2xl hover:shadow-purple-300/50 dark:hover:shadow-purple-900/50 hover:scale-[1.02] hover:border-purple-400',
      features: [
        { icon: Percent, text: '2.5% Seller / 3.5% Buyer', included: true, highlight: 'Save 1.5%' },
        { icon: Shield, text: 'Auto-Bid Bot Access', included: true },
        { icon: Megaphone, text: '3-Day Listing Promotion', included: true },
        { icon: TrendingUp, text: 'Priority Search Ranking', included: true },
        { icon: Star, text: 'Premium Seller Badge', included: true },
      ],
      cta: 'Upgrade to Premium',
      ctaClass: 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700',
    },
    {
      id: 'partner_pro',
      name: 'Partner Pro',
      period: '/year',
      description: 'Power tools for high-volume sellers',
      icon: Store,
      iconBg: 'bg-cyan-100 dark:bg-cyan-900/50',
      iconColor: 'text-cyan-600 dark:text-cyan-400',
      cardClass: 'bg-gradient-to-br from-cyan-50/80 via-white/80 to-teal-50/80 dark:from-cyan-900/30 dark:via-slate-800/80 dark:to-teal-900/30 border-cyan-300 dark:border-cyan-700',
      hoverClass: 'hover:shadow-2xl hover:shadow-cyan-300/50 dark:hover:shadow-cyan-900/50 hover:scale-[1.02] hover:border-cyan-400',
      badge: 'PRO TOOLS',
      badgeClass: 'bg-gradient-to-r from-cyan-500 to-teal-500 text-white',
      featured: true,
      features: [
        { icon: Percent, text: '25% Buyer & Seller Discount', included: true, highlight: 'Pro Rate' },
        { icon: Store, text: 'Branded Storefront Page', included: true },
        { icon: FileSpreadsheet, text: 'CSV Bulk Listing Import', included: true },
        { icon: Sparkles, text: '2h Early Auction Access', included: true },
        { icon: Megaphone, text: '10 Featured Listings/Month', included: true },
        { icon: BarChart3, text: 'Analytics Export (CSV/JSON)', included: true },
        { icon: Headphones, text: 'Priority Chat + Email Support', included: true },
      ],
      cta: 'Go Partner Pro',
      ctaClass: 'bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-700 hover:to-teal-700',
    },
    {
      id: 'vip',
      name: 'VIP Elite',
      period: '/year',
      description: 'Ultimate auction experience',
      icon: Crown,
      iconBg: 'bg-gradient-to-br from-amber-200 to-yellow-300 dark:from-amber-700 dark:to-yellow-600',
      iconColor: 'text-amber-800 dark:text-amber-100',
      cardClass: 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-amber-500/50 text-white',
      hoverClass: 'hover:shadow-2xl hover:shadow-amber-500/30 hover:scale-[1.02] hover:border-amber-400',
      darkTheme: true,
      features: [
        { icon: Percent, text: '2% Seller / 3% Buyer', included: true, highlight: 'Save 2%' },
        { icon: Shield, text: 'Auto-Bid Bot + Priority', included: true },
        { icon: Megaphone, text: '7-Day Listing Promotion', included: true },
        { icon: Sparkles, text: '24h Early Access to Auctions', included: true },
        { icon: Crown, text: 'VIP Elite Badge', included: true },
        { icon: Headphones, text: 'Dedicated Support Line', included: true },
      ],
      cta: 'Go VIP Elite',
      ctaClass: 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-black font-bold',
    },
  ];

  const [upgrading, setUpgrading] = useState(null);
  const [trialStatus, setTrialStatus] = useState(null);
  const [startingTrial, setStartingTrial] = useState(false);

  // Fetch trial status on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.get(`${API}/partner-pro/trial/status`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => setTrialStatus(r.data))
        .catch(() => {});
    }
  }, []);

  const handleStartTrial = async () => {
    const token = localStorage.getItem('token');
    if (!token) { toast.error('Please log in first'); return; }
    setStartingTrial(true);
    try {
      const { data } = await axios.post(`${API}/partner-pro/trial/start`, {}, { headers: { Authorization: `Bearer ${token}` } });
      if (data.success) {
        toast.success(data.message);
        window.location.reload();
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not start trial');
    } finally {
      setStartingTrial(false);
    }
  };

  const handleUpgrade = async (tierId) => {
    if (tierId === 'free') return;
    
    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Please log in to subscribe');
      return;
    }

    setUpgrading(tierId);
    try {
      const response = await axios.post(
        `${API}/subscriptions/create`,
        { plan_id: tierId },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.data.success) {
        toast.success(`Successfully subscribed to ${tierId.charAt(0).toUpperCase() + tierId.slice(1)}!`);
        if (onUpgrade) onUpgrade(tierId);
        window.location.reload();
      }
    } catch (error) {
      const detail = error?.response?.data?.detail || 'Subscription failed';
      toast.error(detail);
    } finally {
      setUpgrading(null);
    }
  };

  if (loading) {
    return (
      <div className="w-full py-8 flex items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="w-full py-8" data-testid="trendy-subscription-cards">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 lg:gap-8">
        {tiers.map((tier) => {
          const isCurrentTier = currentTier === tier.id;
          const Icon = tier.icon;
          const price = getPlanPrice(tier.id);
          const originalPrice = getOriginalPrice(tier.id);
          const savingsPercent = getSavingsPercent(tier.id);
          
          return (
            <div
              key={tier.id}
              className={`relative rounded-2xl p-6 lg:p-8 border-2 backdrop-blur-xl transition-all duration-500 ease-out ${tier.cardClass} ${tier.hoverClass} ${tier.featured ? 'md:-mt-4 md:mb-4' : ''} ${hoveredCard === tier.id ? 'z-10' : 'z-0'}`}
              onMouseEnter={() => setHoveredCard(tier.id)}
              onMouseLeave={() => setHoveredCard(null)}
              data-testid={`subscription-card-${tier.id}`}
            >
              {/* Badge */}
              {tier.badge && !isCurrentTier && (
                <div className={`absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full text-xs font-bold tracking-wide shadow-lg ${tier.badgeClass}`}>
                  {tier.badge}
                </div>
              )}

              {/* Current Plan Indicator */}
              {isCurrentTier && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-green-500 text-white text-xs font-semibold rounded-full shadow-md">
                  CURRENT PLAN
                </div>
              )}

              {/* Header */}
              <div className="text-center mb-6">
                <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center ${tier.iconBg} shadow-lg`}>
                  <Icon className={`h-8 w-8 ${tier.iconColor}`} />
                </div>
                <h3 className={`text-2xl font-bold mb-1 ${tier.darkTheme ? 'text-white' : 'text-slate-900 dark:text-white'}`}>
                  {tier.name}
                </h3>
                <p className={`text-sm ${tier.darkTheme ? 'text-slate-300' : 'text-slate-600 dark:text-slate-400'}`}>
                  {tier.description}
                </p>
              </div>

              {/* Pricing - Dynamic from API */}
              <div className="text-center mb-6">
                {/* Original Price Strikethrough */}
                {originalPrice && (
                  <div className="mb-1">
                    <span className={`text-lg line-through decoration-red-500/60 decoration-2 ${tier.darkTheme ? 'text-slate-500' : 'text-slate-400'}`}>
                      ${formatPrice(originalPrice)}
                    </span>
                    {savingsPercent && (
                      <span className="ml-2 text-xs px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full font-semibold">
                        {savingsPercent}% OFF
                      </span>
                    )}
                  </div>
                )}
                <div className="flex items-end justify-center gap-1">
                  <span className={`text-4xl lg:text-5xl font-bold ${tier.darkTheme ? 'text-white' : 'text-slate-900 dark:text-white'}`} data-testid={`price-${tier.id}`}>
                    ${formatPrice(price)}
                  </span>
                  <span className={`text-sm mb-2 ${tier.darkTheme ? 'text-slate-400' : 'text-slate-500 dark:text-slate-400'}`}>
                    {tier.period}
                  </span>
                </div>
                {/* Promo badge - show savings amount if original exists */}
                {originalPrice ? (
                  <span className="inline-block mt-2 px-3 py-1 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full">
                    Save ${formatPrice(originalPrice - price)}!
                  </span>
                ) : tier.id !== 'free' && (
                  <span className="inline-block mt-2 px-3 py-1 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full">
                    2 Months Free!
                  </span>
                )}

                {/* Price Breakdown Toggle */}
                {tier.id !== 'free' && breakdowns[tier.id] && (
                  <div className="mt-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); setExpandedBreakdown(expandedBreakdown === tier.id ? null : tier.id); }}
                      className={`text-xs font-medium underline underline-offset-2 transition-colors ${
                        tier.darkTheme ? 'text-amber-400/80 hover:text-amber-300' : 'text-blue-600 dark:text-blue-400 hover:text-blue-700'
                      }`}
                      data-testid={`price-breakdown-toggle-${tier.id}`}
                    >
                      {expandedBreakdown === tier.id ? 'Hide' : 'View'} price breakdown
                    </button>
                    {expandedBreakdown === tier.id && (
                      <div className={`mt-2 mx-auto max-w-[240px] text-left rounded-lg p-3 text-xs space-y-1.5 ${
                        tier.darkTheme 
                          ? 'bg-white/10 text-slate-300 border border-white/10' 
                          : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                      }`} data-testid={`price-breakdown-${tier.id}`}>
                        <div className="flex justify-between">
                          <span>{t("subscription.subtotal")}</span>
                          <span className="font-medium">${formatPrice(breakdowns[tier.id].subtotal)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>GST (5%)</span>
                          <span className="font-medium">${formatPrice(breakdowns[tier.id].gst)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>QST (9.975%)</span>
                          <span className="font-medium">${formatPrice(breakdowns[tier.id].qst)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>{t("subscription.processingFee")}</span>
                          <span className="font-medium">${formatPrice(breakdowns[tier.id].processing_fee)}</span>
                        </div>
                        <div className={`flex justify-between pt-1.5 border-t font-semibold ${
                          tier.darkTheme ? 'border-white/20 text-white' : 'border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white'
                        }`}>
                          <span>Total</span>
                          <span>${formatPrice(breakdowns[tier.id].total)} CAD</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-8">
                {tier.features.map((feature, idx) => {
                  const FeatureIcon = feature.icon;
                  return (
                    <li key={idx} className="flex items-start gap-3">
                      <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
                        tier.darkTheme 
                          ? 'bg-amber-500/20' 
                          : tier.id === 'premium' ? 'bg-purple-100 dark:bg-purple-900/50' 
                          : tier.id === 'partner_pro' ? 'bg-cyan-100 dark:bg-cyan-900/50'
                          : 'bg-slate-100 dark:bg-slate-800'
                      }`}>
                        <FeatureIcon className={`h-3.5 w-3.5 ${
                          tier.darkTheme 
                            ? 'text-amber-400' 
                            : tier.id === 'premium' ? 'text-purple-600 dark:text-purple-400' 
                            : tier.id === 'partner_pro' ? 'text-cyan-600 dark:text-cyan-400'
                            : 'text-green-600 dark:text-green-400'
                        }`} />
                      </div>
                      <div className="flex-1">
                        <span className={`text-sm font-medium ${tier.darkTheme ? 'text-white' : 'text-slate-900 dark:text-white'}`}>
                          {feature.text}
                        </span>
                        {feature.highlight && (
                          <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                            tier.darkTheme 
                              ? 'bg-green-500/20 text-green-400' 
                              : 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400'
                          }`}>
                            {feature.highlight}
                          </span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>

              {/* CTA Button */}
              <Button
                className={`w-full py-6 text-base font-semibold rounded-xl transition-all duration-300 ${
                  tier.ctaClass || (isCurrentTier 
                    ? 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 cursor-default' 
                    : 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100'
                  )
                }`}
                onClick={() => !isCurrentTier && handleUpgrade(tier.id)}
                disabled={isCurrentTier || tier.ctaDisabled || upgrading === tier.id}
                data-testid={`upgrade-btn-${tier.id}`}
              >
                {upgrading === tier.id ? (
                  <><RefreshCw className="h-4 w-4 animate-spin mr-2" /> Processing...</>
                ) : isCurrentTier ? 'Current Plan' : tier.cta}
              </Button>

              {/* Terms of Sale */}
              {!isCurrentTier && tier.id !== 'free' && (
                <div className="mt-3 space-y-2">
                  <p className={`text-[11px] leading-relaxed text-center ${tier.darkTheme ? 'text-slate-500' : 'text-slate-400 dark:text-slate-500'}`}>
                    By purchasing, you agree that all payments are final and non-refundable. If you cancel, access continues until the end of your billing cycle.
                  </p>
                </div>
              )}

              {/* Free Trial CTA — Partner Pro only */}
              {tier.id === 'partner_pro' && !isCurrentTier && trialStatus?.eligible_for_trial && (
                <div className="mt-3 text-center">
                  <button
                    onClick={handleStartTrial}
                    disabled={startingTrial}
                    className="text-sm font-semibold text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 underline underline-offset-2 transition-colors"
                    data-testid="start-trial-btn"
                  >
                    {startingTrial ? 'Starting...' : 'Try free for 14 days — no credit card needed'}
                  </button>
                </div>
              )}
              {tier.id === 'partner_pro' && trialStatus?.is_trialing && (
                <div className="mt-3 text-center">
                  <span className="text-xs font-medium px-3 py-1 rounded-full bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300" data-testid="trial-active-badge">
                    Trial active — {trialStatus.days_remaining} days left
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TrendySubscriptionCards;
