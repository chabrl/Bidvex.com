import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Crown, Star, Zap, Shield, TrendingUp, Percent, Megaphone, Headphones, Check, Sparkles, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
  const [hoveredCard, setHoveredCard] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/subscription-plans`);
      if (response.data.success) {
        setPlans(response.data.plans || []);
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
      badge: 'BEST VALUE',
      badgeClass: 'bg-gradient-to-r from-amber-400 to-orange-500 text-black animate-pulse',
      featured: true,
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
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
              {tier.badge && (
                <div className={`absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full text-xs font-bold tracking-wide shadow-lg ${tier.badgeClass}`}>
                  {tier.badge}
                </div>
              )}

              {/* Current Plan Indicator */}
              {isCurrentTier && (
                <div className="absolute -top-3 right-4 px-3 py-1 bg-green-500 text-white text-xs font-semibold rounded-full shadow-md">
                  CURRENT
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
                          : tier.id === 'premium' ? 'bg-purple-100 dark:bg-purple-900/50' : 'bg-slate-100 dark:bg-slate-800'
                      }`}>
                        <FeatureIcon className={`h-3.5 w-3.5 ${
                          tier.darkTheme 
                            ? 'text-amber-400' 
                            : tier.id === 'premium' ? 'text-purple-600 dark:text-purple-400' : 'text-green-600 dark:text-green-400'
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
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TrendySubscriptionCards;
