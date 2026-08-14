import API_BASE from '../config';
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import confetti from 'canvas-confetti';
import { formatCurrency } from '../utils/currencyFormatter';
import { useMetaPixelTracking } from '../hooks/useMetaPixelTracking';
import { useAuth } from '../contexts/AuthContext';

const API = API_BASE;

const PaymentSuccessPage = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('processing');
  const [paymentInfo, setPaymentInfo] = useState(null);
  const sessionId = searchParams.get('session_id');
  // iter230 — centralized Meta Pixel tracking hook
  const { trackPurchase } = useMetaPixelTracking();
  // P7.5 — currently signed-in user, used for Google Enhanced Conversions
  // (SHA-256-hashed email/phone shipped with the purchase event).
  const { user } = useAuth();

  useEffect(() => {
    if (sessionId) {
      checkPaymentStatus();
    } else {
      setStatus('error');
    }
  }, [sessionId]);

  const checkPaymentStatus = async () => {
    let attempts = 0;
    const maxAttempts = 5;
    const pollInterval = 2000;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        setStatus('timeout');
        return;
      }

      try {
        const token = localStorage.getItem('token');
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const response = await axios.get(`${API}/payments/status/${sessionId}`, { headers });
        const data = response.data;
        setPaymentInfo(data);

        if (data.payment_status === 'paid') {
          setStatus('success');
          confetti({
            particleCount: 150,
            spread: 100,
            origin: { y: 0.6 },
            colors: ['#F05A4F', '#30C7B5', '#FFD700']
          });
          // Meta Pixel Purchase event. The backend CAPI fires the matching
          // server-side Purchase with the SAME event_id so Meta deduplicates
          // (max 1 attributed conversion per session). content_ids resolve
          // via the canonical helper so they match the catalog feed exactly.
          //
          // P7.5 — Also emits GA4 `purchase` + optional Google Ads Purchase
          // conversion + Enhanced Conversions user_data (hashed email/phone).
          //
          // P7.5 POST-VERIFICATION FIX — The backend `analytics_tracker.py`
          // computes the CAPI `event_id` as
          // `bidvex_purchase_<CID>_session_<session_id>`. The frontend used
          // to rebuild the id locally with the raw session_id (missing the
          // `session_` prefix), which BROKE Meta browser↔CAPI dedup. We now
          // pass the backend-computed `meta_purchase_event_id` directly to
          // the tracking hook so the browser Pixel and CAPI share the exact
          // same event_id (byte-identical).
          try {
            const meta = data.metadata || {};
            const listingId =
              data.listing_id ||
              meta.listing_id ||
              meta.multi_item_listing_id ||
              meta.auction_id;
            const listingType =
              data.listing_type ||
              meta.listing_type ||
              (meta.multi_item_listing_id ? 'multi_lot' : 'marketplace');
            const finalWinningPrice = (data.amount_total || 0) / 100;
            // The Stripe Checkout session id (cs_...) is still needed by
            // GA4 `transaction_id` (Google's own dedupe key). Meta's dedup
            // key is the authoritative backend `meta_purchase_event_id`.
            const stripeSessionId = sessionId;
            const serverEventId = data.meta_purchase_event_id;
            if (listingId) {
              trackPurchase({
                listingId,
                listingType,
                finalWinningPrice,
                stripeSessionId,
                serverEventId,
                title:    data.listing_title    || meta.listing_title,
                category: data.listing_category || meta.listing_category,
                identity: user
                  ? { email: user.email, phone: user.phone }
                  : undefined,
                // Multi-lot / vehicle-multi-lot lots carry a distinct
                // catalog id — when the backend supplies it via
                // `data.meta_content_id`, use it verbatim so GA4 +
                // Meta both attribute to the exact catalog row.
                lotContentId: data.meta_content_id || meta.meta_content_id,
              });
            }
          } catch (e) { /* silent — pixel must never block the success flow */ }
          return;
        } else if (data.status === 'expired') {
          setStatus('expired');
          return;
        }

        attempts++;
        setTimeout(poll, pollInterval);
      } catch (error) {
        console.error('Error checking payment status:', error);
        setStatus('error');
      }
    };

    poll();
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12" data-testid="payment-success-page">
      <Card className="w-full max-w-md glassmorphism">
        <CardContent className="p-8 text-center space-y-6">
          {status === 'processing' && (
            <>
              <Loader2 className="h-16 w-16 mx-auto text-primary animate-spin" />
              <h2 className="text-2xl font-bold">{t('paymentSuccess.processing', 'Processing Payment')}</h2>
              <p className="text-muted-foreground">
                {t('paymentSuccess.pleaseWait', 'Please wait while we confirm your payment...')}
              </p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle2 className="h-16 w-16 mx-auto text-green-500" data-testid="success-icon" />
              <h2 className="text-2xl font-bold">{t('paymentSuccess.title')}</h2>
              <p className="text-muted-foreground">
                {t('paymentSuccess.thankYou')}. {t('paymentSuccess.step2')}
              </p>
              {paymentInfo && (
                <div className="bg-accent/20 rounded-lg p-4 text-sm space-y-1">
                  <p><span className="font-medium">{t('paymentSuccess.amountPaid')}:</span> {formatCurrency(paymentInfo.amount_total / 100)}</p>
                  <p><span className="font-medium">{t('common.status', 'Status')}:</span> {paymentInfo.payment_status}</p>
                </div>
              )}

              {/* Post-Sale Contact Info — Seller (Phase 3, Option A) */}
              {paymentInfo?.seller_contact && (
                <div
                  className="text-left rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 p-4"
                  data-testid="checkout-seller-contact"
                >
                  <p className="text-xs uppercase font-semibold text-blue-800 dark:text-blue-300 mb-2">
                    Contact Seller / Contacter le vendeur
                  </p>
                  <dl className="text-sm space-y-1">
                    <div className="flex justify-between"><dt className="text-muted-foreground">Name</dt><dd className="font-medium">{paymentInfo.seller_contact.name || '—'}</dd></div>
                    <div className="flex justify-between"><dt className="text-muted-foreground">Email</dt><dd className="font-medium"><a className="text-blue-600 hover:underline" href={`mailto:${paymentInfo.seller_contact.email}`}>{paymentInfo.seller_contact.email || '—'}</a></dd></div>
                    <div className="flex justify-between"><dt className="text-muted-foreground">Phone</dt><dd className="font-medium">{paymentInfo.seller_contact.phone ? <a className="text-blue-600 hover:underline" href={`tel:${paymentInfo.seller_contact.phone}`}>{paymentInfo.seller_contact.phone}</a> : '—'}</dd></div>
                  </dl>
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={() => navigate('/buyer/dashboard')}
                  className="gradient-button text-white border-0 flex-1"
                  data-testid="view-dashboard-btn"
                >
                  {t('paymentSuccess.viewOrder')}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate('/marketplace')}
                  className="flex-1"
                >
                  {t('paymentSuccess.continueShop')}
                </Button>
              </div>
            </>
          )}

          {status === 'error' && (
            <>
              <AlertCircle className="h-16 w-16 mx-auto text-red-500" />
              <h2 className="text-2xl font-bold">{t('errors.paymentError', 'Payment Error')}</h2>
              <p className="text-muted-foreground">
                {t('errors.paymentErrorDesc', 'There was an error processing your payment. Please try again or contact support.')}
              </p>
              <Button
                onClick={() => navigate('/marketplace')}
                className="gradient-button text-white border-0 w-full"
              >
                {t('paymentSuccess.backToMarketplace')}
              </Button>
            </>
          )}

          {status === 'timeout' && (
            <>
              <AlertCircle className="h-16 w-16 mx-auto text-orange-500" />
              <h2 className="text-2xl font-bold">{t('errors.verificationTimeout', 'Payment Verification Timeout')}</h2>
              <p className="text-muted-foreground">
                {t('errors.timeoutDesc', 'We\'re still confirming your payment. Please check your email for confirmation or contact support.')}
              </p>
              <Button
                onClick={() => navigate('/buyer/dashboard')}
                className="gradient-button text-white border-0 w-full"
              >
                {t('paymentSuccess.backToDashboard')}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PaymentSuccessPage;
