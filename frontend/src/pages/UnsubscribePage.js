import API_BASE from '../config';
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Loader2, CheckCircle2, AlertCircle, Mail } from 'lucide-react';
import { LangLink } from '../components/LangLink';

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

  const [state, setState] = useState('loading'); // loading | confirm | success | already | error | self_serve | self_serve_success
  const [emailMasked, setEmailMasked] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // iter407 — self-serve form state (used when no token is present in the URL).
  const [selfEmail, setSelfEmail] = useState('');
  const [selfError, setSelfError] = useState('');

  const API = `${API_BASE}`;

  useEffect(() => {
    if (!token) {
      // iter407 — no token → show the self-serve form instead of an error.
      setState('self_serve');
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

  // iter407 — Submit handler for the no-token self-serve form.
  const handleSelfServeSubmit = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setSelfError('');
    const trimmed = (selfEmail || '').trim();
    // Light client-side sanity check — backend re-validates.
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setSelfError(fr ? 'Adresse courriel invalide.' : 'Please enter a valid email address.');
      return;
    }
    setSubmitting(true);
    try {
      const r = await axios.post(`${API}/unsubscribe/self-serve`, { email: trimmed, lang });
      setEmailMasked(r.data?.email_masked || trimmed);
      setState('self_serve_success');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      // Admin-block returns a bilingual object; keep FR / EN neutral for everyone else.
      if (detail && typeof detail === 'object' && detail.error === 'admin_unsubscribe_blocked') {
        setSelfError(fr ? detail.message_fr : detail.message_en);
      } else if (detail === 'email_invalid') {
        setSelfError(fr ? 'Adresse courriel invalide.' : 'Please enter a valid email address.');
      } else {
        setSelfError(fr
          ? "Impossible de traiter la demande pour le moment. Réessayez dans quelques instants."
          : 'We could not process your request right now. Please try again in a moment.');
      }
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

  // iter407 — no token in URL → offer a self-serve email form.
  if (state === 'self_serve') {
    return (
      <Shell>
        <div className="flex justify-center mb-4">
          <Mail className="h-14 w-14" style={{ color: '#2563eb' }} data-testid="unsubscribe-self-icon" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-center mb-3" style={{ color: '#0f172a' }}>
          {fr ? 'Se désabonner des courriels BidVex' : 'Unsubscribe from BidVex emails'}
        </h1>
        <p className="text-base mb-6 leading-relaxed text-center" style={{ color: '#334155' }}>
          {fr
            ? 'Entrez votre adresse courriel et nous vous retirerons de toutes les communications marketing.'
            : 'Enter your email address and we\u2019ll remove you from all marketing communications.'}
        </p>
        <form onSubmit={handleSelfServeSubmit} data-testid="self-serve-unsubscribe-form" noValidate>
          <label htmlFor="unsub-self-email" className="block text-sm font-medium mb-2" style={{ color: '#0f172a' }}>
            {fr ? 'Adresse courriel' : 'Email address'}
          </label>
          <input
            id="unsub-self-email"
            type="email"
            autoComplete="email"
            required
            value={selfEmail}
            onChange={(e) => { setSelfEmail(e.target.value); if (selfError) setSelfError(''); }}
            placeholder={fr ? 'vous@exemple.com' : 'you@example.com'}
            data-testid="self-serve-unsubscribe-input"
            className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 mb-4"
            style={{ fontSize: 16 }}
            disabled={submitting}
          />
          {selfError && (
            <p className="text-sm mb-4" style={{ color: '#dc2626' }} data-testid="self-serve-unsubscribe-error">
              {selfError}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            data-testid="self-serve-unsubscribe-submit"
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
                {fr ? 'Traitement\u2026' : 'Processing\u2026'}
              </span>
            ) : (fr ? 'Me désabonner' : 'Unsubscribe me')}
          </button>
        </form>
        <p className="text-xs mt-6 leading-relaxed text-center" style={{ color: '#64748b' }}>
          {fr
            ? 'Les courriels transactionnels (enchères, paiements, alertes) ne sont pas affectés.'
            : 'Transactional emails (bids, payments, account alerts) are not affected.'}
        </p>
      </Shell>
    );
  }

  if (state === 'self_serve_success') {
    return (
      <Shell>
        <div className="flex justify-center mb-4">
          <CheckCircle2 className="h-16 w-16" style={{ color: '#10b981' }} data-testid="self-serve-unsubscribe-success-icon" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-center mb-4" style={{ color: '#0f172a' }}>
          {fr ? 'Vous êtes désabonné.' : "You've been unsubscribed."}
        </h1>
        <p className="text-base mb-4 leading-relaxed text-center" style={{ color: '#334155' }} data-testid="self-serve-unsubscribe-success-message">
          {fr
            ? <>Nous avons retiré <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> de notre liste. Vous ne recevrez plus de courriels promotionnels de BidVex.</>
            : <>We&apos;ve removed <strong style={{ color: '#0f172a' }}>{emailMasked}</strong> from our marketing list. You will no longer receive promotional emails from BidVex.</>}
        </p>
        <p className="text-sm mb-8 leading-relaxed text-center" style={{ color: '#64748b' }}>
          {fr
            ? 'Les courriels transactionnels (enchères, paiements, alertes) ne sont pas affectés.'
            : 'Transactional emails (bids, payments, account alerts) are not affected.'}
        </p>
        <div className="text-center">
          <LangLink to="/"
                className="inline-block py-3 px-6 rounded-xl font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)' }}
                data-testid="self-serve-unsubscribe-home-link">
            {fr ? 'Retour à BidVex' : 'Back to BidVex'}
          </LangLink>
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
          <LangLink to="/" className="text-sm" style={{ color: '#2563eb', textDecoration: 'underline' }} data-testid="unsubscribe-cancel-link">
            {fr ? 'Annuler, me ramener' : 'Never mind, take me back'}
          </LangLink>
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
          <LangLink
            to={`/resubscribe?token=${encodeURIComponent(token)}&lang=${lang}`}
            data-testid="resubscribe-cta-link"
            className="text-sm font-medium"
            style={{ color: '#2563eb', textDecoration: 'underline' }}
          >
            {fr ? "Changé d'avis ? Se réabonner ici." : 'Changed your mind? Resubscribe here.'}
          </LangLink>
        </div>
        <div className="text-center">
          <LangLink to="/"
                className="inline-block py-3 px-6 rounded-xl font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)' }}
                data-testid="unsubscribe-home-link">
            {fr ? 'Retour à BidVex' : 'Back to BidVex'}
          </LangLink>
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
          ? <>Ce lien de désabonnement est invalide ou expiré. Contactez <a href="mailto:service@bidvex.com" style={{ color: '#2563eb', textDecoration: 'underline' }}>service@bidvex.com</a> si vous avez besoin d'aide.</>
          : <>This unsubscribe link is invalid or has expired. Please contact <a href="mailto:service@bidvex.com" style={{ color: '#2563eb', textDecoration: 'underline' }}>service@bidvex.com</a> if you need assistance.</>}
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
