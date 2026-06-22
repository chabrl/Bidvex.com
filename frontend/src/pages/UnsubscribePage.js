import API_BASE from '../config';
import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

/**
 * BidVex custom unsubscribe page (bilingual EN/FR).
 *
 * iter309 D4 — Canonical single route:
 *   /unsubscribe?token=<signed>&lang=<en|fr>
 *
 * Legacy alias (still mounted in App.js for emails already in inboxes):
 *   /desabonnement?token=...
 *
 * Endpoints (unified — handle BOTH platform itsdangerous + external JWT tokens):
 *   GET  {API}/unsubscribe/auto-verify?token=...
 *   POST {API}/unsubscribe/auto-confirm { token }
 */
const UnsubscribePage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const langParam = searchParams.get('lang');
  const isFrenchPath = typeof window !== 'undefined' && window.location.pathname.startsWith('/desabonnement');
  const lang = langParam === 'fr' || isFrenchPath ? 'fr' : 'en';
  const fr = lang === 'fr';

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
        const r = await axios.get(`${API}/unsubscribe/auto-verify`, { params: { token } });
        if (cancelled) return;
        setEmailMasked(r.data?.email_masked || '');
        setState(r.data?.already_unsubscribed ? 'already' : 'confirm');
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
      const r = await axios.post(`${API}/unsubscribe/auto-confirm`, { token });
      setEmailMasked(r.data?.email_masked || emailMasked);
      setState(r.data?.status === 'already_done' ? 'already' : 'success');
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
      data-testid="unsubscribe-page"
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
        <div className="flex items-center justify-center py-8" data-testid="unsubscribe-loading">
          <Loader2 className="h-8 w-8 animate-spin" style={{ color: '#2563eb' }} />
        </div>
      </Shell>
    );
  }

  if (state === 'confirm') {
    return (
      <Shell>
        <h1 className="text-2xl md:text-3xl font-bold mb-4" style={{ color: '#0f172a' }}>
          {fr ? 'Se désabonner des courriels BidVex' : 'Unsubscribe from BidVex emails'}
        </h1>
        <p className="text-base mb-8 leading-relaxed" style={{ color: '#334155' }}>
          {fr
            ? <>Vous êtes sur le point de désabonner <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> de toutes les communications marketing de BidVex.</>
            : <>You are about to unsubscribe <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> from all BidVex marketing communications.</>}
        </p>
        <button
          onClick={handleConfirm}
          disabled={submitting}
          data-testid="confirm-unsubscribe-btn"
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
          ) : (fr ? 'Confirmer le désabonnement' : 'Confirm Unsubscribe')}
        </button>
        <div className="text-center mt-6">
          <Link to="/" className="text-sm" style={{ color: '#2563eb', textDecoration: 'underline' }} data-testid="unsubscribe-cancel-link">
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
          <CheckCircle2 className="h-16 w-16" style={{ color: '#10b981' }} data-testid="unsubscribe-success-icon" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-center mb-4" style={{ color: '#0f172a' }}>
          {state === 'already'
            ? (fr ? 'Vous êtes déjà désabonné.' : "You're already unsubscribed.")
            : (fr ? 'Vous êtes désabonné.' : "You've been unsubscribed.")}
        </h1>
        <p className="text-base mb-4 leading-relaxed text-center" style={{ color: '#334155' }}>
          {fr
            ? <>Nous avons retiré <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> de notre liste. Vous ne recevrez plus de courriels promotionnels de BidVex.</>
            : <>We've removed <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> from our marketing list. You will no longer receive promotional emails from BidVex.</>}
        </p>
        <p className="text-sm mb-8 leading-relaxed text-center" style={{ color: '#64748b' }}>
          {fr
            ? "Les courriels transactionnels (enchères, paiements, alertes) ne sont pas affectés."
            : 'Transactional emails (bids, payments, account alerts) are not affected.'}
        </p>
        <div className="text-center mb-4">
          <Link
            to={`/resubscribe?token=${encodeURIComponent(token)}&lang=${lang}`}
            data-testid="resubscribe-cta-link"
            className="text-sm font-medium"
            style={{ color: '#2563eb', textDecoration: 'underline' }}
          >
            {fr ? "Changé d'avis ? Se réabonner ici." : 'Changed your mind? Resubscribe here.'}
          </Link>
        </div>
        <div className="text-center">
          <Link to="/"
                className="inline-block py-3 px-6 rounded-xl font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)' }}
                data-testid="unsubscribe-home-link">
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
        <AlertCircle className="h-16 w-16" style={{ color: '#dc2626' }} data-testid="unsubscribe-error-icon" />
      </div>
      <h1 className="text-xl md:text-2xl font-bold text-center mb-4" style={{ color: '#0f172a' }}>
        {fr ? 'Lien invalide ou expiré' : 'Invalid or expired link'}
      </h1>
      <p className="text-base leading-relaxed text-center" style={{ color: '#334155' }}>
        {fr
          ? <>Ce lien de désabonnement est invalide ou expiré. Contactez <a href="mailto:support@bidvex.com" style={{ color: '#2563eb', textDecoration: 'underline' }}>support@bidvex.com</a> si vous avez besoin d'aide.</>
          : <>This unsubscribe link is invalid or has expired. Please contact <a href="mailto:support@bidvex.com" style={{ color: '#2563eb', textDecoration: 'underline' }}>support@bidvex.com</a> if you need assistance.</>}
      </p>
      {errorCode && (
        <p className="text-xs mt-4 text-center font-mono" style={{ color: '#94a3b8' }}>
          {errorCode}
        </p>
      )}
    </Shell>
  );
};

export default UnsubscribePage;
