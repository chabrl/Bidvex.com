/**
 * iter317 Directive 2 — Electronic Contractor Agreement modal.
 *
 * Scroll-to-accept gate that blocks contractor-only routes until the
 * current agreement version has been signed. Posts the typed full
 * legal name to `/api/twilio/contractor/agreements/sign` which performs
 * an exact (case-insensitive, whitespace-collapsed) match against the
 * `legal_name` on file before persisting an immutable audit row.
 *
 * Server returns 412 `agreement_required` on every gated endpoint
 * until this modal is dismissed by a successful sign action — the
 * Dashboard catches that envelope and renders this modal instead of
 * the dashboard body.
 */
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { FileSignature, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';

export default function ContractorAgreementModal({ open, onSigned }) {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { token } = useAuth();

  const [agreement, setAgreement] = useState(null);
  const [scrolled, setScrolled] = useState(false);
  const [signedName, setSignedName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorEnvelope, setErrorEnvelope] = useState(null);
  const scrollRef = useRef(null);

  // Fetch agreement text whenever modal opens.
  useEffect(() => {
    if (!open || !token) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/twilio/contractor/agreements/current`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setAgreement(r.data);
      } catch (e) {
        if (!cancelled) {
          toast.error(fr ? 'Impossible de charger l\u2019entente.' : 'Failed to load agreement.');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [open, token, fr]);

  const onScroll = (e) => {
    const el = e.target;
    if (!el) return;
    const reachedBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
    if (reachedBottom && !scrolled) setScrolled(true);
  };

  const handleSign = async () => {
    if (!agreement) return;
    setSubmitting(true);
    setErrorEnvelope(null);
    try {
      const r = await axios.post(
        `${API_BASE}/twilio/contractor/agreements/sign`,
        {
          agreement_version: agreement.version,
          text_hash:         agreement.text_hash,
          signed_full_name:  signedName,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(fr ? 'Entente signée.' : 'Agreement signed.');
      onSigned?.(r.data);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const env = (detail && typeof detail === 'object') ? detail : { message_en: detail || e?.message };
      setErrorEnvelope(env);
      toast.error((fr ? env.message_fr : env.message_en) || (fr ? 'Échec.' : 'Failed.'));
    } finally {
      setSubmitting(false);
    }
  };

  const accountLegalName = agreement?.account_legal_name || '';
  const text = fr ? agreement?.text_fr : agreement?.text_en;
  const title = fr ? agreement?.title_fr : agreement?.title_en;

  return (
    <Dialog open={open} modal>
      <DialogContent
        className="max-w-3xl max-h-[90vh] flex flex-col"
        data-testid="contractor-agreement-modal"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <FileSignature className="h-6 w-6 text-indigo-600" />
            {title || (fr ? 'Entente de services du contractant' : 'Contractor Services Agreement')}
          </DialogTitle>
          <DialogDescription>
            {fr
              ? 'Veuillez lire l\u2019entente entière puis saisir votre nom légal exact pour signer.'
              : 'Please read the full agreement, then type your exact legal name to sign.'}
          </DialogDescription>
        </DialogHeader>

        {/* Scroll-to-accept body */}
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="overflow-y-auto border border-slate-200 rounded p-4 text-sm whitespace-pre-line bg-slate-50 flex-1 min-h-[260px]"
          data-testid="agreement-scroll-body"
          style={{ maxHeight: '50vh' }}
        >
          {text || (fr ? 'Chargement…' : 'Loading…')}
        </div>

        <div className="mt-2 text-xs text-slate-500" data-testid="scroll-status">
          {scrolled ? (
            <span className="text-emerald-700 flex items-center gap-1">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {fr ? 'Vous avez parcouru l\u2019entente entière.' : 'You\u2019ve scrolled through the full agreement.'}
            </span>
          ) : (
            <span className="text-amber-700 flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              {fr ? 'Faites défiler jusqu\u2019au bas pour activer la signature.' : 'Scroll to the bottom to enable signing.'}
            </span>
          )}
        </div>

        {accountLegalName ? (
          <div className="mt-3 rounded border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs text-indigo-900" data-testid="legal-name-on-file">
            {fr ? 'Nom légal au dossier :' : 'Legal name on file:'}{' '}
            <span className="font-semibold">{accountLegalName}</span>
          </div>
        ) : (
          <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" data-testid="no-legal-name-warning">
            {fr
              ? 'Aucun nom légal au dossier. Veuillez d\u2019abord compléter votre profil fiscal.'
              : 'No legal name on file. Complete your tax profile before signing.'}
          </div>
        )}

        <div className="mt-3">
          <Label htmlFor="signed-name-input" className="text-sm">
            {fr ? 'Saisissez votre nom légal complet pour signer' : 'Type your full legal name to sign'}
          </Label>
          <Input
            id="signed-name-input"
            data-testid="signed-name-input"
            value={signedName}
            onChange={(e) => setSignedName(e.target.value)}
            placeholder={accountLegalName || (fr ? 'Nom prénom' : 'First Last')}
            disabled={submitting}
            className="mt-1"
          />
        </div>

        {errorEnvelope && (
          <div className="mt-2 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900" data-testid="agreement-error">
            {fr ? errorEnvelope.message_fr : errorEnvelope.message_en}
          </div>
        )}

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button
            onClick={handleSign}
            disabled={!scrolled || !signedName.trim() || submitting || !accountLegalName}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="agreement-accept-btn"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <FileSignature className="h-4 w-4 mr-2" />
            )}
            {fr ? 'J\u2019accepte' : 'I Accept'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
