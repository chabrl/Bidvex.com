/**
 * iter316 Phase B — Mission B4
 * Contractor Dashboard at `/contractor/dashboard`.
 *
 * Server-enforced role isolation (403 for non-contractors / non-admins).
 * Reuses the iter302 Stripe Connect onboarding link via /api/settlement/connect/onboard.
 *
 * Polls every 60 seconds to refresh earnings + accrued payouts.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  DollarSign, Users, PhoneCall, Link as LinkIcon, Copy, CheckCircle2,
  AlertTriangle, Zap, Loader2, ShieldCheck, UserPlus, X, Save,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../components/ui/dialog';

const POLL_INTERVAL_MS = 60000; // 60s refresh per spec

function formatMoney(amount, currency = 'CAD') {
  const v = Number(amount || 0);
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency }).format(v);
}

function StatCard({ label, value, icon: Icon, color = 'indigo', testid }) {
  return (
    <Card data-testid={testid}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
          <Icon className={`h-4 w-4 text-${color}-600`} />
        </div>
        <p className="text-2xl font-bold mt-1">{value}</p>
      </CardContent>
    </Card>
  );
}

export default function ContractorDashboard() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [onboardingBusy, setOnboardingBusy] = useState(false);
  const [payoutReadiness, setPayoutReadiness] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [addClientOpen, setAddClientOpen] = useState(false);

  // Server-enforced via 403; the client-side gate avoids needless calls.
  const isContractor = user && (user.role === 'dialer_contractor');
  const isAdmin = user && (user.role === 'admin' || user.role === 'super_admin');

  const fetchDashboard = useCallback(async () => {
    if (!token) return;
    try {
      const [r, pr, pm] = await Promise.all([
        axios.get(`${API_BASE}/twilio/contractor/dashboard`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        axios.get(`${API_BASE}/twilio/contractor/payout-readiness`, {
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => ({ data: null })),
        axios.get(`${API_BASE}/twilio/contractor/permissions/me`, {
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => ({ data: { permissions: [] } })),
      ]);
      setData(r.data);
      setPayoutReadiness(pr.data);
      setPermissions(pm.data?.permissions || []);
      setError(null);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 403) {
        setError({ code: 403 });
      } else if (status === 404) {
        setError({ code: 404 });
      } else {
        setError({ code: 'unknown', message: e?.message });
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/auth?next=/contractor/dashboard', { replace: true });
      return undefined;
    }
    if (user) fetchDashboard();
    return undefined;
  }, [authLoading, user, fetchDashboard, navigate]);

  // 60s auto-poll
  useEffect(() => {
    if (!token || error) return undefined;
    const t = setInterval(fetchDashboard, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [token, error, fetchDashboard]);

  const startStripeOnboarding = async () => {
    setOnboardingBusy(true);
    try {
      const r = await axios.post(`${API_BASE}/settlement/connect/onboard`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.data?.onboarding_url) {
        window.location.href = r.data.onboarding_url;
      } else {
        toast.error(fr ? 'Impossible d\u2019initier l\u2019inscription Stripe.' : 'Could not start Stripe onboarding.');
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec Stripe.' : 'Stripe onboarding failed.'));
    } finally {
      setOnboardingBusy(false);
    }
  };

  const copyReferral = async () => {
    const code = data?.referral_code;
    if (!code) return;
    const link = `${window.location.origin}/r/${code}`;
    try {
      await navigator.clipboard.writeText(link);
      toast.success(fr ? 'Lien copié !' : 'Link copied!');
    } catch {
      toast.error(fr ? 'Copie impossible.' : 'Copy failed.');
    }
  };

  // ─── Render gates ─────────────────────────────────────────────────
  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="contractor-dashboard-loading">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-3" />
        <span>{fr ? 'Chargement…' : 'Loading…'}</span>
      </div>
    );
  }

  if (error?.code === 403) {
    return (
      <div className="container mx-auto max-w-3xl py-12 px-4" data-testid="contractor-dashboard-403">
        <Card className="border-2 border-rose-300 bg-rose-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-rose-600 flex-shrink-0" />
            <div>
              <h2 className="font-semibold text-rose-900">
                {fr ? 'Accès refusé' : 'Access denied'}
              </h2>
              <p className="text-sm text-rose-800 mt-1">
                {fr
                  ? 'Ce tableau de bord est réservé aux contractants approuvés. Si vous pensez que c\u2019est une erreur, contactez l\u2019administrateur.'
                  : 'This dashboard is reserved for approved contractors. If you think this is a mistake, contact your administrator.'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto max-w-3xl py-12 px-4">
        <Card className="border-2 border-amber-300 bg-amber-50" data-testid="contractor-dashboard-error">
          <CardContent className="p-6">
            <p className="text-sm">
              {fr ? 'Erreur de chargement.' : 'Failed to load dashboard.'} {error.message || ''}
            </p>
            <Button variant="outline" onClick={fetchDashboard} className="mt-3">
              {fr ? 'Réessayer' : 'Retry'}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const earnings = data.earnings || {};
  const referred = data.referred_accounts || [];
  const history = data.commission_history || [];
  const callStats = data.call_stats || {};

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4 space-y-4" data-testid="contractor-dashboard-page">
      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="contractor-dashboard-title">
            <ShieldCheck className="h-7 w-7 text-indigo-600" />
            {fr ? 'Tableau de bord du contractant' : 'Contractor Dashboard'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {fr
              ? 'Gérez vos comptes recommandés, suivez vos gains et accédez au composeur BidVex.'
              : 'Manage your referred accounts, track commissions, and access the BidVex Dialer.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => navigate('/admin/dialer')}
            data-testid="goto-dialer-btn"
          >
            <PhoneCall className="h-4 w-4 mr-2" />
            {fr ? 'Ouvrir le composeur' : 'Open Dialer'}
          </Button>
          {(isContractor || isAdmin) && (
            <Button
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              onClick={copyReferral}
              data-testid="copy-referral-link-btn"
            >
              <Copy className="h-4 w-4 mr-2" />
              {fr ? 'Copier le lien de parrainage' : 'Copy referral link'}
            </Button>
          )}
        </div>
      </header>

      {/* iter316-D — Payout readiness HARD-BLOCK alert when contractor
          has accrued earnings but Stripe banking isn't ready. */}
      {payoutReadiness && !payoutReadiness.ready && payoutReadiness.accrued_total > 0 && (
        <Card
          className="border-2 border-rose-400 bg-rose-50 animate-pulse-slow"
          data-testid="banking-validation-alert"
        >
          <CardContent className="p-4 flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-rose-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-bold text-rose-900">
                {fr
                  ? `Action requise : ${formatMoney(payoutReadiness.accrued_total)} en attente`
                  : `Action required: ${formatMoney(payoutReadiness.accrued_total)} pending payout`}
              </p>
              <p className="text-sm text-rose-800 mt-1">
                {fr
                  ? 'Votre compte bancaire Stripe n\u2019est pas configuré. Sans cela, votre prochain versement automatique sera ignoré.'
                  : 'Your Stripe banking is not set up. Without it, your next automatic payout will be skipped.'}
              </p>
              <ul className="text-xs text-rose-700 mt-2 list-disc list-inside">
                {(payoutReadiness.blocked_reasons || []).map((r) => (
                  <li key={r} data-testid={`blocked-reason-${r}`}>
                    {{
                      no_stripe_account:     fr ? 'Aucun compte Stripe Connect' : 'No Stripe Connect account',
                      onboarding_incomplete: fr ? 'Onboarding Stripe incomplet'  : 'Stripe onboarding incomplete',
                      payouts_disabled:      fr ? 'Versements Stripe désactivés' : 'Stripe payouts disabled',
                      not_a_contractor:      fr ? 'Pas un contractant'            : 'Not a contractor',
                    }[r] || r}
                  </li>
                ))}
              </ul>
            </div>
            <Button
              onClick={startStripeOnboarding}
              disabled={onboardingBusy}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="banking-validation-resolve-btn"
            >
              {onboardingBusy ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Zap className="h-4 w-4 mr-1" />}
              {fr ? 'Résoudre maintenant' : 'Resolve now'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* iter316-D — Banking is configured & passing every check. */}
      {payoutReadiness && payoutReadiness.ready && (
        <Card className="border-emerald-200 bg-emerald-50" data-testid="banking-validation-ok">
          <CardContent className="p-3 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0" />
            <div className="text-sm">
              <p className="font-semibold text-emerald-900">
                {fr ? 'Versement Stripe vérifié.' : 'Stripe banking verified.'}
              </p>
              <p className="text-xs text-emerald-800">
                {fr
                  ? `Prochain versement automatique : ${new Date(payoutReadiness.next_payout_at).toLocaleDateString('fr-CA')}.`
                  : `Next automatic payout: ${new Date(payoutReadiness.next_payout_at).toLocaleDateString('en-CA')}.`}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stripe Connect status card */}
      <Card
        className={data.stripe_connected
          ? 'border-2 border-emerald-200 bg-emerald-50'
          : 'border-2 border-amber-300 bg-amber-50'}
        data-testid="stripe-status-card"
      >
        <CardContent className="p-4 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            {data.stripe_connected ? (
              <CheckCircle2 className="h-6 w-6 text-emerald-600" />
            ) : (
              <Zap className="h-6 w-6 text-amber-600" />
            )}
            <div>
              <p className="font-semibold text-sm">
                {data.stripe_connected
                  ? (fr ? 'Versements Stripe actifs' : 'Stripe payouts active')
                  : (fr ? 'Connectez Stripe pour recevoir vos versements' : 'Connect Stripe to receive payouts')}
              </p>
              <p className="text-xs text-slate-600 mt-0.5">
                {data.stripe_connected
                  ? (fr
                      ? 'Vos commissions mensuelles sont versées automatiquement le 1er de chaque mois.'
                      : 'Your monthly commissions are auto-transferred on the 1st of every month.')
                  : (fr
                      ? 'Sans Stripe, vos commissions resteront en attente — connectez votre compte pour les débloquer.'
                      : 'Without Stripe, commissions stay accrued — connect to unlock automatic payouts.')}
              </p>
            </div>
          </div>
          {!data.stripe_connected && (
            <Button
              onClick={startStripeOnboarding}
              disabled={onboardingBusy}
              className="bg-amber-600 hover:bg-amber-700 text-white"
              data-testid="stripe-connect-btn"
            >
              {onboardingBusy ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
              {fr ? 'Configurer Stripe' : 'Set up Stripe'}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* iter316-D — Permission-gated quick actions */}
      {permissions.length > 0 && (
        <Card className="border-indigo-200 bg-indigo-50" data-testid="contractor-permissions-card">
          <CardContent className="p-4">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <h3 className="font-semibold flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-indigo-600" />
                  {fr ? 'Ce que vous pouvez faire' : 'What you can do'}
                </h3>
                <p className="text-xs text-slate-600 mt-1">
                  {fr
                    ? 'Permissions accordées par votre administrateur.'
                    : 'Permissions granted by your administrator.'}
                </p>
                <div className="flex flex-wrap gap-1 mt-2" data-testid="contractor-permissions-list">
                  {permissions.map((p) => (
                    <Badge key={p} className="bg-indigo-100 text-indigo-800 border-indigo-300" data-testid={`granted-permission-${p}`}>
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      {{
                        add_users:             fr ? 'Ajouter des utilisateurs' : 'Add users',
                        manage_subscriptions:  fr ? 'Gérer les abonnements'    : 'Manage subscriptions',
                        view_referral_emails:  fr ? 'Voir les emails'          : 'View referral emails',
                      }[p] || p}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {permissions.includes('add_users') && (
                  <Button
                    onClick={() => setAddClientOpen(true)}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white"
                    data-testid="contractor-add-client-btn"
                  >
                    <UserPlus className="h-4 w-4 mr-1" />
                    {fr ? 'Ajouter un client' : 'Add Client'}
                  </Button>
                )}
                {permissions.includes('manage_subscriptions') && (
                  <Button
                    variant="outline"
                    onClick={() => toast.info(
                      fr
                        ? 'Pour gérer un abonnement, contactez votre administrateur ou utilisez l\u2019espace client.'
                        : 'To manage a subscription, contact your administrator or use the client portal.',
                    )}
                    data-testid="contractor-manage-subs-btn"
                  >
                    {fr ? 'Gérer les abonnements' : 'Manage Subscriptions'}
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Earnings stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="earnings-grid">
        <StatCard
          label={fr ? 'Accumulé (non versé)' : 'Accrued (unpaid)'}
          value={formatMoney(earnings.lifetime_accrued)}
          icon={DollarSign}
          testid="stat-accrued"
        />
        <StatCard
          label={fr ? 'Versé à vie' : 'Lifetime paid'}
          value={formatMoney(earnings.lifetime_paid)}
          icon={CheckCircle2}
          testid="stat-paid"
        />
        <StatCard
          label={fr ? 'Ce mois-ci' : 'This month'}
          value={formatMoney(earnings.this_month_accrued)}
          icon={TrendingUpIcon}
          testid="stat-month"
        />
        <StatCard
          label={fr ? 'Comptes parrainés' : 'Referred accounts'}
          value={referred.length}
          icon={Users}
          testid="stat-referrals"
        />
      </div>

      {/* Call stats */}
      <Card data-testid="call-stats-card">
        <CardContent className="p-4">
          <h2 className="font-semibold text-lg mb-3 flex items-center gap-2">
            <PhoneCall className="h-5 w-5" />
            {fr ? 'Activité du composeur' : 'Dialer activity'}
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg border p-3" data-testid="call-stat-today">
              <p className="text-xs text-slate-500">{fr ? "Aujourd'hui" : 'Today'}</p>
              <p className="text-xl font-bold">{callStats.today || 0}</p>
            </div>
            <div className="rounded-lg border p-3" data-testid="call-stat-month">
              <p className="text-xs text-slate-500">{fr ? 'Ce mois-ci' : 'This month'}</p>
              <p className="text-xl font-bold">{callStats.this_month || 0}</p>
            </div>
            <div className="rounded-lg border p-3" data-testid="call-stat-lifetime">
              <p className="text-xs text-slate-500">{fr ? 'À vie' : 'Lifetime'}</p>
              <p className="text-xl font-bold">{callStats.lifetime || 0}</p>
            </div>
            <div className="rounded-lg border p-3" data-testid="call-stat-accounts">
              <p className="text-xs text-slate-500">{fr ? 'Comptes créés' : 'Accounts created'}</p>
              <p className="text-xl font-bold">{callStats.accounts_created || 0}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Referred accounts */}
      <Card data-testid="referred-accounts-card">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h2 className="font-semibold text-lg flex items-center gap-2">
              <Users className="h-5 w-5" />
              {fr ? 'Comptes parrainés' : 'Referred accounts'}
            </h2>
            {data.referral_code && (
              <div className="flex items-center gap-2">
                <LinkIcon className="h-4 w-4 text-slate-500" />
                <span className="text-xs font-mono px-2 py-0.5 bg-slate-100 rounded">
                  /r/{data.referral_code}
                </span>
              </div>
            )}
          </div>
          {referred.length === 0 ? (
            <p className="text-sm text-slate-500 py-4 text-center" data-testid="referred-empty">
              {fr ? 'Aucun compte parrainé pour l\u2019instant.' : 'No referred accounts yet.'}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="referred-table">
                <thead>
                  <tr className="text-xs text-slate-500 border-b">
                    <th className="text-left py-2 pr-2">{fr ? 'Compte' : 'Account'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Type' : 'Type'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Statut' : 'Status'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Créé le' : 'Created'}</th>
                  </tr>
                </thead>
                <tbody>
                  {referred.map((acc, idx) => (
                    <tr key={acc.id || idx} className="border-b" data-testid={`referred-row-${idx}`}>
                      <td className="py-2 pr-2">
                        <p className="font-medium">{acc.name || acc.id}</p>
                        <p className="text-xs text-slate-500 font-mono">{acc.id?.slice(0, 8)}</p>
                      </td>
                      <td className="py-2 pr-2">
                        <Badge variant="outline">{acc.account_type || '—'}</Badge>
                      </td>
                      <td className="py-2 pr-2">
                        {acc.is_demo ? (
                          <Badge className="bg-amber-100 text-amber-800">{fr ? 'Démo' : 'Demo'}</Badge>
                        ) : (
                          <Badge className="bg-emerald-100 text-emerald-800">{fr ? 'Actif' : 'Live'}</Badge>
                        )}
                      </td>
                      <td className="py-2 pr-2 text-xs text-slate-600">
                        {acc.created_at ? new Date(acc.created_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Commission history */}
      <Card data-testid="commission-history-card">
        <CardContent className="p-4">
          <h2 className="font-semibold text-lg mb-3 flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            {fr ? 'Historique des commissions' : 'Commission history'}
          </h2>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500 py-4 text-center" data-testid="commission-history-empty">
              {fr ? 'Aucune commission pour l\u2019instant.' : 'No commission entries yet.'}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-slate-500 border-b">
                    <th className="text-left py-2 pr-2">{fr ? 'Date' : 'Date'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Compte' : 'Account'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Source' : 'Source'}</th>
                    <th className="text-right py-2 pr-2">{fr ? 'Taux' : 'Rate'}</th>
                    <th className="text-right py-2 pr-2">{fr ? 'Montant' : 'Amount'}</th>
                    <th className="text-left py-2 pr-2">{fr ? 'Statut' : 'Status'}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, idx) => (
                    <tr key={h.id || idx} className="border-b" data-testid={`commission-row-${idx}`}>
                      <td className="py-2 pr-2 text-xs">
                        {h.created_at ? new Date(h.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-2 pr-2 text-xs font-mono">{h.source_account_id?.slice(0, 8) || '—'}</td>
                      <td className="py-2 pr-2 text-xs">{h.section || '—'}</td>
                      <td className="py-2 pr-2 text-right text-xs">{((h.commission_rate_applied || h.rate || 0) * 100).toFixed(1)}%</td>
                      <td className="py-2 pr-2 text-right font-semibold">{formatMoney(h.commission_amount)}</td>
                      <td className="py-2 pr-2">
                        <Badge className={h.status === 'paid' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}>
                          {h.status || 'accrued'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* iter316-D — Add Client modal (rendered when permission granted) */}
      {addClientOpen && (
        <AddClientDialog
          token={token}
          fr={fr}
          onClose={() => setAddClientOpen(false)}
          onCreated={() => {
            setAddClientOpen(false);
            fetchDashboard();
          }}
        />
      )}
    </div>
  );
}

// ─── Sub-component: Add Client Dialog (permission-gated) ────────────

function AddClientDialog({ token, fr, onClose, onCreated }) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [province, setProvince] = useState('QC');
  const [accountType, setAccountType] = useState('individual_seller');
  const [busy, setBusy] = useState(false);
  const [inviteUrl, setInviteUrl] = useState(null);

  const submit = async () => {
    if (!email.includes('@')) {
      toast.error(fr ? 'Email valide requis.' : 'Valid email required.');
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(
        `${API_BASE}/twilio/contractor/clients`,
        { email: email.trim().toLowerCase(), name, phone, province, account_type: accountType },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const url = `${window.location.origin}/reset-password?token=${r.data.invite_token}`;
      setInviteUrl(url);
      try { await navigator.clipboard.writeText(url); } catch { /* noop */ }
      setTimeout(onCreated, 2000);
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' ? (fr ? d?.message_fr : d?.message_en) : d) || e?.message;
      toast.error(msg || (fr ? 'Échec.' : 'Failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="contractor-add-client-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            {fr ? 'Ajouter un client' : 'Add a Client'}
          </DialogTitle>
          <DialogDescription>
            {fr
              ? 'Crée un nouveau compte client attribué à vous. Ils recevront un lien d\u2019invitation pour définir leur mot de passe.'
              : 'Creates a new client account attributed to you. They receive an invite link to set their password.'}
          </DialogDescription>
        </DialogHeader>
        {inviteUrl ? (
          <div className="space-y-2" data-testid="add-client-success">
            <p className="text-sm text-emerald-700 font-semibold flex items-center gap-1">
              <CheckCircle2 className="h-4 w-4" />
              {fr ? 'Client créé ! Lien copié :' : 'Client created! Link copied:'}
            </p>
            <Input value={inviteUrl} readOnly className="font-mono text-xs" data-testid="client-invite-link" />
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold">{fr ? 'Email *' : 'Email *'}</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="client@example.com"
                data-testid="add-client-email"
              />
            </div>
            <div>
              <label className="text-xs font-semibold">{fr ? 'Nom complet' : 'Full name'}</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="add-client-name"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold">{fr ? 'Téléphone' : 'Phone'}</label>
                <Input value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="add-client-phone" />
              </div>
              <div>
                <label className="text-xs font-semibold">{fr ? 'Province' : 'Province'}</label>
                <Input value={province} onChange={(e) => setProvince(e.target.value.toUpperCase())} maxLength={2} data-testid="add-client-province" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold">{fr ? 'Type de compte' : 'Account type'}</label>
              <select
                value={accountType}
                onChange={(e) => setAccountType(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                data-testid="add-client-type"
              >
                <option value="individual_seller">{fr ? 'Vendeur individuel' : 'Individual Seller'}</option>
                <option value="vehicle_dealer">{fr ? 'Concessionnaire' : 'Vehicle Dealer'}</option>
                <option value="partner">{fr ? 'Partenaire' : 'Partner'}</option>
                <option value="broker">{fr ? 'Courtier' : 'Broker'}</option>
                <option value="liquidator">{fr ? 'Liquidateur' : 'Liquidator'}</option>
              </select>
            </div>
          </div>
        )}
        <DialogFooter>
          {!inviteUrl && (
            <>
              <Button variant="outline" onClick={onClose} disabled={busy} data-testid="add-client-cancel-btn">
                <X className="h-4 w-4 mr-1" />
                {fr ? 'Annuler' : 'Cancel'}
              </Button>
              <Button
                onClick={submit}
                disabled={busy}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                data-testid="add-client-submit-btn"
              >
                {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
                {fr ? 'Créer' : 'Create'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Tiny trending-up icon to avoid pulling another import for a single use.
function TrendingUpIcon(props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  );
}
