import React, { useState, useEffect } from 'react';
import { Crown, Star, Zap, Shield, TrendingUp, Percent, Megaphone, Headphones, Check, Sparkles } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

/**
 * TrendySubscriptionCards - Premium glassmorphism subscription UI
 * Features:
 * - Three distinct cards with glassmorphism effect
 * - Premium card slightly larger with glowing "Best Value" badge
 * - VIP card with dark/gold luxury theme
 * - Interactive hover effects with elevation
 * - Professional SVG icons for features
 */
const TrendySubscriptionCards = ({ currentTier = 'free', onUpgrade }) => {
  const [hoveredCard, setHoveredCard] = useState(null);

  const tiers = [
    {
      id: 'free',
      name: 'Starter',
      price: 0,
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
      price: 99.99,
      period: '/year',
      promo: '2 Months Free!',
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
      price: 299.99,
      period: '/year',
      promo: '2 Months Free!',
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

  const handleUpgrade = (tierId) => {
    if (onUpgrade) {
      onUpgrade(tierId);
    } else {
      toast.info('Stripe integration coming soon!');
    }
  };

  return (
    <div className="w-full py-8" data-testid="trendy-subscription-cards">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
        {tiers.map((tier) => {
          const isCurrentTier = currentTier === tier.id;
          const Icon = tier.icon;
          
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

              {/* Pricing */}
              <div className="text-center mb-6">
                <div className="flex items-end justify-center gap-1">
                  <span className={`text-4xl lg:text-5xl font-bold ${tier.darkTheme ? 'text-white' : 'text-slate-900 dark:text-white'}`}>
                    ${tier.price}
                  </span>
                  <span className={`text-sm mb-2 ${tier.darkTheme ? 'text-slate-400' : 'text-slate-500 dark:text-slate-400'}`}>
                    {tier.period}
                  </span>
                </div>
                {tier.promo && (
                  <span className="inline-block mt-2 px-3 py-1 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full">
                    {tier.promo}
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
                disabled={isCurrentTier || tier.ctaDisabled}
                data-testid={`upgrade-btn-${tier.id}`}
              >
                {isCurrentTier ? 'Current Plan' : tier.cta}
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TrendySubscriptionCards;
