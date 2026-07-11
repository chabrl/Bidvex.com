/**
 * iter339 — Affiliate Earnings widget + Referred-Users activity feed.
 * Data: GET /api/affiliate/earnings-summary + /api/affiliate/commission-events.
 * Bilingual EN/FR. Projection methodology is shown transparently.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { DollarSign, TrendingUp, Users, Loader2, ArrowRight, Share2, Copy } from 'lucide-react';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { formatCurrency } from '../utils/currencyFormatter';

const SOURCE_LABELS = {
  auction_buyer_fee:  { en: 'won auction',   fr: 'enchère gagnée' },
  auction_seller_fee: { en: 'sold item',     fr: 'article vendu' },
  subscription:       { en: 'subscription',  fr: 'abonnement' },
};

const STATUS_BADGES = {
  pending:  { en: 'Pending',  fr: 'En attente', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  approved: { en: 'Approved', fr: 'Approuvé',   cls: 'bg-blue-100 text-blue-800 border-blue-300' },
  paid:     { en: 'Paid',     fr: 'Payé',       cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
};

const Row = ({ label, value, sub, testId }) => (
  <div className="flex items-baseline justify-between gap-2 py-1">
    <span className="text-sm text-slate-600 dark:text-slate-400">{label}</span>
    <span className="text-sm font-semibold text-right" data-testid={testId}>
      {value}{sub ? <span className="font-normal text-slate-500 text-xs"> {sub}</span> : null}
    </span>
  </div>
);

export const AffiliateEarningsWidget = () => {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const fr = i18n.language?.startsWith('fr');

  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventsTotal, setEventsTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [refLink, setRefLink] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const loadEvents = useCallback(async (p, append) => {
    const r = await axios.get(`${API_BASE}/affiliate/commission-events?page=${p}&limit=10`, { headers });
    setEventsTotal(r.data?.total || 0);
    setEvents((prev) => (append ? [...prev, ...(r.data?.items || [])] : (r.data?.items || [])));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const [s] = await Promise.all([
          axios.get(`${API_BASE}/affiliate/earnings-summary`, { headers }),
          loadEvents(1, false),
        ]);
        setSummary(s.data);
      } catch (e) {
        setLoadError(true);
      } finally { setLoading(false); }
    })();
  }, [token, loadEvents]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      await loadEvents(page + 1, true);
      setPage(page + 1);
    } finally { setLoadingMore(false); }
  };

  const requestPayout = async () => {
    setRequesting(true);
    try {
      const r = await axios.post(`${API_BASE}/affiliate/request-payout`, {}, { headers });
      toast.success(fr
        ? `Demande de paiement soumise (${formatCurrency(r.data?.amount || 0)})`
        : `Payout request submitted (${formatCurrency(r.data?.amount || 0)})`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec de la demande de paiement' : 'Payout request failed'));
    } finally { setRequesting(false); }
  };

  // iter340 P1 — generate + download the Pillow share card PNG.
  const handleShareCard = async () => {
    setSharing(true);
    try {
      const res = await fetch(`${API_BASE}/affiliate/share-card?lang=${fr ? 'fr' : 'en'}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bidvex-earnings-projection.png';
      a.click();
      URL.revokeObjectURL(url);
      toast.success(fr ? 'Carte de projection téléchargée !' : 'Projection card downloaded!');
    } catch (e) {
      toast.error(e.message || (fr ? 'Échec de la génération de la carte' : 'Card generation failed'));
    } finally { setSharing(false); }
  };

  const handleCopyLink = async () => {
    try {
      let link = refLink;
      if (!link) {
        const r = await axios.get(`${API_BASE}/affiliate/my-referral-link`, { headers });
        link = r.data?.referral_link || '';
        setRefLink(link);
      }
      await navigator.clipboard.writeText(link);
      toast.success(fr ? 'Lien de parrainage copié !' : 'Referral link copied!');
    } catch {
      toast.error(fr ? 'Échec de la copie du lien' : 'Failed to copy link');
    }
  };

  if (loading) {
    return (
      <Card data-testid="affiliate-earnings-widget">
        <CardContent className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin" /></CardContent>
      </Card>
    );
  }
  if (!summary) return null;

  const fmtDate = (d) => {
    if (!d) return '—';
    try {
      return new Date(d).toLocaleDateString(fr ? 'fr-CA' : 'en-US', { month: '2-digit', day: '2-digit', year: '2-digit' });
    } catch { return '—'; }
  };

  const basisNote = summary.projection_basis_months >= 3
    ? (fr ? 'Basé sur la moyenne de vos 3 derniers mois' : 'Based on your last 3 months average')
    : (fr
      ? `Basé sur ${summary.projection_basis_months} mois de données`
      : `Based on ${summary.projection_basis_months} month${summary.projection_basis_months === 1 ? '' : 's'} of data`);

  return (
    <Card className="border-emerald-200 dark:border-emerald-800" data-testid="affiliate-earnings-widget">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <DollarSign className="h-5 w-5 text-emerald-600" />
          {fr ? 'Vos gains d\'affiliation' : 'Your Affiliate Earnings'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Monthly / lifetime */}
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          <Row
            label={fr ? 'Ce mois-ci' : 'This month'}
            value={`${formatCurrency(summary.this_month.earned)} ${fr ? 'gagnés' : 'earned'}`}
            sub={fr ? `(${summary.this_month.transaction_count} transactions)` : `(from ${summary.this_month.transaction_count} transactions)`}
            testId="ew-this-month"
          />
          <Row
            label={fr ? 'Le mois dernier' : 'Last month'}
            value={`${formatCurrency(summary.last_month.earned)} ${fr ? 'gagnés' : 'earned'}`}
            testId="ew-last-month"
          />
          <Row
            label={fr ? 'À vie' : 'Lifetime'}
            value={`${formatCurrency(summary.lifetime.earned)} ${fr ? 'gagnés' : 'earned'}`}
            sub={fr ? `(${summary.lifetime.transaction_count} txns au total)` : `(from ${summary.lifetime.transaction_count} total txns)`}
            testId="ew-lifetime"
          />
        </div>

        {/* Projection */}
        <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium flex items-center gap-1.5 text-emerald-800 dark:text-emerald-300">
              <TrendingUp className="h-4 w-4" />
              {fr ? 'Projection du mois prochain' : 'Projected next month'}
            </span>
            <span className="text-base font-bold text-emerald-800 dark:text-emerald-300" data-testid="ew-projected">
              ~{formatCurrency(summary.projected_next_month)}
            </span>
          </div>
          <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1" data-testid="ew-projection-basis">
            {basisNote} · {fr ? 'selon les dépenses mensuelles moyennes de vos utilisateurs référés' : "based on your referred users' avg monthly spend"}
          </p>
        </div>

        {/* Referred users */}
        <div className="rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium flex items-center gap-1.5">
              <Users className="h-4 w-4 text-blue-600" />
              {fr ? 'Vos utilisateurs référés' : 'Your referred users'}
            </span>
            <span className="text-sm font-bold" data-testid="ew-referred-users">
              {summary.referred_users.active_this_month} {fr ? 'actifs' : 'active'}
              <span className="font-normal text-slate-500 text-xs"> / {summary.referred_users.total} {fr ? 'au total' : 'total'}</span>
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400" data-testid="ew-fees-generated">
            {fr
              ? `Ont généré ${formatCurrency(summary.this_month.platform_fees_generated)} en frais de plateforme ce mois-ci`
              : `Generated ${formatCurrency(summary.this_month.platform_fees_generated)} in platform fees this month`}
            {' · '}
            {fr ? 'Votre part de 3 % :' : 'Your 3% share:'}{' '}
            <b>{formatCurrency(summary.this_month.earned)}</b>
          </p>
        </div>

        {/* Pending approval + payout */}
        <div className="flex items-center justify-between gap-2 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 p-3">
          <span className="text-sm">
            {fr ? 'En attente d\'approbation :' : 'Pending approval:'}{' '}
            <b data-testid="ew-pending">{formatCurrency(summary.pending_approval)}</b>
          </span>
          <Button size="sm" variant="outline" className="border-amber-400 text-amber-800 hover:bg-amber-100"
            onClick={requestPayout} disabled={requesting} data-testid="ew-request-payout-btn">
            {requesting ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : null}
            {fr ? 'Demander un paiement' : 'Request Payout'}
            <ArrowRight className="h-3.5 w-3.5 ml-1" />
          </Button>
        </div>

        {/* iter340 P1 — share card + copy link */}
        <div className="flex gap-2">
          <Button
            size="sm"
            className="flex-1 bg-[#0B2545] hover:bg-[#123869] text-white"
            onClick={handleShareCard}
            disabled={sharing}
            data-testid="ew-share-card-btn"
          >
            {sharing ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Share2 className="h-3.5 w-3.5 mr-1.5" />}
            {fr ? 'Partager ma projection' : 'Share My Projection'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCopyLink}
            data-testid="ew-copy-link-btn"
          >
            <Copy className="h-3.5 w-3.5 mr-1.5" />
            {fr ? 'Copier le lien' : 'Copy Link'}
          </Button>
        </div>

        {/* Activity feed */}
        <div data-testid="commission-events-feed">
          <p className="text-sm font-semibold mb-2">
            {fr ? 'Événements de commission récents' : 'Recent commission events'}
          </p>
          {events.length === 0 ? (
            <p className="text-xs text-slate-500" data-testid="ce-empty">
              {fr ? 'Aucune commission pour le moment — partagez votre lien pour commencer à gagner.' : 'No commissions yet — share your link to start earning.'}
            </p>
          ) : (
            <div className="space-y-1.5">
              {events.map((ev, i) => {
                const src = SOURCE_LABELS[ev.revenue_source] || { en: 'transaction', fr: 'transaction' };
                const sb = STATUS_BADGES[ev.status] || STATUS_BADGES.pending;
                return (
                  <div key={ev.id || i} className="flex items-center gap-2 text-xs flex-wrap py-1 border-b border-slate-100 dark:border-slate-800 last:border-0" data-testid={`ce-row-${i}`}>
                    <span className="text-slate-500 font-mono w-16 shrink-0">{fmtDate(ev.date)}</span>
                    <span className="font-medium">{ev.referred_user}</span>
                    <span className="text-slate-500">{fr ? src.fr : src.en}</span>
                    <span className="text-slate-400">→</span>
                    <span>{fr ? 'Frais BidVex :' : 'BidVex fee:'} <b>{formatCurrency(ev.platform_fee)}</b></span>
                    <span className="text-slate-400">→</span>
                    <span>{fr ? 'Vos 3 % :' : 'Your 3%:'} <b className="text-emerald-700 dark:text-emerald-400">{formatCurrency(ev.commission)}</b></span>
                    <Badge className={`${sb.cls} text-[10px] ml-auto`}>{fr ? sb.fr : sb.en}</Badge>
                  </div>
                );
              })}
              {events.length < eventsTotal && (
                <Button variant="ghost" size="sm" className="w-full text-xs" onClick={loadMore} disabled={loadingMore} data-testid="ce-load-more">
                  {loadingMore ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : null}
                  {fr ? 'Voir plus' : 'Load more'}
                </Button>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default AffiliateEarningsWidget;
