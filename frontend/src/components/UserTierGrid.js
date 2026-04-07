import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Crown, Star, Zap, Shield, TrendingUp, Percent, Megaphone, Headphones, Check, X, Sparkles, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const UserTierGrid = ({ currentTier = 'free', onUpgrade }) => {
  const { t } = useTranslation();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(null);
  const [startingTrial, setStartingTrial] = useState(false);
  const [trialStatus, setTrialStatus] = useState(null);

  useEffect(() => { fetchPlans(); fetchTrialStatus(); }, []);

  const fetchPlans = async () => {
    try {
      const res = await axios.get(`${API}/subscription-plans`);
      if (res.data.success) setPlans(res.data.plans || []);
    } catch (e) { console.error('Error fetching plans:', e); }
    finally { setLoading(false); }
  };

  const fetchTrialStatus = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      const res = await axios.get(`${API}/subscriptions/trial-status`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data) setTrialStatus(res.data);
    } catch { /* skip */ }
  };

  const getPlanPrice = (id) => plans.find(p => p.plan_id === id)?.price_yearly || 0;
  const getOriginalPrice = (id) => {
    const p = plans.find(x => x.plan_id === id);
    const orig = p?.original_price_yearly || 0;
    return orig > (p?.price_yearly || 0) ? orig : null;
  };

  const formatPrice = (n) => new Intl.NumberFormat('en-CA', { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n || 0);

  const handleUpgrade = async (tierId) => {
    if (tierId === 'free') return;
    const token = localStorage.getItem('token');
    if (!token) { toast.error('Please log in to subscribe'); return; }
    setUpgrading(tierId);
    try {
      const res = await axios.post(`${API}/subscriptions/create`, { plan_id: tierId }, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data.success) {
        toast.success(t('subCards.processing'));
        if (onUpgrade) onUpgrade(tierId);
        window.location.reload();
      }
    } catch (err) { toast.error(err?.response?.data?.detail || 'Subscription failed'); }
    finally { setUpgrading(null); }
  };

  const handleStartTrial = async () => {
    const token = localStorage.getItem('token');
    if (!token) { toast.error('Please log in'); return; }
    setStartingTrial(true);
    try {
      const res = await axios.post(`${API}/subscriptions/start-trial`, { plan_id: 'premium' }, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data.success) { toast.success('Trial started!'); window.location.reload(); }
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not start trial'); }
    finally { setStartingTrial(false); }
  };

  // ─── Tier definitions (3 tiers only, no Partner Pro) ───
  const tiers = [
    {
      id: 'free',
      nameKey: 'subCards.plans.free.name',
      descKey: 'subCards.plans.free.description',
      periodKey: 'subCards.plans.free.period',
      icon: Zap,
      accent: 'slate',
      cardBg: 'bg-white dark:bg-slate-800/80 border-slate-200 dark:border-slate-700',
      iconBg: 'bg-slate-100 dark:bg-slate-700',
      iconColor: 'text-slate-500',
      features: [
        { key: 'subCards.features.standardBidding', included: true },
        { key: 'subCards.features.wishlistAccess', included: true },
        { key: 'subCards.features.feeStandard', included: true },
        { key: 'subCards.features.basicVisibility', included: true },
        { key: 'subCards.features.autoBidBot', included: false },
        { key: 'subCards.features.promo3Day', included: false },
      ],
    },
    {
      id: 'premium',
      nameKey: 'subCards.plans.premium.name',
      descKey: 'subCards.plans.premium.description',
      periodKey: 'subCards.plans.premium.period',
      icon: Star,
      accent: 'purple',
      popular: true,
      cardBg: 'bg-gradient-to-b from-purple-50 to-white dark:from-purple-950/40 dark:to-slate-800/80 border-purple-400 dark:border-purple-600',
      iconBg: 'bg-purple-100 dark:bg-purple-900/50',
      iconColor: 'text-purple-600 dark:text-purple-400',
      features: [
        { key: 'subCards.features.feePremium', included: true, highlight: 'subCards.highlights.save15' },
        { key: 'subCards.features.autoBidBot', included: true },
        { key: 'subCards.features.promo3Day', included: true },
        { key: 'subCards.features.priorityRanking', included: true },
        { key: 'subCards.features.premiumBadge', included: true },
        { key: 'subCards.features.prioritySupport', included: true },
      ],
    },
    {
      id: 'vip',
      nameKey: 'subCards.plans.vip.name',
      descKey: 'subCards.plans.vip.description',
      periodKey: 'subCards.plans.vip.period',
      icon: Crown,
      accent: 'amber',
      dark: true,
      cardBg: 'bg-gradient-to-b from-slate-900 to-slate-950 border-amber-500/60',
      iconBg: 'bg-gradient-to-br from-amber-300 to-yellow-500',
      iconColor: 'text-amber-900',
      features: [
        { key: 'subCards.features.feeVip', included: true, highlight: 'subCards.highlights.save2' },
        { key: 'subCards.features.autoBidPriority', included: true },
        { key: 'subCards.features.promo7Day', included: true },
        { key: 'subCards.features.earlyAccess24h', included: true },
        { key: 'subCards.features.vipBadge', included: true },
        { key: 'subCards.features.dedicatedSupport', included: true },
      ],
    },
  ];

  if (loading) {
    return (
      <div className="w-full py-12 flex items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="w-full" data-testid="user-tier-grid">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {tiers.map((tier) => {
          const isCurrent = currentTier === tier.id;
          const Icon = tier.icon;
          const price = getPlanPrice(tier.id);
          const originalPrice = getOriginalPrice(tier.id);

          return (
            <div
              key={tier.id}
              className={`relative flex flex-col rounded-2xl border-2 p-6 transition-all duration-300 hover:shadow-xl ${tier.cardBg} ${tier.popular ? 'md:-translate-y-2 shadow-lg shadow-purple-200/40 dark:shadow-purple-900/30' : ''}`}
              data-testid={`tier-card-${tier.id}`}
            >
              {/* Popular badge */}
              {tier.popular && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-xs font-bold tracking-wider rounded-full shadow-lg" data-testid="popular-badge">
                  BEST VALUE
                </div>
              )}

              {/* Current plan badge */}
              {isCurrent && (
                <div className="absolute -top-3.5 right-4 px-4 py-1 bg-green-500 text-white text-xs font-bold tracking-wider rounded-full shadow-lg ring-2 ring-green-300" data-testid={`current-badge-${tier.id}`}>
                  {t('subCards.currentPlan')}
                </div>
              )}

              {/* Icon + Title */}
              <div className="text-center mb-5">
                <div className={`w-14 h-14 mx-auto mb-3 rounded-xl flex items-center justify-center ${tier.iconBg} shadow-md`}>
                  <Icon className={`h-7 w-7 ${tier.iconColor}`} />
                </div>
                <h3
                  className={`text-xl font-bold mb-1 ${tier.dark ? '' : 'text-slate-900 dark:text-white'}`}
                  style={tier.dark ? { color: '#FFFFFF' } : undefined}
                  data-testid={`plan-title-${tier.id}`}
                >
                  {t(tier.nameKey)}
                </h3>
                <p className={`text-sm ${tier.dark ? 'text-slate-400' : 'text-slate-500 dark:text-slate-400'}`}>
                  {t(tier.descKey)}
                </p>
              </div>

              {/* Price */}
              <div className="text-center mb-5">
                {originalPrice && (
                  <span className={`text-sm line-through mr-2 ${tier.dark ? 'text-slate-500' : 'text-slate-400'}`}>
                    ${formatPrice(originalPrice)}
                  </span>
                )}
                <span className={`text-3xl font-extrabold ${tier.dark ? 'text-white' : 'text-slate-900 dark:text-white'}`}>
                  ${formatPrice(price)}
                </span>
                <span className={`text-sm ml-1 ${tier.dark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {t(tier.periodKey)}
                </span>
              </div>

              {/* Features — check/cross list */}
              <ul className="space-y-2.5 mb-6 flex-1" data-testid={`features-${tier.id}`}>
                {tier.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    {f.included ? (
                      <div className="mt-0.5 w-5 h-5 rounded-full bg-green-100 dark:bg-green-900/40 flex items-center justify-center shrink-0">
                        <Check className="h-3 w-3 text-green-600 dark:text-green-400" />
                      </div>
                    ) : (
                      <div className="mt-0.5 w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center shrink-0">
                        <X className="h-3 w-3 text-slate-400 dark:text-slate-500" />
                      </div>
                    )}
                    <span className={`text-sm leading-snug ${
                      f.included
                        ? (tier.dark ? 'text-slate-200' : 'text-slate-700 dark:text-slate-300')
                        : 'text-slate-400 dark:text-slate-500 line-through'
                    }`}>
                      {t(f.key)}
                      {f.highlight && (
                        <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${
                          tier.dark ? 'bg-green-500/20 text-green-400' : 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                        }`}>
                          {t(f.highlight)}
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>

              {/* CTA button — always at the bottom via flex */}
              <div className="mt-auto space-y-3">
                <Button
                  onClick={() => handleUpgrade(tier.id)}
                  disabled={isCurrent || upgrading === tier.id || tier.id === 'free'}
                  className={`w-full h-11 rounded-xl font-semibold text-sm transition-all ${
                    isCurrent
                      ? 'bg-green-500/20 text-green-700 dark:text-green-400 border border-green-500/40 cursor-default hover:bg-green-500/20'
                      : tier.id === 'free'
                        ? 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 cursor-default hover:bg-slate-100'
                        : tier.dark
                          ? 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-black font-bold shadow-lg shadow-amber-500/25'
                          : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white shadow-lg shadow-purple-500/25'
                  }`}
                  data-testid={`upgrade-btn-${tier.id}`}
                >
                  {upgrading === tier.id ? (
                    <><RefreshCw className="h-4 w-4 animate-spin mr-2" /> {t('subCards.processing')}</>
                  ) : isCurrent ? (
                    <><Check className="h-4 w-4 mr-1.5" /> {t('subCards.currentPlan')}</>
                  ) : (
                    t(`subCards.plans.${tier.id}.cta`)
                  )}
                </Button>

                {/* Trial CTA for premium (non-partners only) */}
                {tier.id === 'premium' && currentTier === 'free' && !trialStatus?.has_used_trial && (
                  <button
                    onClick={handleStartTrial}
                    disabled={startingTrial}
                    className="w-full text-xs font-medium text-purple-600 dark:text-purple-400 hover:underline"
                    data-testid="start-trial-btn"
                  >
                    {startingTrial ? t('subCards.starting') : t('subCards.tryFree')}
                  </button>
                )}

                {trialStatus?.is_trial_active && tier.id === 'premium' && (
                  <span className="block text-center text-xs font-medium px-3 py-1 rounded-full bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300" data-testid="trial-active-badge">
                    {t('subCards.trialActive', { days: trialStatus.days_remaining })}
                  </span>
                )}
              </div>

              {/* Fine print */}
              {tier.id !== 'free' && !isCurrent && (
                <p className={`mt-3 text-[10px] text-center leading-relaxed ${tier.dark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {t('subCards.termsText')}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default UserTierGrid;
