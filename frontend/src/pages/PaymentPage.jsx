/**
 * iter261 Mission 1 — BidVex-hosted Payment Page.
 *
 * Public, no-auth route at /pay/:payment_request_id. The email's
 * "Pay Now" button always lands here (even when Stripe is misconfigured)
 * so users always have a way to complete an admin-issued payment.
 *
 * Flow:
 *   1. GET /api/pay/:id            — fetch the payment payload
 *   2. If status === paid           → show "already paid" screen
 *   3. If status === expired        → show expired screen
 *   4. Otherwise show Pay Now CTA. On click:
 *      - If stripe_payment_link is present, redirect straight to it
 *      - Else POST /api/pay/:id/checkout-session and redirect to
 *        the on-the-fly Checkout URL
 *      - If both fail, show manual_instructions modal
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Helmet } from 'react-helmet-async';
import { Loader2, CreditCard, ShieldCheck, AlertTriangle, Copy, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import API_BASE from '../config';

const fmtMoney = (n) => `$${Number(n || 0).toFixed(2)} CAD`;

const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-CA', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZone: 'UTC',
    }) + ' UTC';
  } catch {
    return iso;
  }
};

const PaymentPage = () => {
  const { payment_request_id: paymentRequestId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pr, setPr] = useState(null);
  const [paying, setPaying] = useState(false);
  const [manualMsg, setManualMsg] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await axios.get(`${API_BASE}/pay/${paymentRequestId}`);
      setPr(r.data);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || 'This payment link is no longer valid.');
    } finally {
      setLoading(false);
    }
  }, [paymentRequestId]);

  useEffect(() => { load(); }, [load]);

  const handlePay = async () => {
    if (!pr) return;
    setPaying(true);
    // Prefer the pre-issued Stripe Payment Link when present.
    if (pr.stripe_payment_link) {
      window.location.href = pr.stripe_payment_link;
      return;
    }
    try {
      const r = await axios.post(`${API_BASE}/pay/${paymentRequestId}/checkout-session`);
      if (r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
        return;
      }
      setManualMsg(r.data?.manual_instructions || 'Please contact support@bidvex.com to arrange payment.');
    } catch (e) {
      setManualMsg(e?.response?.data?.detail || 'Failed to initiate checkout. Please contact support.');
    } finally {
      setPaying(false);
    }
  };

  const copyRef = async () => {
    try { await navigator.clipboard.writeText(paymentRequestId); toast.success('Reference ID copied'); }
    catch { /* noop */ }
  };

  // ─── render ────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4" data-testid="payment-page">
      <Helmet>
        <title>Payment — BidVex</title>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>
      <div className="max-w-md mx-auto bg-white border border-slate-200 rounded-2xl shadow-sm p-8">
        <div className="flex items-center gap-3 mb-6">
          <span className="text-2xl font-extrabold text-[#0055FF] tracking-tight">BidVex</span>
        </div>

        {loading && (
          <div className="text-center py-10" data-testid="payment-page-loading">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-slate-400" />
            <p className="text-sm text-slate-500 mt-3">Loading payment details…</p>
          </div>
        )}

        {!loading && (error || !pr) && (
          <div className="text-center py-6" data-testid="payment-page-error">
            <AlertTriangle className="h-10 w-10 mx-auto text-rose-500 mb-3" />
            <h2 className="text-lg font-bold text-slate-900 mb-2">Payment Link Invalid</h2>
            <p className="text-sm text-slate-600 mb-4">
              {error || 'This payment link is no longer valid or has expired.'}
            </p>
            <Button asChild variant="outline" data-testid="payment-page-contact">
              <a href="mailto:support@bidvex.com">
                <Mail className="h-3.5 w-3.5 mr-1.5" />
                Contact Support
              </a>
            </Button>
          </div>
        )}

        {!loading && pr && pr.status === 'paid' && (
          <div className="text-center py-6" data-testid="payment-page-paid">
            <div className="text-5xl mb-3">✅</div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">Payment Already Completed</h2>
            <p className="text-sm text-slate-600 mb-4">
              This payment has been completed. Thank you!
            </p>
            <Button onClick={() => navigate('/marketplace')} data-testid="payment-page-goto-marketplace">
              Go to Marketplace
            </Button>
          </div>
        )}

        {!loading && pr && pr.status === 'expired' && (
          <div className="text-center py-6" data-testid="payment-page-expired">
            <AlertTriangle className="h-10 w-10 mx-auto text-amber-500 mb-3" />
            <h2 className="text-lg font-bold text-slate-900 mb-2">Payment Link Expired</h2>
            <p className="text-sm text-slate-600 mb-4">
              This payment link has expired. Please reach out to support to issue a new one.
            </p>
            <Button asChild variant="outline" data-testid="payment-page-expired-contact">
              <a href="mailto:support@bidvex.com">Contact Support</a>
            </Button>
          </div>
        )}

        {!loading && pr && pr.status === 'pending' && (
          <div data-testid="payment-page-active">
            <div className="flex items-center gap-2 mb-1">
              <CreditCard className="h-5 w-5 text-[#0055FF]" />
              <h1 className="text-lg font-bold text-slate-900">Payment Request</h1>
            </div>
            <p className="text-xs text-slate-500 mb-6">Complete your payment securely below.</p>
            <dl className="space-y-3 text-sm border-y border-slate-100 py-4 mb-6">
              <div className="flex items-baseline justify-between">
                <dt className="text-slate-500">Amount Due</dt>
                <dd className="font-bold text-2xl text-[#e53e3e]" data-testid="payment-page-amount">
                  {fmtMoney(pr.total_amount)}
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-slate-500 flex-shrink-0">Reason</dt>
                <dd className="font-medium text-slate-900 text-right" data-testid="payment-page-description">
                  {pr.description || '—'}
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-slate-500 flex-shrink-0">Requested by</dt>
                <dd className="text-slate-700">BidVex Admin</dd>
              </div>
              {pr.expires_at && (
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-slate-500 flex-shrink-0">Expires</dt>
                  <dd className="text-slate-700 text-right text-xs">{fmtDate(pr.expires_at)}</dd>
                </div>
              )}
            </dl>
            <Button
              className="w-full h-12 font-bold text-base"
              style={{ backgroundColor: '#0055FF', color: 'white' }}
              onClick={handlePay}
              disabled={paying}
              data-testid="payment-page-pay-now"
            >
              {paying ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CreditCard className="h-4 w-4 mr-2" />}
              {paying ? 'Redirecting to Stripe…' : `Pay Now — ${fmtMoney(pr.total_amount)}`}
            </Button>
            <p className="text-center text-xs text-slate-500 mt-3 flex items-center justify-center gap-1">
              <ShieldCheck className="h-3 w-3" />
              Secured by Stripe
            </p>
          </div>
        )}

        {manualMsg && (
          <div className="mt-4 border border-amber-200 bg-amber-50 rounded-lg p-4 text-sm" data-testid="payment-page-manual-instructions">
            <p className="text-amber-900 mb-3">{manualMsg}</p>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={copyRef} data-testid="payment-page-copy-ref">
                <Copy className="h-3.5 w-3.5 mr-1.5" />
                Copy Reference ID
              </Button>
              <Button asChild size="sm" variant="outline">
                <a href="mailto:support@bidvex.com" data-testid="payment-page-email-support">
                  <Mail className="h-3.5 w-3.5 mr-1.5" />
                  Email Support
                </a>
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PaymentPage;
