/**
 * VehicleUnlockPage — iter194
 * Winning bidder lands here after auction close. Shows fee breakdown,
 * collects 2.5% net (Stripe fees grossed up), then reveals dealer contact.
 * Routed via /vehicle-auctions/:id/unlock
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Loader2, Lock, CheckCircle2, ArrowLeft, CreditCard, Phone, Mail, MapPin, Building2, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const API = API_BASE;
const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

const PaymentForm = ({ quote, listingId, onSuccess }) => {
  const { t } = useTranslation();
  const stripe = useStripe();
  const elements = useElements();
  const { token } = useAuth();
  const [processing, setProcessing] = useState(false);

  const handlePay = async () => {
    if (!stripe || !elements) return;
    setProcessing(true);
    try {
      // Create PaymentIntent on backend
      const checkoutRes = await axios.post(
        `${API}/vehicles/${listingId}/unlock-fee/checkout`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const { client_secret, payment_intent_id } = checkoutRes.data;

      // Confirm card payment
      const card = elements.getElement(CardElement);
      const result = await stripe.confirmCardPayment(client_secret, {
        payment_method: { card },
      });
      if (result.error) {
        toast.error(result.error.message);
        setProcessing(false);
        return;
      }

      // Confirm with backend (sets unlock_paid_at)
      await axios.post(
        `${API}/vehicles/${listingId}/unlock-fee/confirm`,
        { payment_intent_id },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(t('vehicleDealer.unlockSuccess'));
      onSuccess();
    } catch (err) {
      const msg = err?.response?.data?.detail || err.message || 'Payment failed';
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-md border bg-slate-50 dark:bg-slate-900/50 p-4 space-y-1">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{t('vehicleDealer.winningBid')}</span>
          <span className="font-semibold">${quote.winning_bid.toFixed(2)} {quote.currency}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{t('vehicleDealer.platformFeeLabel')}</span>
          <span className="font-semibold">${quote.platform_fee_net.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{t('vehicleDealer.stripeFeeLabel')}</span>
          <span className="font-semibold">${quote.stripe_processing_fee.toFixed(2)}</span>
        </div>
        <div className="border-t my-2" />
        <div className="flex justify-between">
          <span className="font-bold">{t('vehicleDealer.totalToPay')}</span>
          <span className="font-black text-xl">${quote.total_charge_to_buyer.toFixed(2)} {quote.currency}</span>
        </div>
      </div>

      {/* Mandatory bilingual disclosure */}
      <div className="p-3 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/30">
        <div className="flex gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-900 dark:text-amber-200">{t('vehicleDealer.unlockNotice')}</p>
        </div>
      </div>

      <div className="rounded-md border border-slate-300 bg-white p-3">
        <label className="text-xs font-medium mb-2 block flex items-center gap-1">
          <CreditCard className="h-3 w-3" />
          {t('storage.depositBanner.cardDetailsLabel')}
        </label>
        <CardElement
          options={{
            style: {
              base: { fontSize: '15px', color: '#1e293b', '::placeholder': { color: '#94a3b8' } },
              invalid: { color: '#dc2626' },
            },
          }}
        />
      </div>

      <Button
        onClick={handlePay}
        disabled={processing || !stripe}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3"
        data-testid="unlock-fee-pay-btn"
      >
        {processing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Lock className="h-4 w-4 mr-2" />}
        {processing ? t('vehicleDealer.processing') : t('vehicleDealer.payAndUnlock')}
      </Button>
    </div>
  );
};

const ContactReveal = ({ contact }) => {
  const { t } = useTranslation();
  return (
    <Card className="border-emerald-300" data-testid="dealer-contact-reveal">
      <CardHeader className="bg-emerald-50 dark:bg-emerald-950/30">
        <CardTitle className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          {t('vehicleDealer.contactRevealTitle')}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <Field label={t('vehicleDealer.contactName')} value={contact.seller_name} />
        {contact.seller_business_name && (
          <Field icon={<Building2 className="h-4 w-4" />} label={t('vehicleDealer.businessName')} value={contact.seller_business_name} />
        )}
        {contact.seller_phone && (
          <Field icon={<Phone className="h-4 w-4" />} label={t('vehicleDealer.phone')} value={contact.seller_phone} />
        )}
        {contact.seller_email && (
          <Field icon={<Mail className="h-4 w-4" />} label={t('vehicleDealer.email')} value={contact.seller_email} />
        )}
        <Field
          icon={<MapPin className="h-4 w-4" />}
          label={t('vehicleDealer.pickupAddress')}
          value={[contact.pickup_address, contact.pickup_city, contact.pickup_province, contact.pickup_postal_code].filter(Boolean).join(', ')}
        />
        {contact.additional_notes && (
          <Field label={t('vehicleDealer.additionalNotes')} value={contact.additional_notes} />
        )}
        <div className="mt-4 p-3 rounded-md bg-slate-100 dark:bg-slate-800 text-xs text-slate-700 dark:text-slate-300">
          <p>{t('vehicleDealer.contactRevealReminder')}</p>
        </div>
      </CardContent>
    </Card>
  );
};

const Field = ({ icon, label, value }) => (
  <div className="flex items-start gap-2 py-1.5 border-b last:border-b-0">
    {icon && <span className="text-muted-foreground mt-0.5">{icon}</span>}
    <div className="flex-1">
      <p className="text-xs uppercase text-muted-foreground tracking-wide">{label}</p>
      <p className="text-sm font-semibold mt-0.5" data-testid={`dealer-contact-${label.toLowerCase().replace(/\s+/g, '-')}`}>{value || '—'}</p>
    </div>
  </div>
);


const VehicleUnlockPage = () => {
  const { id } = useParams();
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [quote, setQuote] = useState(null);
  const [contact, setContact] = useState(null);

  const fetchState = async () => {
    setLoading(true);
    try {
      // Try contact first — if 200, fee already paid
      try {
        const contactRes = await axios.get(`${API}/vehicles/${id}/dealer-contact`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setContact(contactRes.data);
      } catch (err) {
        if (err?.response?.status === 402) {
          // Need to pay → fetch quote
          const quoteRes = await axios.get(`${API}/vehicles/${id}/unlock-quote`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          setQuote(quoteRes.data);
        } else {
          throw err;
        }
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message_en : (detail || 'Error loading');
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) {
      navigate('/auth');
      return;
    }
    fetchState();
  }, [id, token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="vehicle-unlock-page">
      <div className="max-w-2xl mx-auto px-4">
        <Link
          to={`/vehicle-auctions/${id}`}
          className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3"
          data-testid="unlock-back-link"
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back to listing
        </Link>

        {contact ? (
          <ContactReveal contact={contact} />
        ) : quote ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lock className="h-5 w-5 text-blue-600" />
                {t('vehicleDealer.unlockTitle')}
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">{t('vehicleDealer.unlockSubtitle')}</p>
            </CardHeader>
            <CardContent>
              <Elements stripe={stripePromise}>
                <PaymentForm quote={quote} listingId={id} onSuccess={fetchState} />
              </Elements>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              No unlock data available. Please make sure you are the winning bidder.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default VehicleUnlockPage;
