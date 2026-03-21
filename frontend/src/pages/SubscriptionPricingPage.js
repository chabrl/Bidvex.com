/**
 * SubscriptionPricingPage - Public pricing page with checkout
 * Features: Plan comparison, coupon code input, Stripe checkout
 * Enhanced: Dynamic pricing from Admin Pricing Engine, Launch Special badges, savings calculator
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { 
  Crown, Star, User as UserIcon, Check, X, Zap, ArrowRight,
  Ticket, RefreshCw, Percent, DollarSign, Sparkles, Shield,
  Gift, TrendingDown, PartyPopper, AlertCircle
} from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
import { useTranslation } from 'react-i18next';

// Plan icons and styling
const PLAN_STYLES = {
  free: { 
    icon: UserIcon, 
    gradient: 'from-slate-500 to-slate-600',
    border: 'border-slate-200 dark:border-slate-700',
    badge: null,
    launchBadge: false
  },
  premium: { 
    icon: Star, 
    gradient: 'from-purple-500 to-indigo-600',
    border: 'border-purple-300 dark:border-purple-700',
    badge: null,
    launchBadge: true,
    launchBadgeColor: 'from-blue-500 to-cyan-500'
  },
  partner_pro: {
    icon: Shield,
    gradient: 'from-blue-500 to-emerald-600',
    border: 'border-blue-300 dark:border-blue-700',
    badge: null,
    launchBadge: true,
    launchBadgeColor: 'from-blue-500 to-emerald-500'
  },
  vip: { 
    icon: Crown, 
    gradient: 'from-amber-500 to-orange-600',
    border: 'border-amber-300 dark:border-amber-700',
    badge: null,
    launchBadge: true,
    launchBadgeColor: 'from-amber-400 to-yellow-500'
  }
};

const SubscriptionPricingPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isYearly, setIsYearly] = useState(true);
  
  // Checkout state
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [couponCode, setCouponCode] = useState('');
  const [couponValidation, setCouponValidation] = useState(null);
  const [validatingCoupon, setValidatingCoupon] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  const isLoggedIn = !!localStorage.getItem('token');

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/subscription-plans`);
      if (response.data.success) {
        // Sort plans: free, premium, vip
        const sortOrder = ['free', 'premium', 'partner_pro', 'vip'];
        const sorted = (response.data.plans || []).sort(
          (a, b) => sortOrder.indexOf(a.plan_id) - sortOrder.indexOf(b.plan_id)
        );
        setPlans(sorted);
      }
    } catch (error) {
      console.error('Error fetching plans:', error);
      toast.error('Failed to load pricing');
    } finally {
      setLoading(false);
    }
  };

  const validateCoupon = async () => {
    if (!couponCode.trim()) {
      toast.error('Please enter a coupon code');
      return;
    }
    if (!selectedPlan) {
      toast.error('Please select a plan first');
      return;
    }

    setValidatingCoupon(true);
    try {
      const response = await axios.post(`${API}/validate-coupon`, {
        code: couponCode.trim(),
        plan_id: selectedPlan.plan_id,
        billing_period: isYearly ? 'yearly' : 'monthly'
      });

      if (response.data.valid) {
        setCouponValidation(response.data);
        toast.success(response.data.message);
      } else {
        setCouponValidation(null);
        toast.error(response.data.message || 'Invalid coupon');
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to validate coupon';
      toast.error(message);
      setCouponValidation(null);
    } finally {
      setValidatingCoupon(false);
    }
  };

  const removeCoupon = () => {
    setCouponCode('');
    setCouponValidation(null);
  };

  const handleCheckout = async (plan) => {
    if (!isLoggedIn) {
      toast.error('Please log in to subscribe');
      navigate('/auth?redirect=/pricing');
      return;
    }

    if (plan.plan_id === 'free') {
      toast.info('Free plan is already available to all users');
      return;
    }

    setCheckoutLoading(true);
    try {
      const response = await axios.post(
        `${API}/subscriptions/create`,
        {
          plan_id: plan.plan_id
        },
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`
          }
        }
      );

      if (response.data.success) {
        toast.success(`Successfully subscribed to ${plan.name}!`);
        navigate('/settings');
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Subscription failed';
      toast.error(message);
    } finally {
      setCheckoutLoading(false);
    }
  };

  const getPrice = (plan) => {
    return isYearly ? plan.price_yearly : plan.price_monthly;
  };

  // Get original/full price from dynamic API data (not hardcoded)
  const getFullPrice = (plan) => {
    if (!plan) return null;
    const originalPrice = isYearly 
      ? plan.original_price_yearly 
      : plan.original_price_monthly;
    // Only return if original price is set and greater than current price
    const currentPrice = getPrice(plan);
    if (originalPrice && originalPrice > currentPrice) {
      return originalPrice;
    }
    return null;
  };

  // Calculate discount percentage dynamically from API data
  const getDiscountPercent = (plan) => {
    if (!plan) return 0;
    const fullPrice = getFullPrice(plan);
    const currentPrice = getPrice(plan);
    if (!fullPrice || fullPrice <= currentPrice) return 0;
    return Math.round((1 - currentPrice / fullPrice) * 100);
  };

  // Calculate yearly savings vs monthly (for the billing toggle badge)
  const getYearlySavingsPercent = (plan) => {
    if (!plan || plan.price_monthly <= 0) return 0;
    const yearlyEquivalent = plan.price_monthly * 12;
    if (yearlyEquivalent <= plan.price_yearly) return 0;
    return Math.round((1 - plan.price_yearly / yearlyEquivalent) * 100);
  };

  // Check if Stripe is configured for checkout
  const isStripeConfigured = (plan) => {
    if (isYearly) {
      return !!plan.stripe_price_id_yearly;
    }
    return !!plan.stripe_price_id_monthly;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900" data-testid="pricing-page">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLDAsMCwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] dark:bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')]" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="absolute top-20 right-1/4 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl" />
        
        <div className="relative container mx-auto px-4 py-16 text-center">
          {/* Launch Offer Banner */}
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-2 bg-gradient-to-r from-amber-500/10 to-orange-500/10 dark:from-amber-500/20 dark:to-orange-500/20 border border-amber-500/30 rounded-full">
            <Gift className="h-4 w-4 text-amber-500" />
            <span className="text-sm font-medium text-amber-700 dark:text-amber-400" dangerouslySetInnerHTML={{ __html: t('pricingPage.launchBanner') }} />
            <PartyPopper className="h-4 w-4 text-amber-500" />
          </div>

          <Badge className="mb-4 bg-primary/10 text-primary border-primary/20">
            <Sparkles className="h-3 w-3 mr-1" />
            {t('pricingPage.title')}
          </Badge>
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-4">
            {t('pricingPage.subtitle')}
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto mb-8">
            Unlock premium features, lower fees, and exclusive benefits with our membership plans
          </p>
          
          {/* Billing Toggle */}
          <div className="flex items-center justify-center gap-4">
            <span className={`text-sm font-medium ${!isYearly ? 'text-primary' : 'text-slate-500'}`}>
              {t('pricingPage.monthly')}
            </span>
            <Switch
              checked={isYearly}
              onCheckedChange={setIsYearly}
              className="data-[state=checked]:bg-primary"
              data-testid="billing-toggle"
            />
            <span className={`text-sm font-medium ${isYearly ? 'text-primary' : 'text-slate-500'}`}>
              {t('pricingPage.yearly')}
            </span>
            {isYearly && plans.length > 0 && (
              <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                {t('pricingPage.savePercent', { percent: Math.max(...plans.filter(p => p.price_monthly > 0).map(p => getYearlySavingsPercent(p)), 0) })}
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Pricing Cards */}
      <div className="container mx-auto px-4 pb-16">
        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto -mt-8">
          {plans.map((plan) => {
            const style = PLAN_STYLES[plan.plan_id] || PLAN_STYLES.free;
            const PlanIcon = style.icon;
            const price = getPrice(plan);
            const fullPrice = getFullPrice(plan);  // Now uses plan object, not planId
            const discountPercent = getDiscountPercent(plan);  // Now uses plan object
            const isSelected = selectedPlan?.plan_id === plan.plan_id;
            const monthlyEquivalent = isYearly && plan.price_yearly > 0 
              ? plan.price_yearly / 12 
              : null;
            const hasPromoDiscount = fullPrice && fullPrice > price;
            const stripeReady = isStripeConfigured(plan);

            return (
              <Card 
                key={plan.plan_id}
                className={`relative overflow-hidden transition-all duration-300 ${
                  isSelected 
                    ? 'ring-2 ring-primary shadow-xl scale-[1.02]' 
                    : 'hover:shadow-lg'
                } ${style.border}`}
                onClick={() => plan.plan_id !== 'free' && setSelectedPlan(plan)}
                data-testid={`plan-card-${plan.plan_id}`}
              >
                {/* Launch Special Badge - Only show if there's a promotional discount */}
                {style.launchBadge && hasPromoDiscount && discountPercent > 0 && (
                  <div className="absolute top-0 left-0 right-0">
                    <div className={`bg-gradient-to-r ${style.launchBadgeColor} text-white text-xs font-bold py-1.5 px-3 text-center`}>
                      <Zap className="h-3 w-3 inline mr-1" />
                      LAUNCH SPECIAL - {discountPercent}% OFF
                    </div>
                  </div>
                )}

                <CardHeader className={`text-center pb-4 ${style.launchBadge && hasPromoDiscount ? 'pt-10' : ''}`}>
                  <div className={`w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br ${style.gradient} flex items-center justify-center shadow-lg mb-4`}>
                    <PlanIcon className="h-8 w-8 text-white" />
                  </div>
                  <CardTitle className="text-2xl">{plan.name}</CardTitle>
                  
                  {/* Price with Strikethrough Anchoring - Only when promotional discount exists */}
                  <div className="mt-4">
                    {/* Full Price Strikethrough */}
                    {hasPromoDiscount && (
                      <div className="mb-1">
                        <span className="text-lg text-slate-400 line-through decoration-red-500/50 decoration-2">
                          {formatCurrency(fullPrice)}
                        </span>
                      </div>
                    )}
                    
                    {/* Current Price */}
                    <div className="flex items-baseline justify-center gap-2">
                      <span className="text-4xl font-bold text-slate-900 dark:text-white" data-testid={`price-${plan.plan_id}`}>
                        {formatCurrency(price)}
                      </span>
                      <span className="text-slate-500">
                        /{isYearly ? t('pricingPage.perYear') : t('pricingPage.perMonth')}
                      </span>
                    </div>
                    
                    {/* Monthly Equivalent */}
                    {monthlyEquivalent && (
                      <p className="text-sm text-slate-400 mt-1">
                        {formatCurrency(monthlyEquivalent)}/mo equivalent
                      </p>
                    )}
                    
                    {/* Savings Badge - Only when promotional discount exists */}
                    {hasPromoDiscount && (
                      <Badge className="mt-2 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 gap-1">
                        <TrendingDown className="h-3 w-3" />
                        Save {formatCurrency(fullPrice - price)}
                      </Badge>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* Features */}
                  <ul className="space-y-3">
                    {(plan.features || []).map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm">
                        <Check className="h-5 w-5 text-green-500 flex-shrink-0" />
                        <span className="text-slate-600 dark:text-slate-300">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  {/* Fee Discounts */}
                  {(plan.buyer_premium_discount > 0 || plan.seller_commission_discount > 0) && (
                    <div className="pt-4 border-t space-y-2">
                      {plan.buyer_premium_discount > 0 && (
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-500">Buyer Fee Discount</span>
                          <Badge variant="secondary">{plan.buyer_premium_discount}% off</Badge>
                        </div>
                      )}
                      {plan.seller_commission_discount > 0 && (
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-500">Seller Fee Discount</span>
                          <Badge variant="secondary">{plan.seller_commission_discount}% off</Badge>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>

                <CardFooter className="flex flex-col gap-2">
                  <Button
                    className={`w-full gap-2 ${
                      plan.plan_id !== 'free' 
                        ? `bg-gradient-to-r ${style.gradient} hover:opacity-90` 
                        : ''
                    }`}
                    variant={plan.plan_id === 'free' ? 'outline' : 'default'}
                    disabled={checkoutLoading}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (plan.plan_id === 'free') {
                        toast.info('Free plan is available to all users');
                      } else {
                        handleCheckout(plan);
                      }
                    }}
                    data-testid={`select-plan-${plan.plan_id}`}
                  >
                    {checkoutLoading && selectedPlan?.plan_id === plan.plan_id ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        Processing...
                      </>
                    ) : plan.plan_id === 'free' ? (
                      t('pricingPage.currentPlan')
                    ) : (
                      <>
                        {t('pricingPage.choosePlan')}
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </Button>
                  {/* Terms of Sale */}
                  {plan.plan_id !== 'free' && (
                    <p className="mt-2 text-[11px] leading-relaxed text-slate-400 dark:text-slate-500 text-center px-2">
                      By purchasing, you agree that all payments are final and non-refundable. If you cancel, access continues until the end of your billing cycle.
                    </p>
                  )}
                  {/* Stripe Configuration Status */}
                  {plan.plan_id !== 'free' && !stripeReady && (
                    <div className="flex items-center justify-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                      <AlertCircle className="h-3 w-3" />
                      <span>{t("subscription.paymentSetupPending")}</span>
                    </div>
                  )}
                </CardFooter>
              </Card>
            );
          })}
        </div>

        {/* Checkout Section with Coupon */}
        {selectedPlan && selectedPlan.plan_id !== 'free' && (
          <Card className="max-w-lg mx-auto mt-12 bg-white/80 dark:bg-slate-800/80 backdrop-blur-xl border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                Complete Your Subscription
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {selectedPlan.name} Plan - {isYearly ? 'Yearly' : 'Monthly'} Billing
              </p>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Coupon Code Input */}
              <div className="space-y-3">
                <Label className="flex items-center gap-2">
                  <Ticket className="h-4 w-4" />
                  Have a Coupon Code?
                </Label>
                <div className="flex gap-2">
                  <Input
                    value={couponCode}
                    onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                    placeholder="Enter code (e.g., LAUNCH50)"
                    disabled={!!couponValidation}
                    className="flex-1 uppercase"
                    data-testid="coupon-input"
                  />
                  {couponValidation ? (
                    <Button variant="outline" onClick={removeCoupon} className="gap-2">
                      <X className="h-4 w-4" />
                      Remove
                    </Button>
                  ) : (
                    <Button 
                      variant="outline" 
                      onClick={validateCoupon}
                      disabled={validatingCoupon || !couponCode}
                      className="gap-2"
                      data-testid="apply-coupon-btn"
                    >
                      {validatingCoupon ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                      Apply
                    </Button>
                  )}
                </div>
                
                {/* Coupon Applied Success - Enhanced with Savings */}
                {couponValidation && (
                  <div className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                    <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
                      <Check className="h-5 w-5" />
                      <span className="font-bold text-lg">{couponValidation.code} applied!</span>
                    </div>
                    <p className="text-sm text-green-600 dark:text-green-500 mt-1">
                      {couponValidation.discount_type === 'percentage' 
                        ? `${couponValidation.discount_value}% off your subscription` 
                        : `${formatCurrency(couponValidation.discount_value)} off your subscription`}
                    </p>
                    
                    {/* Big Savings Highlight */}
                    <div className="mt-3 p-3 bg-white/60 dark:bg-slate-800/60 rounded-lg border border-green-300 dark:border-green-700">
                      <div className="flex items-center justify-center gap-2">
                        <PartyPopper className="h-5 w-5 text-amber-500" />
                        <span className="text-xl font-bold text-green-700 dark:text-green-300">
                          You are saving {formatCurrency(couponValidation.discount_amount)} today!
                        </span>
                        <PartyPopper className="h-5 w-5 text-amber-500" />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Price Breakdown */}
              <div className="space-y-3 pt-4 border-t">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Subtotal</span>
                  <span>{formatCurrency(getPrice(selectedPlan))}</span>
                </div>
                
                {couponValidation && (
                  <div className="flex justify-between text-sm text-green-600 dark:text-green-400 font-medium">
                    <span className="flex items-center gap-1">
                      <Percent className="h-3 w-3" />
                      Discount ({couponValidation.code})
                    </span>
                    <span>-{formatCurrency(couponValidation.discount_amount)}</span>
                  </div>
                )}
                
                <div className="flex justify-between text-lg font-bold pt-3 border-t">
                  <span>Total</span>
                  <div className="text-right">
                    {couponValidation && (
                      <span className="text-sm text-slate-400 line-through mr-2">
                        {formatCurrency(getPrice(selectedPlan))}
                      </span>
                    )}
                    <span className="text-primary text-2xl">
                      {couponValidation 
                        ? formatCurrency(couponValidation.new_total)
                        : formatCurrency(getPrice(selectedPlan))}
                    </span>
                  </div>
                </div>
              </div>

              {/* Checkout Button */}
              <Button
                className="w-full gap-2 h-12 text-lg"
                onClick={() => handleCheckout(selectedPlan)}
                disabled={checkoutLoading}
              >
                {checkoutLoading ? (
                  <>
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <DollarSign className="h-5 w-5" />
                    {isLoggedIn ? 'Proceed to Checkout' : 'Login to Subscribe'}
                  </>
                )}
              </Button>

              {/* Trust Badges */}
              <div className="flex items-center justify-center gap-4 pt-4 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Shield className="h-3 w-3" />
                  Secure Payment
                </span>
                <span>•</span>
                <span>{t("subscription.cancelAnytime")}</span>
                <span>•</span>
                <span>{t("subscription.instantAccess")}</span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default SubscriptionPricingPage;
