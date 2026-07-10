import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import {
  DollarSign, Users, TrendingUp, Copy, ExternalLink, Link2,
  Wallet, CreditCard, CheckCircle2, AlertTriangle, Clock,
  RefreshCw, Building2, Loader2
} from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';
import { AffiliateEarningsWidget } from '../components/AffiliateEarningsWidget';

const API = API_BASE;

const AffiliateDashboard = () => {
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();
  const isFrench = i18n.language?.startsWith('fr');

  const [stats, setStats] = useState(null);
  const [connectStatus, setConnectStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const headers = { Authorization: `Bearer ${token}` };
      const [statsRes, connectRes] = await Promise.all([
        axios.get(`${API}/affiliate/stats`, { headers }),
        axios.get(`${API}/users/me/stripe-connect/status`, { headers }).catch(() => ({ data: { has_account: false } })),
      ]);
      setStats(statsRes.data);
      setConnectStatus(connectRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load affiliate data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const copyReferralLink = () => {
    if (stats?.referral_link) {
      navigator.clipboard.writeText(stats.referral_link);
      toast.success(isFrench ? 'Lien copié!' : 'Referral link copied!');
    }
  };

  const handleManageBankInfo = async () => {
    try {
      const response = await axios.post(`${API}/users/me/stripe-connect/dashboard-link`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data.type === 'onboarding') {
        window.location.href = response.data.url;
      } else {
        window.open(response.data.url, '_blank');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to open Stripe Dashboard');
    }
  };

  const handleStartOnboarding = async () => {
    try {
      const response = await axios.post(`${API}/users/me/stripe-connect/onboard`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      window.location.href = response.data.onboarding_url;
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start onboarding');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const hasConnect = connectStatus?.has_account;
  const payoutsEnabled = connectStatus?.payouts_enabled;

  return (
    <div className="min-h-screen py-8 px-4" data-testid="affiliate-dashboard">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Users className="h-6 w-6 text-primary" />
              {isFrench ? 'Centre d\'affiliation' : 'Affiliate Center'}
            </h1>
            <p className="text-slate-600 dark:text-slate-400">
              {isFrench ? 'Partagez, référez et gagnez des commissions' : 'Share, refer, and earn commissions'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleRefresh} disabled={refreshing} data-testid="affiliate-refresh-btn">
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              {isFrench ? 'Actualiser' : 'Refresh'}
            </Button>
            {hasConnect && (
              <Button onClick={handleManageBankInfo} data-testid="affiliate-bank-info-btn">
                <CreditCard className="mr-2 h-4 w-4" />
                {payoutsEnabled
                  ? (isFrench ? 'Gérer les infos bancaires' : 'Manage Bank Info')
                  : (isFrench ? 'Compléter le profil Stripe' : 'Complete Stripe Setup')}
                <ExternalLink className="ml-2 h-3 w-3" />
              </Button>
            )}
          </div>
        </div>

        {/* Payout Setup Alert */}
        {!hasConnect && (
          <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950">
            <Building2 className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-700 dark:text-blue-400">
              <strong>{isFrench ? 'Configuration requise:' : 'Setup Required:'}</strong>{' '}
              {isFrench
                ? 'Connectez votre compte bancaire pour recevoir vos commissions automatiquement.'
                : 'Connect your bank account to receive affiliate commissions automatically.'}
              <Button variant="link" className="p-0 h-auto ml-2 text-blue-700 underline" onClick={handleStartOnboarding}>
                {isFrench ? 'Configurer maintenant' : 'Set up now'}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {hasConnect && !payoutsEnabled && (
          <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-700 dark:text-amber-400">
              <strong>{isFrench ? 'Action requise:' : 'Action Required:'}</strong>{' '}
              {isFrench
                ? 'Complétez votre profil Stripe pour activer les paiements.'
                : 'Complete your Stripe profile to enable payouts.'}
              <Button variant="link" className="p-0 h-auto ml-2 text-amber-700 underline" onClick={handleManageBankInfo}>
                {isFrench ? 'Compléter maintenant' : 'Complete now'}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Referral Link Card */}
        <Card className="border-primary/30" data-testid="referral-link-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Link2 className="h-5 w-5 text-primary" />
              {isFrench ? 'Votre lien de référence' : 'Your Referral Link'}
            </CardTitle>
            <CardDescription>
              {isFrench
                ? "Partagez ce lien — vous gagnez 3 % du profit net de BidVex sur chaque transaction (frais d'enchères et abonnements) des utilisateurs que vous référez, à vie."
                : "Share this link — you earn 3% of BidVex's net platform profit on every transaction (auction fees & subscriptions) from users you refer, for life."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded-lg px-4 py-3 font-mono text-sm truncate" data-testid="referral-link-display">
                {stats?.referral_link || '...'}
              </div>
              <Button onClick={copyReferralLink} className="shrink-0 gap-2" data-testid="copy-referral-link-btn">
                <Copy className="h-4 w-4" />
                {isFrench ? 'Copier' : 'Copy'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {isFrench ? 'Code:' : 'Code:'} <span className="font-mono font-bold">{stats?.affiliate_code || '—'}</span>
              {' '}| {isFrench ? 'Cookie de suivi: 30 jours' : 'Tracking cookie: 30 days'}
            </p>
          </CardContent>
        </Card>

        {/* iter339 — Earnings widget + activity feed */}
        <AffiliateEarningsWidget />

        {/* Metrics */}
        <div className="grid sm:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 border-green-200 dark:border-green-800">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-green-700 dark:text-green-400">{isFrench ? 'Total gagné' : 'Total Earned'}</span>
                <DollarSign className="h-5 w-5 text-green-600" />
              </div>
              <p className="text-2xl font-bold text-green-800 dark:text-green-300" data-testid="total-earnings">
                {formatCurrency(stats?.total_earnings || 0)}
              </p>
              <p className="text-xs text-green-600 dark:text-green-500">{isFrench ? 'Depuis le début' : 'All time'}</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950 border-amber-200 dark:border-amber-800">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-amber-700 dark:text-amber-400">{isFrench ? 'En attente' : 'Pending'}</span>
                <Clock className="h-5 w-5 text-amber-600" />
              </div>
              <p className="text-2xl font-bold text-amber-800 dark:text-amber-300" data-testid="pending-earnings">
                {formatCurrency(stats?.pending_earnings || 0)}
              </p>
              <p className="text-xs text-amber-600 dark:text-amber-500">{isFrench ? 'Versement dans 7 jours' : 'Paid out in 7 days'}</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950 border-blue-200 dark:border-blue-800">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-blue-700 dark:text-blue-400">{isFrench ? 'Références' : 'Referrals'}</span>
                <Users className="h-5 w-5 text-blue-600" />
              </div>
              <p className="text-2xl font-bold text-blue-800 dark:text-blue-300" data-testid="total-referrals">
                {stats?.total_referrals || 0}
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-500">{stats?.active_referrals || 0} {isFrench ? 'actives' : 'active'}</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-purple-50 to-fuchsia-50 dark:from-purple-950 dark:to-fuchsia-950 border-purple-200 dark:border-purple-800">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-purple-700 dark:text-purple-400">{isFrench ? 'Versé' : 'Paid Out'}</span>
                <Wallet className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-2xl font-bold text-purple-800 dark:text-purple-300" data-testid="paid-earnings">
                {formatCurrency(stats?.paid_earnings || 0)}
              </p>
              <p className="text-xs text-purple-600 dark:text-purple-500">{isFrench ? 'Transféré' : 'Transferred'}</p>
            </CardContent>
          </Card>
        </div>

        {/* How it works */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">{isFrench ? 'Comment ça fonctionne' : 'How It Works'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-3 gap-6">
              <div className="text-center p-4">
                <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center mx-auto mb-3">
                  <Link2 className="h-5 w-5 text-blue-600" />
                </div>
                <h3 className="font-semibold mb-1">{isFrench ? '1. Partagez' : '1. Share'}</h3>
                <p className="text-sm text-muted-foreground">
                  {isFrench ? 'Envoyez votre lien unique à vos contacts.' : 'Send your unique referral link to your contacts.'}
                </p>
              </div>
              <div className="text-center p-4">
                <div className="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center mx-auto mb-3">
                  <Users className="h-5 w-5 text-green-600" />
                </div>
                <h3 className="font-semibold mb-1">{isFrench ? '2. Ils achètent' : '2. They Buy'}</h3>
                <p className="text-sm text-muted-foreground">
                  {isFrench ? 'Quand ils font un achat, vous gagnez une commission.' : 'When they make a purchase, you earn a commission.'}
                </p>
              </div>
              <div className="text-center p-4">
                <div className="w-10 h-10 rounded-full bg-purple-100 dark:bg-purple-900 flex items-center justify-center mx-auto mb-3">
                  <DollarSign className="h-5 w-5 text-purple-600" />
                </div>
                <h3 className="font-semibold mb-1">{isFrench ? '3. Vous êtes payé' : '3. Get Paid'}</h3>
                <p className="text-sm text-muted-foreground">
                  {isFrench ? "3 % du profit de BidVex sur chaque transaction — crédité pour approbation par l'admin." : "3% of BidVex's profit on each transaction — credited for admin approval."}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Referrals Table */}
        {stats?.referrals?.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">{isFrench ? 'Vos références' : 'Your Referrals'}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="pb-2 font-medium text-muted-foreground">{isFrench ? 'Utilisateur' : 'User'}</th>
                      <th className="pb-2 font-medium text-muted-foreground">{isFrench ? 'Date' : 'Date'}</th>
                      <th className="pb-2 font-medium text-muted-foreground">{isFrench ? 'Statut' : 'Status'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.referrals.map((ref, i) => (
                      <tr key={ref.id || i} className="border-b last:border-0">
                        <td className="py-3 font-mono text-xs">{ref.referred_email ? `${ref.referred_email.slice(0, 3)}***` : '—'}</td>
                        <td className="py-3 text-muted-foreground">{ref.created_at ? new Date(ref.created_at).toLocaleDateString() : '—'}</td>
                        <td className="py-3">
                          <Badge variant={ref.status === 'converted' ? 'default' : 'secondary'} data-testid={`referral-status-${i}`}>
                            {ref.status === 'converted'
                              ? (isFrench ? 'Converti' : 'Converted')
                              : (isFrench ? 'En attente' : 'Pending')}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Earnings History */}
        {stats?.earnings_history?.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">{isFrench ? 'Historique des commissions' : 'Commission History'}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="pb-2 font-medium text-muted-foreground">{isFrench ? 'Date' : 'Date'}</th>
                      <th className="pb-2 font-medium text-muted-foreground">{isFrench ? 'Montant' : 'Amount'}</th>
                      <th className="pb-2 font-medium text-muted-foreground">{isFrench ? 'Statut' : 'Status'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.earnings_history.map((e, i) => (
                      <tr key={e.id || i} className="border-b last:border-0">
                        <td className="py-3 text-muted-foreground">{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                        <td className="py-3 font-semibold text-green-700 dark:text-green-400">{formatCurrency(e.commission_amount)}</td>
                        <td className="py-3">
                          <Badge variant={e.status === 'transferred' ? 'default' : e.status === 'pending' ? 'secondary' : 'outline'}>
                            {e.status === 'transferred'
                              ? (isFrench ? 'Transféré' : 'Transferred')
                              : e.status === 'pending'
                                ? (isFrench ? 'En attente' : 'Pending')
                                : e.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Account Footer */}
        {hasConnect && (
          <Card className="bg-slate-50 dark:bg-slate-800">
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  {payoutsEnabled ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-amber-600" />
                  )}
                  <span className="text-sm">
                    {isFrench ? 'Compte Stripe:' : 'Stripe Account:'}{' '}
                    <span className="font-mono text-xs" title={isFrench ? 'Votre identifiant marchand unique pour les paiements sécurisés.' : 'This is your unique merchant identifier for secure payments.'}>
                      {'••••'}{(connectStatus?.account_id || '').slice(-4)}
                    </span>
                  </span>
                </div>
                <Badge variant={payoutsEnabled ? 'default' : 'secondary'}>
                  {payoutsEnabled
                    ? (isFrench ? 'Paiements activés' : 'Payouts Enabled')
                    : (isFrench ? 'Configuration requise' : 'Setup Required')}
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default AffiliateDashboard;
