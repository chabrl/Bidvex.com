/**
 * iter317 Directive 3 — Contractor Email Hub (iter318 sender update).
 *
 * Two-pane page:
 *   • Composer (To picker + free-text, Subject, Body)
 *   • Sent log (most-recent 50 outbound emails)
 *
 * Server enforces:
 *   • FROM is locked to office@bidvex.com (visible read-only here).
 *   • Signature is appended server-side; we DO NOT preview it here so
 *     the user can't accidentally edit it. The Sent log surfaces the
 *     final rendered HTML.
 *   • Agreement must be signed before the send endpoint accepts a
 *     request (412 envelope handled at the route level).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Mail, Send, ChevronLeft, Loader2, AlertTriangle, CheckCircle2, Inbox,
  Sparkles, RefreshCw,
} from 'lucide-react';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import ContractorAgreementModal from './ContractorAgreementModal';

const SUBJECT_MAX = 300;
const BODY_MAX = 50000;

function formatDate(iso, fr) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(fr ? 'fr-CA' : 'en-CA', {
      dateStyle: 'short', timeStyle: 'short',
    });
  } catch { return iso; }
}

export default function ContractorEmailHub() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { token, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // iter336 — AI follow-up prefill payload passed via router state from
  // AdminAICoachSessions → FollowUpEmailPanel. We capture it once on mount
  // so re-renders don't re-prefill after the user starts editing.
  const [prefill, setPrefill] = useState(() => {
    const p = location.state?.prefill;
    return (p && p.source === 'ai_followup') ? p : null;
  });

  const [agreementOpen, setAgreementOpen] = useState(false);
  const [agreementChecked, setAgreementChecked] = useState(false);
  const [emails, setEmails] = useState([]);
  const [recipients, setRecipients] = useState([]);
  const [meta, setMeta] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  const [toEmail, setToEmail] = useState('');
  const [clientAccountId, setClientAccountId] = useState('');
  const [subject, setSubject] = useState(prefill?.subject || '');
  const [bodyHtml, setBodyHtml] = useState(prefill?.body || '');

  // Clear the router state after we've captured it so a browser refresh
  // doesn't re-inject the same draft (would double the "AI-suggested"
  // signal misleadingly).
  useEffect(() => {
    if (location.state?.prefill) {
      window.history.replaceState({}, document.title);
    }
  }, []);

  // AI badge visibility — a field is "AI-suggested" only while it still
  // matches the pre-filled value. The instant the contractor types, the
  // badge disappears (trust signal per spec).
  const subjectIsAiSuggested = !!prefill && subject === prefill.subject && subject.length > 0;
  const bodyIsAiSuggested    = !!prefill && bodyHtml === prefill.body && bodyHtml.length > 0;

  // Banner rules (per spec):
  //   • Show when prefill loaded and body has NOT been changed at all.
  //   • Auto-dismiss the moment the contractor edits the body.
  const showAiBanner = !!prefill && bodyIsAiSuggested;

  const isContractor = user?.role === 'dialer_contractor';
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // ── Gate: contractor must have signed the agreement ──
  const checkAgreement = useCallback(async () => {
    if (!token) return false;
    try {
      const r = await axios.get(`${API_BASE}/twilio/contractor/agreements/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.data?.required && !r.data?.signed) {
        setAgreementOpen(true);
        return false;
      }
      setAgreementOpen(false);
      return true;
    } catch {
      return true;
    } finally {
      setAgreementChecked(true);
    }
  }, [token]);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    try {
      const [s, p] = await Promise.all([
        axios.get(`${API_BASE}/twilio/contractor/emails`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        axios.get(`${API_BASE}/twilio/contractor/emails/recipients`, {
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => ({ data: { items: [] } })),
      ]);
      setEmails(s.data?.items || []);
      setMeta({
        sender_email:  s.data?.sender_email,
        sender_name:   s.data?.sender_name,
        support_phone: s.data?.support_phone,
      });
      setRecipients(p.data?.items || []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message);
    }
  }, [token]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { navigate('/auth?next=/contractor/emails', { replace: true }); return; }
    (async () => {
      const ok = await checkAgreement();
      if (ok) await fetchAll();
    })();
  }, [authLoading, user, checkAgreement, fetchAll, navigate]);

  const onPickerChange = (val) => {
    if (!val) {
      setClientAccountId('');
      return;
    }
    const found = recipients.find((r) => r.id === val);
    setClientAccountId(found?.id || '');
    if (found?.email) setToEmail(found.email);
  };

  const subjectInvalid = subject.length === 0 || subject.length > SUBJECT_MAX;
  const bodyInvalid = bodyHtml.trim().length === 0 || bodyHtml.length > BODY_MAX;
  const recipientInvalid = !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(toEmail.trim());

  const handleSend = async () => {
    setSending(true);
    setError(null);
    try {
      await axios.post(
        `${API_BASE}/twilio/contractor/emails/send`,
        {
          to_email:           toEmail.trim().toLowerCase(),
          subject,
          body_html:          bodyHtml,
          client_account_id:  clientAccountId || null,
          locale:             fr ? 'fr' : 'en',
          // iter336 — Link this outbound email back to the AI Coach session
          // that generated the draft (server updates ai_voice_calls.$.sent).
          call_log_id:        prefill?.call_log_id || null,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(fr ? 'Courriel envoyé.' : 'Email sent.');
      setSubject(''); setBodyHtml(''); setToEmail(''); setClientAccountId('');
      setPrefill(null); // clear the AI banner/badges once sent
      await fetchAll();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const env = (detail && typeof detail === 'object') ? detail : { message_en: detail || e?.message };
      if (e?.response?.status === 412) {
        setAgreementOpen(true);
        return;
      }
      const msg = (fr ? env.message_fr : env.message_en) || (fr ? 'Échec.' : 'Failed.');
      toast.error(msg);
      setError(msg);
    } finally {
      setSending(false);
    }
  };

  if (authLoading || !agreementChecked) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="email-hub-loading">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-3" />
        <span>{fr ? 'Chargement…' : 'Loading…'}</span>
      </div>
    );
  }

  if (!isContractor && !isAdmin) {
    return (
      <div className="container mx-auto max-w-3xl py-12 px-4" data-testid="email-hub-403">
        <Card className="border-2 border-rose-300 bg-rose-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-rose-600" />
            <div>
              <h2 className="font-semibold text-rose-900">
                {fr ? 'Accès refusé' : 'Access denied'}
              </h2>
              <p className="text-sm text-rose-800 mt-1">
                {fr
                  ? 'Le Hub Courriels est réservé aux contractants approuvés.'
                  : 'The Email Hub is reserved for approved contractors.'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4 space-y-4" data-testid="email-hub-page">
      <ContractorAgreementModal
        open={agreementOpen}
        onSigned={async () => {
          setAgreementOpen(false);
          await fetchAll();
        }}
      />

      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="email-hub-title">
            <Mail className="h-7 w-7 text-indigo-600" />
            {fr ? 'Hub Courriels du contractant' : 'Contractor Email Hub'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {fr
              ? `Envoyez des courriels depuis ${meta?.sender_email || 'office@bidvex.com'} avec votre signature BidVex.`
              : `Send emails from ${meta?.sender_email || 'office@bidvex.com'} with your BidVex signature appended.`}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => navigate('/contractor/dashboard')}
          data-testid="back-to-dashboard-btn"
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          {fr ? 'Tableau de bord' : 'Dashboard'}
        </Button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ── Composer ── */}
        <Card data-testid="email-composer-card">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-sm">
                {fr ? 'Nouveau courriel' : 'New Email'}
              </h2>
              <Badge variant="outline" className="text-xs" data-testid="locked-sender-badge">
                {fr ? 'De :' : 'From:'} {meta?.sender_email || 'office@bidvex.com'}
              </Badge>
            </div>

            {showAiBanner && (
              <div
                className="rounded-md border border-purple-200 bg-gradient-to-r from-purple-50 to-indigo-50 px-3 py-2 flex items-start gap-2"
                data-testid="ai-followup-banner"
              >
                <Sparkles className="h-4 w-4 text-purple-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-purple-900">
                    {fr
                      ? "Brouillon suggéré par l'IA à partir de l'appel."
                      : 'AI-drafted follow-up from the coach session.'}
                  </p>
                  <p className="text-[11px] text-purple-800 mt-0.5">
                    {fr
                      ? 'Relisez et personnalisez avant l\'envoi. Le badge disparaît dès que vous modifiez un champ.'
                      : 'Review and personalise before sending. Badges disappear the moment you edit a field.'}
                  </p>
                </div>
                {prefill?.call_log_id && (
                  <button
                    type="button"
                    onClick={() => navigate(
                      `/admin?tab=ai-coach-sessions`,
                      { state: { autoExpandCallLogId: prefill.call_log_id } },
                    )}
                    className="text-[11px] font-semibold text-indigo-700 hover:text-indigo-900 hover:underline flex items-center gap-1 whitespace-nowrap flex-shrink-0"
                    data-testid="ai-followup-regenerate-link"
                  >
                    <RefreshCw className="h-3 w-3" />
                    {fr ? 'Régénérer' : 'Regenerate'}
                  </button>
                )}
              </div>
            )}

            <div>
              <Label htmlFor="recipient-picker" className="text-xs">
                {fr ? 'Choisir un client recommandé' : 'Pick a referred client'}
              </Label>
              <select
                id="recipient-picker"
                data-testid="recipient-picker"
                className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm bg-white"
                value={clientAccountId}
                onChange={(e) => onPickerChange(e.target.value)}
              >
                <option value="">
                  {fr ? '— Aucun (saisir manuellement) —' : '— None (free-text) —'}
                </option>
                {recipients.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.display} ({r.email})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label htmlFor="to-email-input" className="text-xs">
                {fr ? 'Destinataire' : 'To'}
              </Label>
              <Input
                id="to-email-input"
                data-testid="to-email-input"
                type="email"
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                placeholder="client@example.com"
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="subject-input" className="text-xs flex items-center justify-between">
                <span className="flex items-center gap-2">
                  {fr ? 'Sujet' : 'Subject'}
                  {subjectIsAiSuggested && (
                    <Badge
                      variant="outline"
                      className="text-[9px] font-medium border-purple-300 text-purple-700 bg-purple-50 px-1.5 py-0"
                      data-testid="subject-ai-badge"
                    >
                      <Sparkles className="h-2.5 w-2.5 mr-0.5" />
                      {fr ? 'IA suggéré' : 'AI-suggested'}
                    </Badge>
                  )}
                </span>
                <span className="text-[10px] text-slate-400">
                  {subject.length}/{SUBJECT_MAX}
                </span>
              </Label>
              <Input
                id="subject-input"
                data-testid="subject-input"
                value={subject}
                onChange={(e) => setSubject(e.target.value.slice(0, SUBJECT_MAX))}
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="body-html-input" className="text-xs flex items-center justify-between">
                <span className="flex items-center gap-2">
                  {fr ? 'Corps du courriel (HTML accepté)' : 'Body (HTML accepted)'}
                  {bodyIsAiSuggested && (
                    <Badge
                      variant="outline"
                      className="text-[9px] font-medium border-purple-300 text-purple-700 bg-purple-50 px-1.5 py-0"
                      data-testid="body-ai-badge"
                    >
                      <Sparkles className="h-2.5 w-2.5 mr-0.5" />
                      {fr ? 'IA suggéré' : 'AI-suggested'}
                    </Badge>
                  )}
                </span>
                <span className="text-[10px] text-slate-400">
                  {bodyHtml.length}/{BODY_MAX}
                </span>
              </Label>
              <Textarea
                id="body-html-input"
                data-testid="body-html-input"
                value={bodyHtml}
                onChange={(e) => setBodyHtml(e.target.value.slice(0, BODY_MAX))}
                rows={10}
                className="mt-1 font-mono text-xs"
                placeholder={
                  fr
                    ? '<p>Bonjour,</p><p>Merci pour votre intérêt envers BidVex…</p>'
                    : '<p>Hi,</p><p>Thanks for your interest in BidVex…</p>'
                }
              />
            </div>

            <div className="rounded border border-indigo-100 bg-indigo-50 px-3 py-2 text-[11px] text-indigo-900" data-testid="signature-notice">
              {fr
                ? 'Votre signature BidVex (logo, coordonnées et téléphone du soutien) sera ajoutée automatiquement par le serveur — ne la dupliquez pas ici.'
                : 'Your BidVex signature (logo, contact details and support phone) is appended automatically by the server — do not duplicate it here.'}
            </div>

            {error && (
              <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900" data-testid="composer-error">
                {error}
              </div>
            )}

            <div className="flex justify-end">
              <Button
                onClick={handleSend}
                disabled={sending || recipientInvalid || subjectInvalid || bodyInvalid}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                data-testid="send-email-btn"
              >
                {sending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                {fr ? 'Envoyer' : 'Send'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ── Sent log ── */}
        <Card data-testid="email-sent-log-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm flex items-center gap-2">
                <Inbox className="h-4 w-4 text-indigo-600" />
                {fr ? 'Envoyés' : 'Sent'}
              </h2>
              <Badge variant="outline" data-testid="sent-count-badge">
                {emails.length}
              </Badge>
            </div>

            {emails.length === 0 ? (
              <p className="text-xs text-slate-500" data-testid="sent-empty-state">
                {fr ? 'Aucun courriel envoyé pour le moment.' : 'No emails sent yet.'}
              </p>
            ) : (
              <ul className="space-y-3 max-h-[60vh] overflow-y-auto" data-testid="sent-list">
                {emails.map((e) => (
                  <li
                    key={e.id}
                    className="rounded border border-slate-200 p-3"
                    data-testid={`sent-row-${e.id}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate" data-testid="sent-subject">
                          {e.subject}
                        </p>
                        <p className="text-xs text-slate-600 truncate">
                          {fr ? 'À :' : 'To:'} {e.to_email}
                        </p>
                      </div>
                      <Badge
                        className={
                          e.status === 'sent'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }
                        data-testid={`sent-status-${e.status}`}
                      >
                        {e.status === 'sent' ? (
                          <CheckCircle2 className="h-3 w-3 mr-1 inline" />
                        ) : (
                          <AlertTriangle className="h-3 w-3 mr-1 inline" />
                        )}
                        {e.status}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1">
                      {formatDate(e.sent_at, fr)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
