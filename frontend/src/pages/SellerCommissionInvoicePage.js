import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Loader2, CreditCard, Banknote, Send, FileText, CheckCircle2, AlertTriangle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmt = (cents) => `$${(Number(cents || 0) / 100).toFixed(2)}`;

export default function SellerCommissionInvoicePage() {
  const { listingId } = useParams();
  const { i18n } = useTranslation();
  const isFr = i18n.language === 'fr';
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [payMethod, setPayMethod] = useState('stripe');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const token = localStorage.getItem('token');
        const r = await axios.get(`${API}/seller/commission-invoice/${listingId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setInvoice(r.data);
      } catch (e) {
        setError(e?.response?.data?.detail || (isFr ? 'Erreur lors du chargement.' : 'Failed to load invoice.'));
      } finally {
        setLoading(false);
      }
    })();
  }, [listingId, isFr]);

  const payNow = async () => {
    try {
      setSubmitting(true);
      setError(null);
      const token = localStorage.getItem('token');
      const r = await axios.post(
        `${API}/seller/commission-invoice/${listingId}/pay-now`,
        {
          payment_method: payMethod,
          return_url: `${window.location.origin}/seller/commission-invoice/${listingId}`,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (payMethod === 'stripe' && r.data.checkout_url) {
        window.location.href = r.data.checkout_url;
      } else {
        // Offline: show a success state locally
        setInvoice((prev) => ({ ...prev, payment_status: 'pending', _offline_instructions: r.data.instructions }));
      }
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === 'string' ? d : (d?.reason || 'Failed to submit payment.'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="commission-invoice-loading">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-8" data-testid="commission-invoice-error">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{typeof error === 'string' ? error : JSON.stringify(error)}</AlertDescription>
        </Alert>
      </div>
    );
  }
  if (!invoice) return null;

  const row = invoice.breakdown_by_method?.[payMethod] || {};
  const paid = invoice.payment_status === 'paid';

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6" data-testid="seller-commission-invoice-page">
      <div>
        <h1 className="text-2xl font-bold" data-testid="commission-invoice-title">
          {isFr ? 'Facture de commission BidVex' : 'BidVex Commission Invoice'}
        </h1>
        <p className="text-sm text-slate-500 mt-1" data-testid="commission-invoice-subtitle">
          {isFr
            ? `Annonce: ${invoice.listing_title || invoice.listing_id} · Type de vendeur: ${invoice.seller_type}`
            : `Listing: ${invoice.listing_title || invoice.listing_id} · Seller type: ${invoice.seller_type}`}
        </p>
      </div>

      {paid && (
        <Alert data-testid="commission-invoice-paid-alert" className="border-emerald-300 bg-emerald-50">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertDescription>
            {isFr ? 'Commission déjà payée.' : 'Commission already paid.'}
          </AlertDescription>
        </Alert>
      )}

      {/* Invoice lines */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {isFr ? 'Détail de la facture' : 'Invoice Detail'}
            <Badge variant="outline" className="ml-2 text-xs" data-testid="commission-rate-badge">
              {(Number(invoice.seller_commission_rate) * 100).toFixed(1)}%
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between" data-testid="line-hammer">
            <span>{isFr ? 'Prix au marteau' : 'Hammer Price'}</span>
            <span>{fmt(invoice.hammer_cents)}</span>
          </div>
          <div className="flex justify-between" data-testid="line-commission">
            <span>{isFr ? 'Commission BidVex' : 'BidVex Commission'} ({(Number(invoice.seller_commission_rate) * 100).toFixed(1)}%)</span>
            <span data-testid="line-commission-amount">{fmt(invoice.seller_commission_cents)}</span>
          </div>
          <div className="flex justify-between" data-testid="line-taxes">
            <span>
              {isFr ? 'Taxes' : 'Taxes'} (
              {invoice.taxes.hst_cents > 0
                ? 'HST'
                : `TPS ${fmt(invoice.taxes.gst_cents)} + TVQ ${fmt(invoice.taxes.qst_cents)}`}
              )
            </span>
            <span data-testid="line-taxes-amount">{fmt(invoice.tax_total_cents)}</span>
          </div>
          <div className="flex justify-between" data-testid="line-stripe-recovery">
            <span>
              {isFr ? 'Frais de traitement du paiement' : 'Payment Processing Fee'}
              {payMethod === 'stripe' ? (
                <span className="text-xs text-slate-500 ml-1">
                  {isFr ? '(Stripe 2,9 % + 0,30 $ – gross-up)' : '(Stripe 2.9% + $0.30 — gross-up)'}
                </span>
              ) : (
                <span className="text-xs text-slate-500 ml-1">
                  ({isFr ? 'Hors ligne — 0 $' : 'Offline — $0'})
                </span>
              )}
            </span>
            <span data-testid="line-stripe-recovery-amount">{fmt(row.stripe_recovery_cents)}</span>
          </div>
          <div className="border-t pt-2 flex justify-between font-bold text-base" data-testid="line-total">
            <span>{isFr ? 'TOTAL À PAYER' : 'TOTAL OWED'}</span>
            <span data-testid="line-total-amount">{fmt(row.total_cents)}</span>
          </div>
        </CardContent>
      </Card>

      {/* Payment method */}
      {!paid && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {isFr ? 'Méthode de paiement' : 'Payment Method'}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              { v: 'stripe', label: isFr ? 'Carte de crédit / débit (Stripe)' : 'Credit / Debit Card (Stripe)', icon: <CreditCard className="h-4 w-4" /> },
              { v: 'etransfer', label: isFr ? 'Virement Interac' : 'Interac E-Transfer', icon: <Send className="h-4 w-4" /> },
              { v: 'cash', label: isFr ? 'Comptant' : 'Cash', icon: <Banknote className="h-4 w-4" /> },
              { v: 'cheque', label: isFr ? 'Chèque' : 'Cheque', icon: <FileText className="h-4 w-4" /> },
            ].map((opt) => (
              <label
                key={opt.v}
                data-testid={`pay-method-${opt.v}`}
                className={`flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer ${
                  payMethod === opt.v ? 'border-blue-500 bg-blue-50/40' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <input
                  type="radio"
                  name="pay-method"
                  value={opt.v}
                  checked={payMethod === opt.v}
                  onChange={() => setPayMethod(opt.v)}
                />
                {opt.icon}
                <span className="text-sm">{opt.label}</span>
              </label>
            ))}

            <Button
              className="w-full h-11 mt-3"
              onClick={payNow}
              disabled={submitting}
              data-testid="pay-now-btn"
            >
              {submitting ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {isFr ? 'Traitement…' : 'Processing…'}</>
              ) : (
                <>{isFr ? 'PAYER MAINTENANT' : 'PAY NOW'} · {fmt(row.total_cents)}</>
              )}
            </Button>

            {invoice._offline_instructions && (
              <Alert data-testid="offline-instructions" className="mt-3">
                <AlertDescription>{invoice._offline_instructions}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
