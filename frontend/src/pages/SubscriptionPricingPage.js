import API_BASE from '../config';
/**
 * SubscriptionPricingPage – 2x2 premium pricing grid
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import {
  Crown, Star, User as UserIcon, Check, ArrowRight,
  RefreshCw, Sparkles, Shield, Gift, TrendingDown, PartyPopper,
  Settings, PiggyBank, CreditCard, Calendar,
} from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';

const API = API_BASE;

/* ────── tier visual config ────── */
const TIERS = {
  free: {
    icon: UserIcon,
    accentTop: 'bg-slate-400',
    cardBg: 'bg-white',
    textName: 'text-slate-900',
    textDesc: 'text-slate-500',
    textPrice: 'text-slate-900',
    textStrike: 'text-slate-400',
    textFeature: 'text-slate-600',
    checkColor: 'text-green-500',
    savingColor: 'text-green-600',
    ctaClass: 'bg-slate-200 text-slate-500 cursor-default hover:bg-slate-200',
    ctaActiveClass: 'bg-slate-200 text-slate-500 cursor-default hover:bg-slate-200',
    discountBadgeBg: 'bg-green-100 text-green-700',
    ring: 'ring-slate-400',
  },
  premium: {
    icon: Star,
    accentTop: 'bg-gradient-to-r from-purple-500 to-indigo-500',
    cardBg: 'bg-white',
    textName: 'text-slate-900',
    textDesc: 'text-slate-500',
    textPrice: 'text-slate-900',
    textStrike: 'text-slate-400',
    textFeature: 'text-slate-600',
    checkColor: 'text-purple-500',
    savingColor: 'text-green-600',
    ctaClass: 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white',
    ctaActiveClass: 'bg-slate-200 text-slate-500 cursor-default hover:bg-slate-200',
    discountBadgeBg: 'bg-purple-100 text-purple-700',
    ring: 'ring-purple-400',
  },
  partner_pro: {
    icon: Shield,
    accentTop: 'bg-gradient-to-r from-teal-500 to-cyan-500',
    cardBg: 'bg-white',
    textName: 'text-slate-900',
    textDesc: 'text-slate-500',
    textPrice: 'text-slate-900',
    textStrike: 'text-slate-400',
    textFeature: 'text-slate-600',
    checkColor: 'text-teal-500',
    savingColor: 'text-green-600',
    ctaClass: 'bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 text-white',
    ctaActiveClass: 'bg-slate-200 text-slate-500 cursor-default hover:bg-slate-200',
    discountBadgeBg: 'bg-teal-100 text-teal-700',
    ring: 'ring-teal-400',
  },
  vip: {
    icon: Crown,
    accentTop: 'bg-gradient-to-r from-amber-400 to-yellow-500',
    cardBg: 'bg-[#1a1a2e]',
    textName: 'text-white',
    textDesc: 'text-[#FFD700]/70',
    textPrice: 'text-white',
    textStrike: 'text-white/50',
    textFeature: 'text-white',
    checkColor: 'text-[#FFD700]',
    savingColor: 'text-[#FFD700]',
    ctaClass: 'bg-[#FFD700] hover:bg-[#e6c200] text-[#1a1a2e] font-bold',
    ctaActiveClass: 'bg-[#FFD700]/30 text-[#FFD700] cursor-default hover:bg-[#FFD700]/30',
    discountBadgeBg: 'bg-[#FFD700] text-[#1a1a2e]',
    ring: 'ring-[#FFD700]',
  },
};

const SubscriptionPricingPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isYearly, setIsYearly] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(null);
  const [userTier, setUserTier] = useState('free');
  const [trialDays, setTrialDays] = useState(null);
  const [subStatus, setSubStatus] = useState(null);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  useEffect(() => { fetchPlans(); if (token) fetchUserTier(); }, []); // eslint-disable-line

  const fetchPlans = async () => {
    try {
      const res = await axios.get(`${API}/subscription-plans`);
      if (res.data.success) {
        const order = ['free', 'premium', 'partner_pro', 'vip'];
        setPlans((res.data.plans || []).sort((a, b) => order.indexOf(a.plan_id) - order.indexOf(b.plan_id)));
      }
    } catch { toast.error(t('pricingPage.loadError')); }
    finally { setLoading(false); }
  };

  const fetchUserTier = async () => {
    try {
      const res = await axios.get(`${API}/subscriptions/status`, { headers: { Authorization: `Bearer ${token}` } });
      setUserTier(res.data.tier || 'free');
      setSubStatus(res.data);
      if (res.data.trial_days_remaining > 0) setTrialDays(res.data.trial_days_remaining);
    } catch { /* ignore */ }
  };

  const handleCheckout = async (plan) => {
    if (!token) { navigate('/auth?redirect=/pricing'); return; }
    if (plan.plan_id === 'free' || plan.plan_id === userTier) return;
    setCheckoutLoading(plan.plan_id);
    try {
      const res = await axios.post(`${API}/subscriptions/create`, { plan_id: plan.plan_id }, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data.success) { toast.success(t('pricingPage.subscribeSuccess', { plan: getDisplayName(plan.plan_id) })); navigate('/settings'); }
    } catch (err) { toast.error(err.response?.data?.detail || t('pricingPage.subscribeFail')); }
    finally { setCheckoutLoading(null); }
  };

  const getDisplayName = (planId) => t(`pricingPage.planNames.${planId}`);
  const getTagline = (planId) => t(`pricingPage.planTaglines.${planId}`, '');
  const getPrice = (p) => isYearly ? p.price_yearly : p.price_monthly;
  const getFullPrice = (p) => {
    const orig = isYearly ? p.original_price_yearly : p.original_price_monthly;
    return orig && orig > getPrice(p) ? orig : null;
  };
  const getDiscount = (p) => { const f = getFullPrice(p); return f ? Math.round((1 - getPrice(p) / f) * 100) : 0; };
  const getYearlySave = (p) => p.price_monthly > 0 && p.price_monthly * 12 > p.price_yearly ? Math.round((1 - p.price_yearly / (p.price_monthly * 12)) * 100) : 0;

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <RefreshCw className="h-8 w-8 animate-spin text-primary" data-testid="pricing-loader" />
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 overflow-x-hidden" data-testid="pricing-page">
      {/* ── Hero ── */}
      <section className="relative overflow-hidden pt-16 sm:pt-20 pb-6 text-center px-4">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,58,237,.06),transparent_60%)]" />
        <div className="relative max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-amber-500/10 border border-amber-400/30 rounded-full text-sm">
            <Gift className="h-4 w-4 text-amber-500" />
            <span className="text-amber-700 font-medium" dangerouslySetInnerHTML={{ __html: t('pricingPage.launchBanner') }} />
            <PartyPopper className="h-4 w-4 text-amber-500" />
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 tracking-tight" data-testid="pricing-title">
            {t('pricingPage.subtitle')}
          </h1>
          {/* billing toggle */}
          <div className="flex items-center justify-center gap-3 pt-2">
            <span className={`text-sm font-medium ${!isYearly ? 'text-primary' : 'text-slate-400'}`}>{t('pricingPage.monthly')}</span>
            <Switch checked={isYearly} onCheckedChange={setIsYearly} className="data-[state=checked]:bg-primary" data-testid="billing-toggle" />
            <span className={`text-sm font-medium ${isYearly ? 'text-primary' : 'text-slate-400'}`}>{t('pricingPage.yearly')}</span>
            {isYearly && plans.length > 0 && (
              <Badge className="bg-green-100 text-green-700 text-xs">
                {t('pricingPage.savePercent', { percent: Math.max(...plans.filter(p => p.price_monthly > 0).map(p => getYearlySave(p)), 0) })}
              </Badge>
            )}
          </div>
        </div>
      </section>

      {/* ── 2x2 Pricing Grid ── */}
      <section className="max-w-[920px] mx-auto px-4 pb-12 sm:pb-16">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {plans.map((plan) => {
            const tier = TIERS[plan.plan_id] || TIERS.free;
            const Icon = tier.icon;
            const price = getPrice(plan);
            const fullPrice = getFullPrice(plan);
            const disc = getDiscount(plan);
            const isCurrent = plan.plan_id === userTier;
            const displayName = getDisplayName(plan.plan_id);
            const tagline = getTagline(plan.plan_id);

            return (
              <div
                key={plan.plan_id}
                className={`relative flex flex-col rounded-2xl shadow-md ${tier.cardBg} ${isCurrent ? `ring-2 ${tier.ring}` : 'ring-1 ring-slate-200'} overflow-hidden transition-shadow hover:shadow-lg`}
                style={{ minHeight: 420 }}
                data-testid={`plan-card-${plan.plan_id}`}
              >
                {/* accent top border */}
                <div className={`h-1.5 ${tier.accentTop}`} />

                {/* current plan badge */}
                {isCurrent && (
                  <div className="absolute top-3 right-3 z-10">
                    <Badge
                      className={`${plan.plan_id === 'vip' ? 'bg-[#FFD700] text-[#1a1a2e]' : 'bg-primary text-white'} text-[11px] font-bold px-2.5 py-0.5 uppercase tracking-wide`}
                      data-testid={`current-badge-${plan.plan_id}`}
                    >
                      {t('pricingPage.currentPlan')}
                    </Badge>
                  </div>
                )}

                {/* card body */}
                <div className="flex flex-col flex-1 p-6 sm:p-8">
                  {/* plan name + icon */}
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${plan.plan_id === 'vip' ? 'bg-[#FFD700]/20' : 'bg-slate-100'}`}>
                      <Icon className={`h-5 w-5 ${plan.plan_id === 'vip' ? 'text-[#FFD700]' : tier.checkColor}`} />
                    </div>
                    <div>
                      <h3 className={`text-lg font-bold ${tier.textName}`} style={plan.plan_id === 'vip' ? { color: '#FFFFFF' } : undefined} data-testid={`plan-name-${plan.plan_id}`}>{displayName}</h3>
                      {tagline && <p className={`text-xs ${tier.textDesc}`}>{tagline}</p>}
                    </div>
                  </div>

                  {/* pricing block */}
                  <div className="mb-5">
                    {fullPrice && disc > 0 && (
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-sm line-through decoration-2 ${tier.textStrike}`}>{formatCurrency(fullPrice)}</span>
                        <Badge className={`text-[11px] font-bold px-1.5 py-0 ${tier.discountBadgeBg}`}>
                          {disc}% {t('pricingPage.off')}
                        </Badge>
                      </div>
                    )}
                    <div className="flex items-baseline gap-1.5">
                      <span className={`text-3xl sm:text-4xl font-extrabold tracking-tight ${tier.textPrice}`} data-testid={`price-${plan.plan_id}`}>
                        {price > 0 ? formatCurrency(price) : t('pricingPage.free')}
                      </span>
                      {price > 0 && (
                        <span className={`text-sm ${tier.textDesc}`}>
                          /{isYearly ? t('pricingPage.yr') : t('pricingPage.mo')}
                        </span>
                      )}
                    </div>
                    {fullPrice && (
                      <p className={`text-xs mt-1 font-medium ${tier.savingColor}`}>
                        <TrendingDown className="h-3 w-3 inline mr-0.5" />
                        {t('pricingPage.saveAmount', { amount: formatCurrency(fullPrice - price) })}
                      </p>
                    )}
                  </div>

                  {/* features */}
                  <ul className="space-y-2.5 flex-1 mb-6">
                    {(plan.features || []).map((feat, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-[13px] leading-snug">
                        <Check className={`h-4 w-4 mt-0.5 flex-shrink-0 ${tier.checkColor}`} />
                        <span className={tier.textFeature}>{feat}</span>
                      </li>
                    ))}
                    {(plan.buyer_premium_discount > 0 || plan.seller_commission_discount > 0) && (
                      <>
                        <li className={`border-t ${plan.plan_id === 'vip' ? 'border-white/10' : 'border-slate-100'} my-1`} />
                        {plan.buyer_premium_discount > 0 && (
                          <li className="flex items-start gap-2.5 text-[13px] leading-snug">
                            <Check className={`h-4 w-4 mt-0.5 flex-shrink-0 ${tier.checkColor}`} />
                            <span className={tier.textFeature}>{t('pricingPage.buyerFeeDiscount', { percent: plan.buyer_premium_discount })}</span>
                          </li>
                        )}
                        {plan.seller_commission_discount > 0 && (
                          <li className="flex items-start gap-2.5 text-[13px] leading-snug">
                            <Check className={`h-4 w-4 mt-0.5 flex-shrink-0 ${tier.checkColor}`} />
                            <span className={tier.textFeature}>{t('pricingPage.sellerFeeDiscount', { percent: plan.seller_commission_discount })}</span>
                          </li>
                        )}
                      </>
                    )}
                  </ul>

                  {/* CTA */}
                  <Button
                    className={`w-full h-12 text-[15px] font-semibold ${isCurrent ? tier.ctaActiveClass : tier.ctaClass}`}
                    disabled={!!checkoutLoading || isCurrent}
                    onClick={() => handleCheckout(plan)}
                    data-testid={`select-plan-${plan.plan_id}`}
                  >
                    {checkoutLoading === plan.plan_id ? (
                      <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> {t('pricingPage.processing')}</>
                    ) : isCurrent ? (
                      t('pricingPage.currentPlan')
                    ) : plan.plan_id === 'free' ? (
                      t('pricingPage.currentPlan')
                    ) : plan.plan_id === 'vip' ? (
                      <><Crown className="h-4 w-4 mr-2" /> {t('pricingPage.goVip')}</>
                    ) : (
                      <>{t('pricingPage.choosePlan')} <ArrowRight className="h-4 w-4 ml-2" /></>
                    )}
                  </Button>

                  {/* trial badge */}
                  {isCurrent && trialDays && (
                    <div className="mt-2 text-center">
                      <Badge className="bg-teal-100 text-teal-700 text-xs">
                        <Sparkles className="h-3 w-3 mr-1" /> {t('pricingPage.trialActive', { days: trialDays })}
                      </Badge>
                    </div>
                  )}

                  {/* terms */}
                  {plan.plan_id !== 'free' && !isCurrent && (
                    <p className={`mt-3 text-[11px] text-center ${plan.plan_id === 'vip' ? 'text-white/40' : 'text-slate-400'}`}>
                      {t('pricingPage.terms')}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Account Settings Section ── */}
      {token && subStatus && (
        <section className="max-w-[920px] mx-auto px-4 pb-12" data-testid="account-settings-section">
          <div className="bg-white rounded-2xl shadow-sm ring-1 ring-slate-200 p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
                <Settings className="h-5 w-5 text-slate-600" />
              </div>
              <h2 className="text-lg sm:text-xl font-bold text-slate-900" data-testid="account-settings-heading">{t('pricingPage.accountSettings')}</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-slate-50 rounded-xl p-4" data-testid="account-current-plan">
                <p className="text-xs text-slate-500 mb-1">{t('pricingPage.yourPlan')}</p>
                <p className="text-lg font-bold text-slate-900">{getDisplayName(userTier)}</p>
                {subStatus.status === 'active' && !subStatus.cancel_at_period_end && (
                  <Badge className="mt-1 bg-green-100 text-green-700 text-xs">{t('pricingPage.active')}</Badge>
                )}
                {subStatus.cancel_at_period_end && (
                  <Badge className="mt-1 bg-amber-100 text-amber-700 text-xs">{t('pricingPage.cancelsPeriodEnd')}</Badge>
                )}
              </div>
              <div className="bg-slate-50 rounded-xl p-4" data-testid="account-billing">
                <p className="text-xs text-slate-500 mb-1">{t('pricingPage.billing')}</p>
                {subStatus.end_date ? (
                  <>
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-4 w-4 text-slate-400" />
                      <p className="text-sm font-medium text-slate-900">{t('pricingPage.renewsOn')}</p>
                    </div>
                    <p className="text-sm text-slate-600 mt-0.5">{new Date(subStatus.end_date).toLocaleDateString()}</p>
                  </>
                ) : (
                  <p className="text-sm text-slate-600">{t('pricingPage.noBilling')}</p>
                )}
              </div>
              <div className="bg-slate-50 rounded-xl p-4" data-testid="account-payment">
                <p className="text-xs text-slate-500 mb-1">{t('pricingPage.payment')}</p>
                <div className="flex items-center gap-1.5">
                  <CreditCard className="h-4 w-4 text-slate-400" />
                  <p className="text-sm font-medium text-slate-900">
                    {subStatus.has_payment_method ? t('pricingPage.cardOnFile') : t('pricingPage.noCard')}
                  </p>
                </div>
                <Link to="/settings" className="text-xs text-primary hover:underline mt-1 inline-block" data-testid="manage-settings-link">
                  {t('pricingPage.manageSettings')}
                </Link>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Personalized Savings Section ── */}
      {plans.length > 0 && (
        <section className="max-w-[920px] mx-auto px-4 pb-16 sm:pb-20" data-testid="savings-section">
          <div className="bg-white rounded-2xl shadow-sm ring-1 ring-slate-200 p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center">
                <PiggyBank className="h-5 w-5 text-green-600" />
              </div>
              <h2 className="text-lg sm:text-xl font-bold text-slate-900" data-testid="savings-heading">{t('pricingPage.personalizedSavings')}</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {plans.filter(p => p.plan_id !== 'free').map((plan) => {
                const yearlyPrice = plan.price_yearly || 0;
                const monthlyEquiv = yearlyPrice > 0 ? (yearlyPrice / 12) : 0;
                const monthlyFull = plan.price_monthly || 0;
                const monthlySaving = monthlyFull > 0 ? (monthlyFull - monthlyEquiv) : 0;
                return (
                  <div key={plan.plan_id} className="bg-slate-50 rounded-xl p-4 text-center" data-testid={`savings-${plan.plan_id}`}>
                    <p className="text-sm font-bold text-slate-900 mb-2">{getDisplayName(plan.plan_id)}</p>
                    {monthlyFull > 0 && monthlySaving > 0 ? (
                      <>
                        <p className="text-2xl font-extrabold text-green-600">{formatCurrency(monthlySaving)}</p>
                        <p className="text-xs text-slate-500 mt-1">{t('pricingPage.savedPerMonth')}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{t('pricingPage.withYearlyBilling')}</p>
                      </>
                    ) : (
                      <>
                        <p className="text-2xl font-extrabold text-slate-900">{formatCurrency(yearlyPrice)}</p>
                        <p className="text-xs text-slate-500 mt-1">{t('pricingPage.perYear')}</p>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default SubscriptionPricingPage;
