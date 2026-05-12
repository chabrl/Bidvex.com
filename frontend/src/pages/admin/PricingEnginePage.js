/**
 * iter210 Step 3 — Pricing Engine admin page.
 *
 * Renders an editable card per pricing key (vehicle_dealer_annual_fee +
 * partner_annual_fee). The admin can tweak base price, launch discount %, and
 * launch window days; the backend regenerates the Stripe Price/Coupon as
 * needed and recomputes the effective price preview.
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Loader2, Save, DollarSign, Calendar, Tag } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import API_BASE from '../../config';

const KEY_LABELS = {
  vehicle_dealer_annual_fee: {
    en: 'Vehicle Dealer Platform Fee',
    fr: 'Frais de plateforme — marchand automobile',
  },
  partner_annual_fee: {
    en: 'Partner Platform Fee',
    fr: 'Frais de plateforme — partenaire',
  },
};

const PricingEnginePage = () => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [data, setData] = useState({});
  const [drafts, setDrafts] = useState({});
  const [savingKey, setSavingKey] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/pricing-engine`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
      const initDrafts = {};
      for (const [k, v] of Object.entries(r.data)) {
        initDrafts[k] = {
          base_price_cad: v.base_price_cad,
          launch_discount_percent: v.launch_discount_percent,
          launch_window_days: v.launch_window_days,
        };
      }
      setDrafts(initDrafts);
    } catch (e) {
      toast.error(isFr ? 'Échec de chargement' : 'Failed to load pricing settings');
    } finally {
      setLoading(false);
    }
  }, [token, isFr]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const previewEffective = (key) => {
    const d = drafts[key];
    if (!d) return 0;
    const base = parseFloat(d.base_price_cad || 0);
    const pct = parseFloat(d.launch_discount_percent || 0);
    return Math.max(0, base - (base * pct / 100));
  };

  const save = async (key) => {
    setSavingKey(key);
    try {
      const body = {
        base_price_cad: parseFloat(drafts[key].base_price_cad),
        launch_discount_percent: parseFloat(drafts[key].launch_discount_percent),
        launch_window_days: parseInt(drafts[key].launch_window_days, 10),
      };
      await axios.put(`${API_BASE}/admin/pricing-engine/${key}`, body, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      toast.success(isFr ? 'Tarification enregistrée' : 'Pricing saved');
      await fetchAll();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : (isFr ? "Échec de l'enregistrement" : 'Save failed'));
    } finally {
      setSavingKey(null);
    }
  };

  const fmt = (n) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));

  return (
    <div className="space-y-6" data-testid="pricing-engine-page">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          {isFr ? 'Moteur de tarification' : 'Pricing Engine'}
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          {isFr
            ? 'Configurez les frais de plateforme et les rabais de lancement. Les abonnements actuels sont préservés (grandfather).'
            : 'Configure platform fees and launch discounts. Existing subscriptions are grandfathered — only new signups use the updated price.'}
        </p>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="pricing-engine-loading">
          <Loader2 className="w-4 h-4 animate-spin" /> {isFr ? 'Chargement…' : 'Loading…'}
        </div>
      ) : (
        Object.keys(KEY_LABELS).map(key => {
          const live = data[key] || {};
          const d = drafts[key] || {};
          const preview = previewEffective(key);
          const cutoff = live.launch_cutoff_date
            ? new Date(live.launch_cutoff_date).toLocaleDateString(isFr ? 'fr-CA' : 'en-CA')
            : '—';
          return (
            <Card key={key} className="border-slate-200 dark:border-slate-700" data-testid={`pricing-card-${key}`}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  <span className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4" />
                    {isFr ? KEY_LABELS[key].fr : KEY_LABELS[key].en}
                  </span>
                  {live.is_within_launch_window ? (
                    <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-300">
                      {isFr ? 'Lancement actif' : 'Launch active'}
                    </Badge>
                  ) : (
                    <Badge variant="outline">
                      {isFr ? 'Lancement expiré' : 'Launch expired'}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs">{isFr ? 'Prix annuel (CAD)' : 'Annual Base Price (CAD)'}</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={d.base_price_cad}
                      onChange={e => setDrafts({ ...drafts, [key]: { ...d, base_price_cad: e.target.value } })}
                      data-testid={`pricing-base-${key}`}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">{isFr ? 'Rabais de lancement (%)' : 'Launch Discount (%)'}</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      max="100"
                      value={d.launch_discount_percent}
                      onChange={e => setDrafts({ ...drafts, [key]: { ...d, launch_discount_percent: e.target.value } })}
                      data-testid={`pricing-discount-${key}`}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">{isFr ? 'Fenêtre de lancement (jours)' : 'Launch Window (days)'}</Label>
                    <Input
                      type="number"
                      step="1"
                      min="0"
                      value={d.launch_window_days}
                      onChange={e => setDrafts({ ...drafts, [key]: { ...d, launch_window_days: e.target.value } })}
                      data-testid={`pricing-window-${key}`}
                    />
                  </div>
                </div>

                <div className="rounded-lg bg-slate-50 dark:bg-slate-900/40 px-3 py-3 text-sm space-y-1">
                  <div className="flex justify-between text-slate-600 dark:text-slate-300">
                    <span>{isFr ? 'Prix effectif (aperçu)' : 'Effective Price Preview'}</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-white" data-testid={`pricing-preview-${key}`}>
                      {fmt(preview)} {isFr ? '/an' : '/yr'}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span className="flex items-center gap-1.5"><Calendar className="w-3 h-3" /> {isFr ? "Date butoir de l'offre" : 'Launch cutoff'}</span>
                    <span>{cutoff}</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span className="flex items-center gap-1.5"><Tag className="w-3 h-3" /> {isFr ? 'Stripe Price' : 'Stripe Price'}</span>
                    <span className="font-mono">{live.stripe_price_id || '—'}</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span className="flex items-center gap-1.5"><Tag className="w-3 h-3" /> {isFr ? 'Stripe Coupon' : 'Stripe Coupon'}</span>
                    <span className="font-mono">{live.stripe_coupon_id || '—'}</span>
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button
                    onClick={() => save(key)}
                    disabled={savingKey === key}
                    data-testid={`pricing-save-${key}`}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {savingKey === key ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isFr ? 'Enregistrement…' : 'Saving…'}</>
                    ) : (
                      <><Save className="w-4 h-4 mr-2" /> {isFr ? 'Enregistrer' : 'Save Pricing Settings'}</>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
};

export default PricingEnginePage;
