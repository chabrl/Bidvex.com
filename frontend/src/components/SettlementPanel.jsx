/**
 * SettlementPanel — iter302 Directive 1.
 *
 * Seller-facing "Winner & Settlement" panel shown on ended listings with a
 * winner (replaces the "Boost Your Listing" promote block). Pulls
 * GET /api/settlement/panel/{listingId} (seller/admin gated server-side),
 * renders winner contact, amounts, payment status, the T+0 → T+72h
 * automated timeline, plus "Send Payment Reminder" and "View Invoice".
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Trophy, Mail, Phone, BellRing, FileText, CheckCircle2, Clock,
  Loader2, CircleDollarSign, PackageCheck, Send, ShieldAlert,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from './ui/dialog';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency } from '../utils/currencyFormatter';
import API_BASE from '../config';

const STATUS_BADGES = {
  payment_collected: { en: 'Paid', fr: 'Payé', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  paid: { en: 'Paid', fr: 'Payé', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  pending_payment: { en: 'Payment pending', fr: 'Paiement en attente', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  payment_failed: { en: 'Payment failed', fr: 'Paiement échoué', cls: 'bg-red-100 text-red-800 border-red-300' },
  overdue: { en: 'Overdue', fr: 'En retard', cls: 'bg-red-100 text-red-800 border-red-300' },
};

const SettlementPanel = ({ listingId }) => {
  const { i18n } = useTranslation();
  const { token, user } = useAuth();
  const fr = (i18n.language || 'en').startsWith('fr');
  const isAdmin = ['admin', 'super_admin'].includes(user?.role);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [invoiceOpen, setInvoiceOpen] = useState(false);
  const [resendOpen, setResendOpen] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCount, setResendCount] = useState(null);
  const MAX_RESENDS = 3;

  const fetchPanel = useCallback(async () => {
    if (!token || !listingId) { setLoading(false); return; }
    try {
      const r = await axios.get(`${API_BASE}/settlement/panel/${listingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
      setResendCount(typeof r.data?.winner_notification_resend_count === 'number'
        ? r.data.winner_notification_resend_count : null);
    } catch {
      setData(null); // not seller / no winner — self-hide
    } finally {
      setLoading(false);
    }
  }, [token, listingId]);

  useEffect(() => { fetchPanel(); }, [fetchPanel]);

  const sendReminder = async () => {
    setSending(true);
    try {
      await axios.post(`${API_BASE}/settlement/panel/${listingId}/remind`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(fr ? 'Rappel de paiement envoyé au gagnant' : 'Payment reminder sent to the winner');
      fetchPanel();
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' && d) ? (fr ? d.message_fr : d.message_en) : d;
      toast.error(msg || (fr ? "Échec de l'envoi du rappel" : 'Failed to send the reminder'));
    } finally {
      setSending(false);
    }
  };

  // iter307 — Admin only: re-send winner email + push (max 3 per listing)
  const resendWinnerNotification = async () => {
    setResending(true);
    try {
      const r = await axios.post(
        `${API_BASE}/settlement/panel/${listingId}/resend-winner-notification`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const remaining = r.data?.remaining ?? '?';
      toast.success(fr
        ? `Notification renvoyée au gagnant (${remaining} restant${remaining === 1 ? '' : 's'})`
        : `Winner notification re-sent (${remaining} remaining)`);
      setResendCount(r.data?.resend_count ?? null);
      setResendOpen(false);
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' && d) ? (fr ? d.message_fr : d.message_en) : d;
      toast.error(msg || (fr ? 'Échec du renvoi' : 'Re-send failed'));
    } finally {
      setResending(false);
    }
  };

  if (loading) {
    return (
      <Card className="glassmorphism border-2 border-emerald-200/40" data-testid="settlement-panel-loading">
        <CardContent className="p-6 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {fr ? 'Chargement du règlement…' : 'Loading settlement…'}
        </CardContent>
      </Card>
    );
  }
  if (!data) return null;

  const paid = ['payment_collected', 'paid'].includes(data.payment_status);
  const badge = STATUS_BADGES[data.payment_status] || STATUS_BADGES.pending_payment;
  const days = data.days_since_end ?? 0;
  const steps = [
    { key: 't0', label: fr ? 'Facture envoyée (T+0)' : 'Invoice sent (T+0)', done: true },
    { key: 't24', label: fr ? 'Rappel (T+24 h)' : 'Reminder (T+24h)', done: paid || days >= 1 },
    { key: 't48', label: fr ? 'Dernier rappel (T+48 h)' : 'Final reminder (T+48h)', done: paid || days >= 2 },
    { key: 't72', label: fr ? 'Débit automatique de la carte (T+72 h)' : 'Auto-charge saved card (T+72h)', done: paid || days >= 3 },
  ];

  return (
    <Card className="glassmorphism border-2 border-emerald-300/50" data-testid="settlement-panel">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Trophy className="h-5 w-5 text-amber-500" />
            {fr ? 'Gagnant et règlement' : 'Winner & Settlement'}
          </CardTitle>
          <Badge className={`border ${badge.cls}`} data-testid="settlement-payment-status">
            {fr ? badge.fr : badge.en}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Winner contact */}
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border space-y-1.5">
          <p className="text-xs uppercase font-semibold text-muted-foreground">
            {fr ? 'Gagnant' : 'Winner'}
          </p>
          <p className="font-semibold" data-testid="settlement-winner-name">
            {data.winner?.name || '—'}
          </p>
          <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-4 text-sm">
            {data.winner?.email && (
              <a href={`mailto:${data.winner.email}`} className="flex items-center gap-1.5 text-blue-600 hover:underline" data-testid="settlement-winner-email">
                <Mail className="h-3.5 w-3.5" /> {data.winner.email}
              </a>
            )}
            {data.winner?.phone && (
              <a href={`tel:${data.winner.phone}`} className="flex items-center gap-1.5 text-blue-600 hover:underline" data-testid="settlement-winner-phone">
                <Phone className="h-3.5 w-3.5" /> {data.winner.phone}
              </a>
            )}
          </div>
        </div>

        {/* Amounts */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg border">
            <p className="text-xs text-muted-foreground">{fr ? 'Prix d\u2019adjudication' : 'Hammer price'}</p>
            <p className="text-lg font-bold" data-testid="settlement-hammer-price">{formatCurrency(data.hammer_price)}</p>
          </div>
          <div className="p-3 rounded-lg border bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200">
            <p className="text-xs text-emerald-700 dark:text-emerald-400">{fr ? 'Votre versement net' : 'Your net payout'}</p>
            <p className="text-lg font-bold text-emerald-700 dark:text-emerald-400" data-testid="settlement-net-payout">{formatCurrency(data.net_payout)}</p>
          </div>
        </div>

        {/* Paid summary / payout state */}
        {paid && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 text-sm" data-testid="settlement-paid-banner">
            <CircleDollarSign className="h-4 w-4 text-emerald-600 flex-shrink-0" />
            <span className="text-emerald-800 dark:text-emerald-300">
              {fr ? 'Paiement de l\u2019acheteur encaissé.' : 'Buyer payment collected.'}{' '}
              {data.payout_status === 'payout_sent'
                ? (fr ? 'Votre versement a été envoyé à votre compte Stripe.' : 'Your payout was sent to your Stripe account.')
                : data.payout_status === 'payout_pending'
                  ? (fr ? 'Versement en file d\u2019attente — fonds sous 14 jours ouvrables.' : 'Payout queued — funds within 14 business days.')
                  : ''}
            </span>
          </div>
        )}
        {data.pickup_code_confirmed && (
          <div className="flex items-center gap-2 text-sm text-cyan-700" data-testid="settlement-pickup-confirmed">
            <PackageCheck className="h-4 w-4" />
            {fr ? 'Collecte confirmée par code' : 'Pickup confirmed by code'}
          </div>
        )}

        {/* Automated timeline */}
        <div data-testid="settlement-timeline">
          <p className="text-xs uppercase font-semibold text-muted-foreground mb-2">
            {fr ? 'Échéancier de paiement automatisé' : 'Automated payment timeline'}
          </p>
          <div className="space-y-1.5">
            {steps.map((s) => (
              <div key={s.key} className="flex items-center gap-2 text-sm" data-testid={`settlement-step-${s.key}`}>
                {s.done
                  ? <CheckCircle2 className="h-4 w-4 text-emerald-600 flex-shrink-0" />
                  : <Clock className="h-4 w-4 text-slate-400 flex-shrink-0" />}
                <span className={s.done ? '' : 'text-muted-foreground'}>{s.label}</span>
              </div>
            ))}
          </div>
          {data.payment_deadline && !paid && (
            <p className="text-xs text-muted-foreground mt-2">
              {fr ? 'Date limite de paiement' : 'Payment deadline'}: {new Date(data.payment_deadline).toLocaleString()}
            </p>
          )}
        </div>

        <Separator />

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-2">
          {!paid && (
            <Button
              className="w-full sm:flex-1 bg-amber-500 hover:bg-amber-600 text-white border-0"
              onClick={sendReminder}
              disabled={sending || !data.reminder_available}
              data-testid="send-reminder-btn"
            >
              {sending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <BellRing className="h-4 w-4 mr-2" />}
              {fr ? 'Envoyer un rappel de paiement' : 'Send Payment Reminder'}
            </Button>
          )}
          <Button
            variant="outline"
            className="w-full sm:flex-1"
            onClick={() => setInvoiceOpen(true)}
            data-testid="view-invoice-btn"
          >
            <FileText className="h-4 w-4 mr-2" />
            {fr ? 'Voir la facture' : 'View Invoice'}
          </Button>
        </div>
        {!paid && !data.reminder_available && data.reminder_sent_hours_ago != null && (
          <p className="text-xs text-muted-foreground" data-testid="reminder-cooldown-note">
            {fr
              ? `Rappel envoyé il y a ${Math.round(data.reminder_sent_hours_ago)} h — un seul rappel manuel par 24 h.`
              : `Reminder sent ${Math.round(data.reminder_sent_hours_ago)}h ago — one manual reminder per 24h.`}
          </p>
        )}

        {/* iter307 — Admin only: Re-send Winner Notification (email + push) */}
        {isAdmin && data.winner?.email && (
          <div className="pt-2 border-t border-dashed border-amber-200 dark:border-amber-900/40" data-testid="admin-resend-block">
            <div className="flex items-start gap-2 mb-2">
              <ShieldAlert className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-amber-700 dark:text-amber-300">
                {fr ? 'Outils administrateur' : 'Admin tools'}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full border-amber-300 text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-950/40"
              onClick={() => setResendOpen(true)}
              disabled={typeof resendCount === 'number' && resendCount >= MAX_RESENDS}
              data-testid="admin-resend-winner-btn"
              title={typeof resendCount === 'number' && resendCount >= MAX_RESENDS
                ? (fr ? `Limite atteinte (${MAX_RESENDS})` : `Max re-sends reached (${MAX_RESENDS})`)
                : undefined}
            >
              <Send className="h-3.5 w-3.5 mr-1.5" />
              {fr ? 'Renvoyer la notification au gagnant' : 'Re-send Winner Notification'}
              {typeof resendCount === 'number' && (
                <span className="ml-1.5 text-xs opacity-70">
                  ({resendCount}/{MAX_RESENDS})
                </span>
              )}
            </Button>
          </div>
        )}

        {/* Admin re-send confirmation dialog */}
        <Dialog open={resendOpen} onOpenChange={setResendOpen}>
          <DialogContent className="sm:max-w-md" data-testid="admin-resend-confirm-dialog">
            <DialogHeader>
              <DialogTitle>
                {fr ? 'Confirmer le renvoi' : 'Confirm Re-send'}
              </DialogTitle>
              <DialogDescription>
                {fr
                  ? `Renvoyer le courriel et la notification push à ${data.winner?.name || data.winner?.email} ?`
                  : `Re-send win email + push to ${data.winner?.name || data.winner?.email}?`}
              </DialogDescription>
            </DialogHeader>
            <div className="text-sm text-muted-foreground">
              {fr
                ? `Cette action ne peut être annulée. Limite: ${MAX_RESENDS} renvois par annonce.`
                : `This action cannot be undone. Limit: ${MAX_RESENDS} re-sends per listing.`}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setResendOpen(false)}
                data-testid="admin-resend-cancel-btn"
              >
                {fr ? 'Annuler' : 'Cancel'}
              </Button>
              <Button
                onClick={resendWinnerNotification}
                disabled={resending}
                className="bg-amber-500 hover:bg-amber-600 text-white"
                data-testid="admin-resend-confirm-btn"
              >
                {resending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {fr ? 'Confirmer le renvoi' : 'Confirm Re-send'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Invoice dialog */}
        <Dialog open={invoiceOpen} onOpenChange={setInvoiceOpen}>
          <DialogContent className="sm:max-w-md" data-testid="settlement-invoice-dialog">
            <DialogHeader>
              <DialogTitle>{fr ? 'Facture' : 'Invoice'}</DialogTitle>
              <DialogDescription className="truncate">{data.title}</DialogDescription>
            </DialogHeader>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Acheteur' : 'Buyer'}</span>
                <span className="font-medium">{data.winner?.name || '—'}</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Prix d\u2019adjudication' : 'Hammer price'}</span>
                <span>{formatCurrency(data.hammer_price)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Frais de plateforme (2,5 %)' : 'Platform fee (2.5%)'}</span>
                <span>{formatCurrency(data.platform_fee)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{fr ? 'Taxes' : 'Taxes'}</span>
                <span>{formatCurrency(data.taxes)}</span>
              </div>
              <Separator />
              <div className="flex justify-between font-bold text-base">
                <span>{fr ? 'Total dû par l\u2019acheteur' : 'Total due by buyer'}</span>
                <span data-testid="invoice-total-due">{formatCurrency(data.total_due)} CAD</span>
              </div>
              <div className="flex justify-between text-emerald-700 font-semibold">
                <span>{fr ? 'Versement net vendeur' : 'Seller net payout'}</span>
                <span>{formatCurrency(data.net_payout)} CAD</span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{fr ? 'Statut' : 'Status'}</span>
                <Badge className={`border ${badge.cls}`}>{fr ? badge.fr : badge.en}</Badge>
              </div>
              {data.payment_deadline && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{fr ? 'Échéance' : 'Deadline'}</span>
                  <span>{new Date(data.payment_deadline).toLocaleString()}</span>
                </div>
              )}
              {(data.seller_statement_id || data.buyer_receipt_id) && (
                <p className="text-xs text-muted-foreground pt-1">
                  {fr ? 'Réf.' : 'Ref.'}: {data.seller_statement_id || data.buyer_receipt_id}
                </p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default SettlementPanel;
