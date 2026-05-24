/**
 * iter225 Task 4 — Buyer-side Custom Contract Acceptance Modal.
 *
 * Shown to a buyer when they request to link to a broker who has
 * `custom_terms_enabled=true`. Bilingual, unskippable, and requires
 * explicit checkbox + typed-name signature before the buyer can
 * proceed with the $500 deposit binding.
 *
 * Fetches custom terms from GET /api/brokers/:broker_id/custom-terms.
 * Submits acceptance to POST /api/broker-relationships/:rel_id/accept-custom-terms
 * (called by parent AFTER the relationship has been created).
 */
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Alert, AlertDescription } from '../ui/alert';
import { FileText, X, AlertTriangle, ChevronDown, CheckCircle2 } from 'lucide-react';

const COPY = {
  en: {
    title:        "Broker's Custom Contract",
    subtitle:     "Your broker has set custom terms in addition to the BidVex platform agreement. Read carefully — bidding is not allowed until you accept.",
    no_terms:     "Your broker has not set any custom terms. You can proceed.",
    accept_check: "I have read and agree to the broker's custom terms above.",
    signature_lbl: "Type your full name as your digital signature",
    accept_btn:   "Accept Contract",
    decline_btn:  "Decline",
    scroll_hint:  "Scroll to the bottom to enable acceptance.",
    success:      "Contract accepted. You can now place bids via this broker.",
    loading:      "Loading contract…",
  },
  fr: {
    title:        "Contrat personnalisé du courtier",
    subtitle:     "Votre courtier a établi des conditions personnalisées en plus de l'accord de plateforme BidVex. Lisez attentivement — les enchères ne sont pas autorisées tant que vous n'avez pas accepté.",
    no_terms:     "Votre courtier n'a pas établi de conditions personnalisées. Vous pouvez continuer.",
    accept_check: "J'ai lu et j'accepte les conditions personnalisées du courtier ci-dessus.",
    signature_lbl: "Tapez votre nom complet comme signature numérique",
    accept_btn:   "Accepter le contrat",
    decline_btn:  "Refuser",
    scroll_hint:  "Faites défiler jusqu'en bas pour activer l'acceptation.",
    success:      "Contrat accepté. Vous pouvez maintenant enchérir via ce courtier.",
    loading:      "Chargement du contrat…",
  },
};

