/**
 * PromoBanner — iter330
 *
 * Reads the subscription plans API and renders a "save 50%" banner whenever
 * `original_price_yearly > price_yearly`. Designed for the public pricing
 * page; pure-display (no auth required).
 *
 * Also surfaces the 1-month-free-trial and first-listing-free Summer 2026
 * promos based on the user's promo state (if authenticated).
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Sparkles, BadgePercent, Clock, Gift } from 'lucide-react';
import API_BASE from '../config';

const API = API_BASE;

function _pct_off(original, live) {
  if (!original || !live || original <= live) return 0;
  return Math.round((1 - live / original) * 100);
}

export default function PromoBanner({ token = null }) {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [plans, setPlans] = useState([]);
  const [promoState, setPromoState] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const planRes = await axios.get(`${API}/subscription-plans`);
        if (!cancelled) setPlans(planRes.data?.plans || []);
        if (token) {
          try {
            const stateRes = await axios.get(`${API}/promo/state`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (!cancelled) setPromoState(stateRes.data);
          } catch { /* not signed in or no profile yet */ }
        }
      } catch { /* graceful — banner just hides */ }
      finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  if (loading) return null;

  // Find the deepest discount across all paid plans — used as the banner's
  // headline % and the strikethrough pair.
  let bestDiscount = null;
  for (const p of plans) {
    if (p.plan_id === 'free') continue;
    const pct = _pct_off(p.original_price_yearly, p.price_yearly);
    if (pct > 0 && (!bestDiscount || pct > bestDiscount.pct)) {
      bestDiscount = {
        plan_id: p.plan_id,
        name: p.name || p.plan_id,
        pct,
        original_yearly: p.original_price_yearly,
        live_yearly: p.price_yearly,
        live_monthly: p.price_monthly,
        original_monthly: p.original_price_monthly,
      };
    }
  }

  // Compose pills
  const pills = [];
  if (bestDiscount) {
    pills.push({
      key: 'promo-pct',
      Icon: BadgePercent,
      label: fr ? `${bestDiscount.pct} % de rabais Été 2026` : `Save ${bestDiscount.pct}% — Summer 2026`,
      detail: fr
        ? `${bestDiscount.name} : $${bestDiscount.live_yearly.toFixed(2)}/an (au lieu de $${bestDiscount.original_yearly.toFixed(2)})`
        : `${bestDiscount.name}: $${bestDiscount.live_yearly.toFixed(2)}/yr (was $${bestDiscount.original_yearly.toFixed(2)})`,
    });
  }
  if (promoState?.trial_eligible) {
    pills.push({
      key: 'promo-trial',
      Icon: Clock,
      label: fr ? `${promoState.trial_days || 30} jours d'essai gratuit` : `${promoState.trial_days || 30}-day free trial`,
      detail: fr
        ? 'Activez n\'importe quel forfait payant — annulez avant la fin pour zéro frais.'
        : 'Activate any paid plan — cancel before the end for zero charge.',
    });
  }
  if (promoState?.first_listing_free_eligible) {
    pills.push({
      key: 'promo-first-listing',
      Icon: Gift,
      label: fr ? 'Première annonce sur nous' : 'First listing on us',
      detail: fr
        ? 'Votre toute première annonce est offerte (frais d\'emplacement à 0 $).'
        : 'Your very first listing\'s slot fee is on us ($0.00).',
    });
  }

  if (pills.length === 0) return null;

  return (
    <div
      className="rounded-2xl p-6 md:p-8 text-white"
      style={{ background: 'linear-gradient(135deg, #0B2545 0%, #2186C6 100%)' }}
      data-testid="promo-banner"
    >
      <div className="flex items-center gap-3 mb-4">
        <Sparkles className="w-6 h-6 text-cyan-300" />
        <h2 className="text-xl font-bold uppercase tracking-wider" data-testid="promo-banner-title">
          {fr ? 'Promotions actives' : 'Active Promotions'}
        </h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="promo-banner-pills">
        {pills.map(({ key, Icon, label, detail }) => (
          <div
            key={key}
            data-testid={key}
            className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/15 hover:border-cyan-300/50 transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-5 h-5 text-cyan-300" />
              <span className="text-sm font-bold">{label}</span>
            </div>
            <p className="text-xs text-cyan-100 leading-relaxed">{detail}</p>
          </div>
        ))}
      </div>
      {bestDiscount && (
        <p className="mt-4 text-[11px] text-cyan-200 italic">
          {fr
            ? `* Affichage hors taxes. Le prix livré reflète déjà le rabais Été 2026.`
            : `* Prices shown exclude tax. The live price already reflects the Summer 2026 discount.`}
        </p>
      )}
    </div>
  );
}
