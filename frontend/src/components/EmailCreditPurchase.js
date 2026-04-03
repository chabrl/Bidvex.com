import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { Badge } from './ui/badge';
import { Mail, Loader2, Info } from 'lucide-react';

const API = API_BASE;

const EMAIL_TIERS = [
  { min: 1, max: 1000, per_email: 0.018 },
  { min: 1001, max: 5000, per_email: 0.015 },
  { min: 5001, max: 10000, per_email: 0.012 },
  { min: 10001, max: 100000, per_email: 0.010 },
];

function getPerEmailRate(qty) {
  const tier = EMAIL_TIERS.find((t) => qty >= t.min && qty <= t.max);
  return tier ? tier.per_email : 0.018;
}

const EmailCreditPurchase = () => {
  const { t, i18n } = useTranslation();
  const { token, user } = useAuth();
  const [quantity, setQuantity] = useState(500);
  const [purchasing, setPurchasing] = useState(false);
  const isFr = i18n.language === 'fr';

  const calc = useMemo(() => {
    const rate = getPerEmailRate(quantity);
    const subtotal = quantity * rate;
    const gst = subtotal * 0.05;
    const qst = subtotal * 0.09975;
    const total = subtotal + gst + qst;
    return { rate, subtotal, gst, qst, total };
  }, [quantity]);

  const handlePurchase = async () => {
    setPurchasing(true);
    try {
      const res = await axios.post(
        `${API}/payments/email-credits/purchase`,
        { quantity, return_url: window.location.href },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to start checkout';
      alert(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setPurchasing(false);
    }
  };

  const formatCAD = (v) =>
    new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', { style: 'currency', currency: 'CAD' }).format(v);

  const currentCredits = user?.email_credits || 0;

  return (
    <Card className="border-sky-200 dark:border-sky-900/40" data-testid="email-credit-purchase">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Mail className="h-5 w-5 text-sky-600" />
            {isFr ? 'Crédits Marketing Email' : 'Email Marketing Credits'}
          </CardTitle>
          <Badge variant="outline" className="text-xs" data-testid="current-email-credits">
            {currentCredits.toLocaleString()} {isFr ? 'crédits' : 'credits'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Quantity Slider */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">
              {isFr ? 'Quantité' : 'Quantity'}
            </label>
            <span className="text-lg font-bold text-sky-700" data-testid="email-qty-display">
              {quantity.toLocaleString()}
            </span>
          </div>
          <Slider
            min={100}
            max={100000}
            step={100}
            value={[quantity]}
            onValueChange={(v) => setQuantity(v[0])}
            className="w-full"
            data-testid="email-qty-slider"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
            <span>100</span>
            <span>100,000</span>
          </div>
        </div>

        {/* Pricing Tier indicator */}
        <div className="flex flex-wrap gap-1.5">
          {EMAIL_TIERS.map((tier) => {
            const active = quantity >= tier.min && quantity <= tier.max;
            return (
              <Badge
                key={tier.min}
                variant={active ? 'default' : 'outline'}
                className={`text-[10px] ${active ? 'bg-sky-600' : ''}`}
              >
                {tier.min.toLocaleString()}+ = ${tier.per_email.toFixed(3)}/ea
              </Badge>
            );
          })}
        </div>

        {/* Cost Breakdown */}
        <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span>{isFr ? 'Sous-total' : 'Subtotal'} ({quantity.toLocaleString()} &times; ${calc.rate.toFixed(3)})</span>
            <span className="font-medium">{formatCAD(calc.subtotal)}</span>
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>GST (TPS 5%)</span>
            <span>{formatCAD(calc.gst)}</span>
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>QST (TVQ 9.975%)</span>
            <span>{formatCAD(calc.qst)}</span>
          </div>
          <div className="flex justify-between font-semibold border-t pt-1.5">
            <span>Total</span>
            <span data-testid="email-total-price">{formatCAD(calc.total)}</span>
          </div>
        </div>

        <Button
          onClick={handlePurchase}
          disabled={purchasing || quantity < 100}
          className="w-full bg-gradient-to-r from-sky-500 to-sky-600 hover:from-sky-600 hover:to-sky-700 text-white"
          data-testid="buy-email-credits-btn"
        >
          {purchasing ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Mail className="h-4 w-4 mr-2" />
          )}
          {isFr ? `Acheter ${quantity.toLocaleString()} crédits` : `Purchase ${quantity.toLocaleString()} Credits`}
        </Button>

        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>
            {isFr
              ? 'Les crédits n\'expirent jamais. Le tarif baisse avec le volume. Taxes QC incluses au paiement.'
              : 'Credits never expire. Rate decreases with volume. QC taxes applied at checkout.'}
          </span>
        </div>
      </CardContent>
    </Card>
  );
};

export default EmailCreditPurchase;