export default function BuyerCustomTermsModal({ open, brokerId, relationshipId, onAccepted, onClose, lang = 'en' }) {
  const t = COPY[lang === 'fr' ? 'fr' : 'en'];

  const scrollRef = useRef(null);
  const [terms, setTerms] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scrolledBottom, setScrolledBottom] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [signature, setSignature] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [successFlash, setSuccessFlash] = useState(false);

  useEffect(() => {
    if (!open || !brokerId) return;
    let cancelled = false;
    setLoading(true); setError(null);
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/brokers/${brokerId}/custom-terms`);
        if (!cancelled) setTerms(r.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail?.error || 'failed_to_load_terms');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, brokerId]);

  useEffect(() => {
    if (!open) {
      setScrolledBottom(false); setAgreed(false); setSignature('');
      setError(null); setSuccessFlash(false);
      if (scrollRef.current) scrollRef.current.scrollTop = 0;
    }
  }, [open]);

  const hasTerms = terms?.enabled && (terms.custom_terms_html?.trim() || terms.custom_terms_plain?.trim());

  // If broker doesn't have custom terms, fast-accept on render
  useEffect(() => {
    if (open && terms && !hasTerms && onAccepted) {
      onAccepted(null);
    }
  }, [open, terms, hasTerms, onAccepted]);

  const onScroll = (e) => {
    const el = e.currentTarget;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 24) {
      setScrolledBottom(true);
    }
  };

  const canAccept = scrolledBottom && agreed && signature.trim().length >= 2;

  const submit = async () => {
    if (!canAccept || submitting) return;
    setSubmitting(true); setError(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      if (!relationshipId) {
        // Defer to parent — parent will call accept-custom-terms after rel is created
        setSuccessFlash(true);
        if (onAccepted) onAccepted({ signature_text: signature.trim(), accepted: true });
        return;
      }
      const r = await axios.post(
        `${API_BASE}/broker-relationships/${relationshipId}/accept-custom-terms`,
        { accepted: true, signature_text: signature.trim(), locale: lang },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (r.data?.success) {
        setSuccessFlash(true);
        if (onAccepted) onAccepted(r.data);
        setTimeout(() => { if (onClose) onClose(); }, 1100);
      }
    } catch (e) {
      setError(
        e?.response?.data?.detail?.[lang === 'fr' ? 'message_fr' : 'message_en']
        || e?.response?.data?.detail?.error
        || (lang === 'fr' ? 'L\'acceptation a échoué.' : 'Acceptance failed.')
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;
  if (terms && !hasTerms) return null;  // No custom terms — modal auto-skipped

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
      data-testid="buyer-custom-terms-modal"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white dark:bg-slate-900 w-full max-w-2xl rounded-xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <header className="px-5 py-3 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-amber-500 to-orange-500 text-white flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="w-5 h-5 flex-shrink-0" />
            <h2 className="font-bold text-base sm:text-lg truncate">
              {terms?.broker_name ? `${terms.broker_name} — ${t.title}` : t.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="p-1.5 rounded-md hover:bg-white/20 transition disabled:opacity-50"
            aria-label="Close"
            data-testid="buyer-terms-close"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        {/* Subtitle */}
        <div className="px-5 py-2.5 bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs">
          {t.subtitle}
        </div>

        {/* Scrollable body */}
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="flex-1 overflow-y-auto px-5 py-4 bg-slate-50 dark:bg-slate-900/40 text-sm leading-relaxed"
          data-testid="buyer-terms-scroll"
        >
          {loading ? (
            <p className="text-slate-500 text-center py-8">{t.loading}</p>
          ) : terms?.custom_terms_html ? (
            <div
              className="prose prose-sm dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: terms.custom_terms_html }}
            />
          ) : (
            <pre className="whitespace-pre-wrap font-sans text-slate-700 dark:text-slate-200">
              {terms?.custom_terms_plain || ''}
            </pre>
          )}
          <div className="text-xs text-slate-400 text-center py-2" data-testid="buyer-terms-bottom-sentinel">— end of contract —</div>
        </div>

        {!scrolledBottom && hasTerms && (
          <div className="px-5 py-2 bg-slate-100 dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 flex items-center gap-2">
            <ChevronDown className="w-4 h-4 animate-bounce text-amber-600" />
            <span>{t.scroll_hint}</span>
          </div>
        )}

        {/* Footer — accept block */}
        <footer className="px-5 py-4 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 space-y-3">
          {error && (
            <Alert variant="destructive" data-testid="buyer-terms-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{String(error)}</AlertDescription>
            </Alert>
          )}
          {successFlash && (
            <Alert className="border-emerald-300 bg-emerald-50">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <AlertDescription className="text-emerald-800">{t.success}</AlertDescription>
            </Alert>
          )}
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              disabled={!scrolledBottom || submitting}
              className="mt-1 h-5 w-5 accent-amber-600"
              data-testid="buyer-terms-agree"
            />
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{t.accept_check}</span>
          </label>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
              {t.signature_lbl} <span className="text-rose-500">*</span>
            </label>
            <Input
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
              placeholder={lang === 'fr' ? 'Prénom Nom' : 'Full Name'}
              disabled={!scrolledBottom || !agreed || submitting}
              data-testid="buyer-terms-signature"
              className="font-serif italic"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={submitting} data-testid="buyer-terms-decline">
              {t.decline_btn}
            </Button>
            <Button
              onClick={submit}
              disabled={!canAccept || submitting}
              className="bg-gradient-to-r from-amber-500 to-orange-500 text-white"
              data-testid="buyer-terms-accept"
            >
              {submitting ? '…' : t.accept_btn}
            </Button>
          </div>
        </footer>
      </div>
    </div>
  );
}
