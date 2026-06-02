/**
 * iter261 Mission 1 — Stripe success-landing handshake page.
 *
 * Loaded when Stripe redirects after a successful Checkout. On mount,
 * fires `POST /api/pay/:id/confirm-success` (idempotent) so the
 * payment_request flips to `paid` even if the webhook is delayed.
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Helmet } from 'react-helmet-async';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import API_BASE from '../config';

const PaymentSuccessPage = () => {
  const { payment_request_id: paymentRequestId } = useParams();
  const navigate = useNavigate();
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await axios.post(`${API_BASE}/pay/${paymentRequestId}/confirm-success`);
      } catch {
        // Idempotent. Webhook will catch it.
      } finally {
        if (!cancelled) setConfirmed(true);
      }
    })();
    return () => { cancelled = true; };
  }, [paymentRequestId]);

  return (
    <div className="min-h-screen bg-slate-50 py-16 px-4" data-testid="payment-success-page">
      <Helmet>
        <title>Payment Successful — BidVex</title>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>
      <div className="max-w-md mx-auto bg-white border border-slate-200 rounded-2xl shadow-sm p-8 text-center">
        {!confirmed ? (
          <div data-testid="payment-success-confirming">
            <Loader2 className="h-10 w-10 mx-auto text-emerald-500 animate-spin mb-3" />
            <p className="text-sm text-slate-500">Confirming your payment…</p>
          </div>
        ) : (
          <>
            <CheckCircle2 className="h-16 w-16 mx-auto text-emerald-500 mb-4" />
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              Payment Successful!
            </h1>
            <p className="text-sm text-slate-600 mb-1">
              Thank you — your payment has been received.
            </p>
            <p className="text-xs text-slate-500 mb-6">
              A confirmation email has been sent to your inbox.
            </p>
            <Button
              className="w-full"
              style={{ backgroundColor: '#0055FF', color: 'white' }}
              onClick={() => navigate('/dashboard')}
              data-testid="payment-success-goto-dashboard"
            >
              Go to My Dashboard
            </Button>
          </>
        )}
      </div>
    </div>
  );
};

export default PaymentSuccessPage;
