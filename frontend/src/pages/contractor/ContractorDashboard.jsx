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
  AlertTriangle, Zap, Loader2, ShieldCheck,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';

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

  // Server-enforced via 403; the client-side gate avoids needless calls.
  const isContractor = user && (user.role === 'dialer_contractor');
  const isAdmin = user && (user.role === 'admin' || user.role === 'super_admin');

  const fetchDashboard = useCallback(async () => {
    if (!token) return;
    try {
      const r = await axios.get(`${API_BASE}/twilio/contractor/dashboard`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
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
    </div>
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
