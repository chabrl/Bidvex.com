import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  DollarSign, 
  TrendingUp, 
  Clock, 
  Wallet,
  Building2,
  ExternalLink,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  FileText,
  RefreshCw,
  CreditCard,
  ArrowUpRight,
  Calendar
} from 'lucide-react';

const API = API_BASE;

const SellerEarningsDashboard = () => {
  const { t, i18n } = useTranslation();
  const isFrench = i18n.language === 'fr';
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [earnings, setEarnings] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [connectStatus, setConnectStatus] = useState(null);
  
  useEffect(() => {
    fetchAllData();
  }, []);
  
  const fetchAllData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = localStorage.getItem('token');
      if (!token) {
        setError(isFrench ? 'Authentification requise' : 'Authentication required');
        return;
      }
      
      const headers = { Authorization: `Bearer ${token}` };
      
      // Fetch earnings
      const earningsRes = await axios.get(`${API}/payments/seller/earnings`, { headers });
      setEarnings(earningsRes.data);
      
      // Fetch Connect status
      const connectRes = await axios.get(`${API}/users/me/stripe-connect/status`, { headers });
      setConnectStatus(connectRes.data);
      
      // Fetch transactions
      if (earningsRes.data.has_connect_account) {
        const txRes = await axios.get(`${API}/payments/seller/transactions?limit=10`, { headers });
        setTransactions(txRes.data.transactions || []);
      }
      
    } catch (err) {
      console.error('Failed to load seller earnings:', err);
      setError(err.response?.data?.detail || 'Failed to load earnings data');
    } finally {
      setLoading(false);
    }
  };
  
  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAllData();
    setRefreshing(false);
  };
  
  const handleManageBankInfo = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API}/users/me/stripe-connect/dashboard-link`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      window.open(response.data.dashboard_url, '_blank');
      
    } catch (err) {
      console.error('Failed to get dashboard link:', err);
      setError(err.response?.data?.detail || 'Failed to open Stripe Dashboard');
    }
  };
  
  const handleStartOnboarding = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API}/users/me/stripe-connect/onboard`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      window.location.href = response.data.onboarding_url;
      
    } catch (err) {
      console.error('Failed to start onboarding:', err);
      setError(err.response?.data?.detail || 'Failed to start seller onboarding');
    }
  };
  
  const formatCurrency = (amount) => {
    if (!amount && amount !== 0) return '$0.00';
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };
  
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString(isFrench ? 'fr-CA' : 'en-CA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };
  
  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }
  
  // Not a seller / No Connect account
  if (!earnings?.has_connect_account) {
    return (
      <div className="space-y-6">
        <Card className="border-dashed">
          <CardContent className="p-8 text-center">
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mx-auto mb-4">
              <Building2 className="h-8 w-8 text-blue-600 dark:text-blue-400" />
            </div>
            <h2 className="text-2xl font-bold mb-2">
              {isFrench ? 'Devenez vendeur sur BidVex' : 'Become a Seller on BidVex'}
            </h2>
            <p className="text-slate-600 dark:text-slate-400 mb-6 max-w-md mx-auto">
              {isFrench 
                ? 'Complétez l\'inscription Stripe Connect pour commencer à vendre et recevoir des paiements.'
                : 'Complete Stripe Connect onboarding to start selling and receiving payments.'}
            </p>
            
            <div className="grid sm:grid-cols-3 gap-4 mb-6 max-w-lg mx-auto">
              <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <DollarSign className="h-6 w-6 text-green-600 mx-auto mb-2" />
                <p className="text-sm font-medium">{isFrench ? 'Paiements sécurisés' : 'Secure Payouts'}</p>
              </div>
              <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <Clock className="h-6 w-6 text-blue-600 mx-auto mb-2" />
                <p className="text-sm font-medium">{isFrench ? 'Virements rapides' : 'Fast Transfers'}</p>
              </div>
              <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <TrendingUp className="h-6 w-6 text-purple-600 mx-auto mb-2" />
                <p className="text-sm font-medium">{isFrench ? 'Tableau de bord' : 'Analytics'}</p>
              </div>
            </div>
            
            <Button size="lg" onClick={handleStartOnboarding} data-testid="start-seller-onboarding-btn">
              <Building2 className="mr-2 h-5 w-5" />
              {isFrench ? 'Commencer l\'inscription' : 'Start Onboarding'}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  const metrics = earnings.financial_metrics || {};
  
  return (
    <div className="space-y-6" data-testid="seller-earnings-dashboard">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Wallet className="h-6 w-6 text-primary" />
            {isFrench ? 'Tableau de bord vendeur' : 'Seller Earnings Dashboard'}
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            {isFrench ? 'Gérez vos revenus et paiements' : 'Manage your earnings and payouts'}
          </p>
        </div>
        
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            {isFrench ? 'Actualiser' : 'Refresh'}
          </Button>
          <Button onClick={handleManageBankInfo} data-testid="manage-bank-info-btn">
            <CreditCard className="mr-2 h-4 w-4" />
            {isFrench ? 'Gérer les infos bancaires' : 'Manage Bank Info'}
            <ExternalLink className="ml-2 h-3 w-3" />
          </Button>
        </div>
      </div>
      
      {/* Account Status Alert */}
      {connectStatus && !connectStatus.payouts_enabled && (
        <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-700 dark:text-amber-400">
            <strong>{isFrench ? 'Action requise:' : 'Action Required:'}</strong>{' '}
            {isFrench 
              ? 'Complétez votre profil Stripe pour activer les paiements.'
              : 'Complete your Stripe profile to enable payouts.'}
            <Button 
              variant="link" 
              className="p-0 h-auto ml-2 text-amber-700 underline"
              onClick={handleManageBankInfo}
            >
              {isFrench ? 'Compléter maintenant' : 'Complete now'}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      
      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      {/* Financial Metrics */}
      <div className="grid sm:grid-cols-3 gap-4">
        {/* Total Earned */}
        <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 border-green-200 dark:border-green-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-green-700 dark:text-green-400">
                {isFrench ? 'Total gagné' : 'Total Earned'}
              </span>
              <TrendingUp className="h-5 w-5 text-green-600" />
            </div>
            <p className="text-3xl font-bold text-green-800 dark:text-green-300">
              {metrics.total_earned_display || '$0.00'}
            </p>
            <p className="text-xs text-green-600 mt-1">
              {isFrench ? 'Depuis le début' : 'All time'}
            </p>
          </CardContent>
        </Card>
        
        {/* Pending Payouts */}
        <Card className="bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950 border-amber-200 dark:border-amber-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
                {isFrench ? 'En attente' : 'Pending Payouts'}
              </span>
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <p className="text-3xl font-bold text-amber-800 dark:text-amber-300">
              {metrics.pending_payouts_display || '$0.00'}
            </p>
            <p className="text-xs text-amber-600 mt-1">
              {isFrench ? 'En cours de traitement' : 'Being processed'}
            </p>
          </CardContent>
        </Card>
        
        {/* Available Balance */}
        <Card className="bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950 border-blue-200 dark:border-blue-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-700 dark:text-blue-400">
                {isFrench ? 'Solde disponible' : 'Available Balance'}
              </span>
              <Wallet className="h-5 w-5 text-blue-600" />
            </div>
            <p className="text-3xl font-bold text-blue-800 dark:text-blue-300">
              {metrics.available_balance_display || '$0.00'}
            </p>
            <p className="text-xs text-blue-600 mt-1">
              {isFrench ? 'Prêt pour virement' : 'Ready for payout'}
            </p>
          </CardContent>
        </Card>
      </div>
      
      {/* Recent Payouts */}
      {earnings.recent_payouts && earnings.recent_payouts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <ArrowUpRight className="h-5 w-5" />
              {isFrench ? 'Virements récents' : 'Recent Payouts'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {earnings.recent_payouts.map((payout) => (
                <div 
                  key={payout.id} 
                  className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${
                      payout.status === 'paid' ? 'bg-green-500' : 
                      payout.status === 'pending' ? 'bg-amber-500' : 'bg-slate-400'
                    }`} />
                    <div>
                      <p className="font-medium">{formatCurrency(payout.amount)}</p>
                      <p className="text-xs text-slate-500">
                        <Calendar className="inline h-3 w-3 mr-1" />
                        {formatDate(payout.arrival_date)}
                      </p>
                    </div>
                  </div>
                  <Badge variant={payout.status === 'paid' ? 'default' : 'secondary'}>
                    {payout.status === 'paid' 
                      ? (isFrench ? 'Payé' : 'Paid')
                      : (isFrench ? 'En attente' : 'Pending')}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Recent Transactions */}
      {transactions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {isFrench ? 'Transactions récentes' : 'Recent Transactions'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3 text-sm font-medium text-slate-600">
                      {isFrench ? 'Date' : 'Date'}
                    </th>
                    <th className="text-left py-2 px-3 text-sm font-medium text-slate-600">
                      {isFrench ? 'Type' : 'Type'}
                    </th>
                    <th className="text-right py-2 px-3 text-sm font-medium text-slate-600">
                      {isFrench ? 'Prix au marteau' : 'Hammer Price'}
                    </th>
                    <th className="text-right py-2 px-3 text-sm font-medium text-slate-600">
                      {isFrench ? 'Commission' : 'Commission'}
                    </th>
                    <th className="text-right py-2 px-3 text-sm font-medium text-slate-600">
                      {isFrench ? 'Net' : 'Net Payout'}
                    </th>
                    <th className="text-center py-2 px-3 text-sm font-medium text-slate-600">
                      {isFrench ? 'Facture' : 'Invoice'}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.id} className="border-b last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800">
                      <td className="py-3 px-3 text-sm">
                        {formatDate(tx.created_at)}
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant="outline" className="text-xs">
                          {tx.type === 'marketplace_purchase' 
                            ? (isFrench ? 'Vente' : 'Sale')
                            : tx.type}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-sm text-right">
                        {formatCurrency(tx.hammer_price)}
                      </td>
                      <td className="py-3 px-3 text-sm text-right text-red-600">
                        -{formatCurrency(tx.seller_commission)}
                      </td>
                      <td className="py-3 px-3 text-sm text-right font-medium text-green-600">
                        {formatCurrency(tx.seller_payout)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {tx.pdf_url ? (
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => window.open(tx.pdf_url, '_blank')}
                          >
                            <FileText className="h-4 w-4" />
                          </Button>
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Account Info Footer */}
      <Card className="bg-slate-50 dark:bg-slate-800">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              {earnings.payouts_enabled ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-600" />
              )}
              <span className="text-sm">
                {isFrench ? 'Compte Stripe:' : 'Stripe Account:'}{' '}
                <span className="font-mono text-xs">{earnings.account_id}</span>
              </span>
            </div>
            <div className="flex gap-2">
              <Badge variant={earnings.payouts_enabled ? 'default' : 'secondary'}>
                {earnings.payouts_enabled 
                  ? (isFrench ? 'Paiements activés' : 'Payouts Enabled')
                  : (isFrench ? 'Configuration requise' : 'Setup Required')}
              </Badge>
              <Badge variant={earnings.charges_enabled ? 'default' : 'secondary'}>
                {earnings.charges_enabled 
                  ? (isFrench ? 'Charges activées' : 'Charges Enabled')
                  : (isFrench ? 'Charges désactivées' : 'Charges Disabled')}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SellerEarningsDashboard;
