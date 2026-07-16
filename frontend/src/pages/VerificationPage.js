/**
 * iter355 H-1 — Stripe Identity Verification Page (Bidder KYC).
 *
 * Entry points:
 *   1. Direct nav to /verify-identity from Profile / anywhere.
 *   2. Deep-linked from Checkout when settlement returns
 *      403 IDENTITY_VERIFICATION_REQUIRED.
 *
 * Flow:
 *   1. Call POST /api/identity/verify → { client_secret, status, url }.
 *   2. Use @stripe/stripe-js `stripe.verifyIdentity(client_secret)`
 *      to open the embedded Stripe Identity modal.
 *   3. After the modal closes, POLL /api/identity/status every 4s until
 *      `is_identity_verified === true` OR user cancels.
 *   4. On success, either redirect back to the origin (?return_to=...)
 *      or show a big Verified card with CTA to Profile.
 *
 * The Stripe webhook is the single source of truth — this page only
 * displays state. Local polling is for immediate UX responsiveness.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { loadStripe } from '@stripe/stripe-js';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { ShieldCheck, IdCard, Loader2, AlertTriangle, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import API_BASE from '../config';

const API = API_BASE;
const stripePromise = process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY
  ? loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY)
  : null;

const POLL_INTERVAL_MS = 4000;
const POLL_MAX_ATTEMPTS = 45; // 3 minutes.

const authHeaders = () => {
  const token =
    localStorage.getItem('token') ||
    localStorage.getItem('bidvex_token') ||
    localStorage.getItem('bidvex_session_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export default function VerificationPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const returnTo = params.get('return_to') || '/dashboard';
  const [status, setStatus] = useState('loading'); // loading|idle|opening|processing|verified|failed
  const [errorMsg, setErrorMsg] = useState(null);
  const [session, setSession] = useState(null);
  const [pollAttempts, setPollAttempts] = useState(0);
  const pollTimerRef = useRef(null);

  // Fetch current KYC state on mount.
  const fetchStatus = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/identity/status`, { headers: authHeaders() });
      if (r.data.is_identity_verified) {
        setStatus('verified');
        return true;
      }
      // If they've already got an in-flight session, expose it so
      // the "resume" button is available.
      if (r.data.stripe_identity_status) {
        setSession({
          status: r.data.stripe_identity_status,
          last_error_reason: r.data.last_error_reason,
        });
      }
      setStatus((s) => (s === 'loading' ? 'idle' : s));
      return false;
    } catch (e) {
      if (e?.response?.status === 401) {
        navigate('/auth?next=/verify-identity');
        return false;
      }
      setStatus('idle');
      return false;
    }
  }, [navigate]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const pollUntilVerified = useCallback((attempt = 0) => {
    if (attempt >= POLL_MAX_ATTEMPTS) {
      setStatus('processing');
      stopPolling();
      return;
    }
    pollTimerRef.current = setTimeout(async () => {
      const done = await fetchStatus();
      setPollAttempts(attempt + 1);
      if (!done) pollUntilVerified(attempt + 1);
    }, POLL_INTERVAL_MS);
  }, [fetchStatus, stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  // Redirect if verified and a return_to is provided.
  useEffect(() => {
    if (status === 'verified' && returnTo && returnTo !== window.location.pathname) {
      const t = setTimeout(() => navigate(returnTo), 1800);
      return () => clearTimeout(t);
    }
  }, [status, returnTo, navigate]);

  const startVerification = async () => {
    if (!stripePromise) {
      setErrorMsg('Stripe is not configured. Please contact support.');
      setStatus('failed');
      return;
    }
    setStatus('opening');
    setErrorMsg(null);
    try {
      const r = await axios.post(
        `${API}/api/identity/verify`,
        { return_url: window.location.origin + '/verify-identity?return_to=' + encodeURIComponent(returnTo) },
        { headers: authHeaders() },
      );
      if (r.data.already_verified) {
        setStatus('verified');
        toast.success('Identity already verified.');
        return;
      }
      const clientSecret = r.data.client_secret;
      setSession({ status: r.data.status });
      const stripe = await stripePromise;
      if (!stripe) throw new Error('Stripe.js failed to load');
      const { error } = await stripe.verifyIdentity(clientSecret);
      if (error) {
        console.warn('[verifyIdentity] error', error);
        setErrorMsg(error.message || 'Verification could not complete.');
        setStatus('failed');
        return;
      }
      // Modal closed OK — start polling for webhook confirmation.
      setStatus('processing');
      pollUntilVerified(0);
    } catch (e) {
      console.error('[verify] failed', e);
      const detail = e?.response?.data?.detail;
      const msg =
        (detail && typeof detail === 'object'
          ? detail.message_en || detail.error
          : detail) ||
        e.message ||
        'Could not start verification.';
      setErrorMsg(msg);
      setStatus('failed');
    }
  };

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 py-12 px-4"
      data-testid="verification-page"
    >
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-700 px-4 py-1.5 rounded-full text-xs font-semibold mb-4">
            <ShieldCheck className="h-3.5 w-3.5" />
            BidVex KYC · Vérification d&apos;identité
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 tracking-tight">
            Verify your identity
          </h1>
          <p className="mt-3 text-slate-600 text-base sm:text-lg">
            One-time check to confirm you are who you say you are — required
            before finalizing your winning bid.
          </p>
        </div>

        {status === 'verified' && (
          <Card className="border-emerald-200 bg-emerald-50 shadow-sm" data-testid="verify-state-verified">
            <CardContent className="p-8 text-center">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 mb-4">
                <ShieldCheck className="h-8 w-8 text-emerald-600" />
              </div>
              <h2 className="text-2xl font-bold text-emerald-900 mb-2">
                Verified ✓
              </h2>
              <p className="text-emerald-800 text-sm mb-6">
                Your identity has been confirmed. You can now claim winning
                auctions without interruption.
              </p>
              <Button
                onClick={() => navigate(returnTo)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
                data-testid="verify-continue-btn"
              >
                Continue{returnTo === '/dashboard' ? ' to Dashboard' : ''}
              </Button>
            </CardContent>
          </Card>
        )}

        {status === 'processing' && (
          <Card className="border-blue-200 bg-blue-50 shadow-sm" data-testid="verify-state-processing">
            <CardContent className="p-8 text-center">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 mb-4">
                <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
              </div>
              <h2 className="text-2xl font-bold text-blue-900 mb-2">
                Almost there…
              </h2>
              <p className="text-blue-800 text-sm">
                Stripe is reviewing your submission. Verification typically
                completes within a minute.
                {pollAttempts > 0 && (
                  <span className="block mt-1 text-xs">
                    (checked {pollAttempts}× · we&apos;ll refresh automatically)
                  </span>
                )}
              </p>
            </CardContent>
          </Card>
        )}

        {(status === 'idle' || status === 'opening' || status === 'failed' || status === 'loading') && (
          <Card className="shadow-sm border-slate-200" data-testid="verify-state-idle">
            <CardContent className="p-8">
              <div className="flex items-start gap-4 mb-6">
                <div className="flex-shrink-0 h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                  <IdCard className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 mb-1">
                    What you&apos;ll need
                  </h2>
                  <ul className="text-sm text-slate-700 space-y-1.5">
                    <li className="flex items-start gap-2">
                      <span className="text-blue-600 mt-0.5">•</span>
                      <span>A government-issued photo ID (driver&apos;s license, passport, or ID card)</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-600 mt-0.5">•</span>
                      <span>A device with a camera (phone or laptop webcam)</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-600 mt-0.5">•</span>
                      <span>About 90 seconds of your time</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-6">
                <div className="flex items-start gap-3">
                  <Sparkles className="h-5 w-5 text-slate-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-slate-700">
                    <p className="font-medium mb-1">Powered by Stripe Identity</p>
                    <p className="text-slate-600">
                      Your ID is encrypted and reviewed by Stripe, a PCI-DSS
                      Level 1 provider. BidVex never sees or stores your ID —
                      we only receive a verified/not-verified signal.
                    </p>
                  </div>
                </div>
              </div>

              {errorMsg && (
                <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 mb-4 flex items-start gap-2" data-testid="verify-error">
                  <AlertTriangle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-rose-800">{errorMsg}</p>
                </div>
              )}

              {session?.last_error_reason && status === 'idle' && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-900">
                  <p className="font-semibold mb-0.5">
                    Previous attempt: {session.last_error_reason.replace(/_/g, ' ')}
                  </p>
                  <p className="text-amber-800 text-xs">
                    Please try again with a clearer photo of your ID.
                  </p>
                </div>
              )}

              <Button
                onClick={startVerification}
                disabled={status === 'opening' || status === 'loading'}
                className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white h-11 text-base font-semibold"
                data-testid="verify-start-btn"
              >
                {status === 'opening' ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Opening secure Stripe verification…
                  </>
                ) : status === 'loading' ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Checking status…
                  </>
                ) : session?.status === 'requires_input' ? (
                  <>Resume verification →</>
                ) : (
                  <>
                    <ShieldCheck className="h-4 w-4 mr-2" />
                    Start verification
                  </>
                )}
              </Button>

              <p className="text-xs text-slate-500 text-center mt-4">
                Bilingual · Bilingue · <button onClick={() => navigate(returnTo)} className="text-slate-600 underline hover:text-slate-800" data-testid="verify-skip-btn">Skip for now</button>
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
