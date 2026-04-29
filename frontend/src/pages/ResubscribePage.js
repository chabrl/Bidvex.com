import API_BASE from '../config';
import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Loader2, CheckCircle2, AlertCircle, Mail } from 'lucide-react';

/**
 * BidVex resubscribe page (bilingual EN/FR).
 * Route: /resubscribe?token=...&lang=en|fr
 *
 * Endpoints:
 *   GET  {API}/unsubscribe/resubscribe-verify?token=...
 *   POST {API}/unsubscribe/resubscribe-confirm { token }
 *
 * Uses the SAME signed-token mechanic as the unsubscribe flow
 * (one token can be used in either direction by design).
 */
const ResubscribePage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const langParam = searchParams.get('lang');
  const fr = langParam === 'fr';

  const [state, setState] = useState('loading'); // loading | confirm | success | already | error
  const [emailMasked, setEmailMasked] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const API = `${API_BASE}`;

  useEffect(() => {
    if (!token) {
      setErrorCode('token_missing');
      setState('error');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/unsubscribe/resubscribe-verify`, { params: { token } });
        if (cancelled) return;
        setEmailMasked(r.data?.email_masked || '');
        // If they're already subscribed → already-state. Otherwise → confirm.
        setState(r.data?.is_subscribed ? 'already' : 'confirm');
      } catch (err) {
        if (cancelled) return;
        setErrorCode(err?.response?.data?.detail || 'token_invalid');
        setState('error');
      }
    })();
    return () => { cancelled = true; };
  }, [token, API]);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      const r = await axios.post(`${API}/unsubscribe/resubscribe-confirm`, { token });
      setEmailMasked(r.data?.email_masked || emailMasked);
      setState(r.data?.status === 'already_subscribed' ? 'already' : 'success');
    } catch (err) {
      setErrorCode(err?.response?.data?.detail || 'confirm_failed');
      setState('error');
    } finally {
      setSubmitting(false);
    }
  };

  const Shell = ({ children }) => (
    <div
      style={{ fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}
      className="min-h-screen bg-white flex items-start justify-center px-4 pt-16 pb-16"
      data-testid="resubscribe-page"
    >
      <div className="w-full max-w-[520px] rounded-2xl bg-white shadow-[0_4px_24px_rgba(15,23,42,0.06)] border border-slate-100 p-8 md:p-12">
        <div className="flex justify-center mb-8">
          <div className="text-2xl font-bold tracking-tight" style={{ color: '#0f172a' }}>
            Bid<span style={{ background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>Vex</span>
          </div>
        </div>
        {children}
      </div>
    </div>
  );

  if (state === 'loading') {
    return (
      <Shell>
        <div className="flex items-center justify-center py-8" data-testid="resubscribe-loading">
          <Loader2 className="h-8 w-8 animate-spin" style={{ color: '#2563eb' }} />
        </div>
      </Shell>
    );
  }

  if (state === 'confirm') {
    return (
      <Shell>
        <div className="flex justify-center mb-4">
          <Mail className="h-12 w-12" style={{ color: '#2563eb' }} />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold mb-4 text-center" style={{ color: '#0f172a' }}>
          {fr ? 'Réabonnement aux courriels BidVex' : 'Resubscribe to BidVex emails'}
        </h1>
        <p className="text-base mb-8 leading-relaxed text-center" style={{ color: '#334155' }}>
          {fr
            ? <>Vous êtes sur le point de réabonner <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> aux communications marketing de BidVex.</>
            : <>You are about to resubscribe <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> to BidVex marketing communications.</>}
        </p>
        <button
          onClick={handleConfirm}
          disabled={submitting}
          data-testid="confirm-resubscribe-btn"
          className="w-full py-3 px-6 rounded-xl font-semibold text-white transition-all active:scale-[0.98]"
          style={{
            background: submitting
              ? 'linear-gradient(135deg, #93c5fd 0%, #67e8f9 100%)'
              : 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)',
          }}
        >
          {submitting ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {fr ? 'Traitement…' : 'Processing…'}
            </span>
          ) : (fr ? 'Confirmer le réabonnement' : 'Confirm Resubscribe')}
        </button>
        <div className="text-center mt-6">
          <Link to="/" className="text-sm" style={{ color: '#2563eb', textDecoration: 'underline' }} data-testid="resubscribe-cancel-link">
            {fr ? 'Annuler, me ramener' : 'Never mind, take me back'}
          </Link>
        </div>
      </Shell>
    );
  }

  if (state === 'success' || state === 'already') {
    return (
      <Shell>
        <div className="flex justify-center mb-4">
          <CheckCircle2 className="h-16 w-16" style={{ color: '#10b981' }} data-testid="resubscribe-success-icon" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-center mb-4" style={{ color: '#0f172a' }}>
          {state === 'already'
            ? (fr ? 'Vous êtes déjà abonné.' : "You're already subscribed.")
            : (fr ? 'Vous êtes réabonné.' : "You're subscribed again.")}
        </h1>
        <p className="text-base mb-4 leading-relaxed text-center" style={{ color: '#334155' }}>
          {fr
            ? <>Bon retour. <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> recevra à nouveau les courriels promotionnels de BidVex.</>
            : <>Welcome back. <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> will receive BidVex promotional emails again.</>}
        </p>
        <p className="text-sm mb-8 leading-relaxed text-center" style={{ color: '#64748b' }}>
          {fr
            ? "Vous pouvez vous désabonner à tout moment depuis n'importe quel courriel."
            : 'You can unsubscribe at any time from any email.'}
        </p>
        <div className="text-center">
          <Link to="/"
                className="inline-block py-3 px-6 rounded-xl font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)' }}
                data-testid="resubscribe-home-link">
            {fr ? 'Retour à BidVex' : 'Back to BidVex'}
          </Link>
        </div>
      </Shell>
    );
  }

  // error
  return (
    <Shell>
      <div className="flex justify-center mb-4">
        <AlertCircle className="h-16 w-16" style={{ color: '#dc2626' }} data-testid="resubscribe-error-icon" />
      </div>
      <h1 className="text-xl md:text-2xl font-bold text-center mb-4" style={{ color: '#0f172a' }}>
        {fr ? 'Lien invalide ou expiré' : 'Invalid or expired link'}
      </h1>
      <p className="text-base leading-relaxed text-center" style={{ color: '#334155' }}>
        {fr
          ? <>Ce lien de réabonnement est invalide ou expiré. Contactez <a href="mailto:support@bidvex.com" style={{ color: '#2563eb', textDecoration: 'underline' }}>support@bidvex.com</a> si vous avez besoin d'aide.</>
          : <>This resubscribe link is invalid or has expired. Please contact <a href="mailto:support@bidvex.com" style={{ color: '#2563eb', textDecoration: 'underline' }}>support@bidvex.com</a> if you need assistance.</>}
      </p>
      {errorCode && (
        <p className="text-xs mt-4 text-center font-mono" style={{ color: '#94a3b8' }}>
          {errorCode}
        </p>
      )}
    </Shell>
  );
};

export default ResubscribePage;
