import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import { DollarSign, Users, TrendingUp, Copy, ExternalLink, Download } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AffiliateDashboard = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [withdrawAmount, setWithdrawAmount] = useState('');

  useEffect(() => {
    fetchAffiliateStats();
  }, []);

  const fetchAffiliateStats = async () => {
    try {
      const response = await axios.get(`${API}/affiliate/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch affiliate stats:', error);
      toast.error(t('affiliate.loadFailed', 'Failed to load affiliate data'));
    } finally {
      setLoading(false);
    }
  };

  const copyReferralLink = () => {
    if (stats?.referral_link) {
      navigator.clipboard.writeText(stats.referral_link);
      toast.success(t('affiliate.linkCopied'));
    }
  };

  const handleWithdraw = async () => {
    if (!withdrawAmount || parseFloat(withdrawAmount) <= 0) {
      toast.error(t('affiliate.enterValidAmount', 'Please enter a valid amount'));
      return;
    }

    if (parseFloat(withdrawAmount) > stats?.pending_earnings) {
      toast.error(t('affiliate.insufficientBalance', 'Insufficient balance'));
      return;
    }

    try {
      await axios.post(`${API}/affiliate/withdraw`, {
        amount: parseFloat(withdrawAmount),
        method: 'bank_transfer'
      });
      toast.success(t('affiliate.withdrawalSubmitted', 'Withdrawal request submitted!'));
      setWithdrawAmount('');
      fetchAffiliateStats();
    } catch (error) {
      toast.error(t('affiliate.withdrawalFailed', 'Failed to submit withdrawal request'));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="affiliate-dashboard">
      <div className="max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">{t('affiliate.dashboard')}</h1>
          <p className="text-muted-foreground">{t('affiliate.description', 'Earn 3% commission on every sale from your referrals')}</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('affiliate.totalClicks')}</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.total_clicks || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('affiliate.conversions')}</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.total_referrals || 0}</div>
              <p className="text-xs text-muted-foreground">
                {stats?.conversion_rate || 0}% {t('affiliate.conversionRate')}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('affiliate.pendingCommission')}</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">${(stats?.pending_earnings || 0).toFixed(2)}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('affiliate.paidCommission')}</CardTitle>
              <DollarSign className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">${(stats?.paid_earnings || 0).toFixed(2)}</div>
            </CardContent>
          </Card>
        </div>

        {/* Referral Link */}
        <Card>
          <CardHeader>
            <CardTitle>{t('affiliate.referralLink')}</CardTitle>
            <CardDescription>{t('affiliate.shareDesc', 'Share this link to earn commission')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={stats?.referral_link || ''}
                readOnly
                className="font-mono text-sm"
              />
              <Button onClick={copyReferralLink} variant="outline">
                <Copy className="h-4 w-4 mr-2" />
                {t('affiliate.copyLink')}
              </Button>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(`https://twitter.com/intent/tweet?url=${encodeURIComponent(stats?.referral_link || '')}`, '_blank')}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('affiliate.shareOn')} Twitter
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(stats?.referral_link || '')}`, '_blank')}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('affiliate.shareOn')} Facebook
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Referrals Table */}
        <Card>
          <CardHeader>
            <CardTitle>{t('affiliate.referrals')}</CardTitle>
            <CardDescription>{t('affiliate.referralsDesc', 'Track your referred users and earnings')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">{t('affiliate.referralName')}</th>
                    <th className="text-left py-2">{t('affiliate.signupDate')}</th>
                    <th className="text-left py-2">{t('affiliate.status')}</th>
                    <th className="text-left py-2">{t('affiliate.commission')}</th>
                  </tr>
                </thead>
                <tbody>
                  {stats?.referrals && stats.referrals.length > 0 ? (
                    stats.referrals.map((ref, idx) => (
                      <tr key={idx} className="border-b">
                        <td className="py-2">{ref.name}</td>
                        <td className="py-2">{new Date(ref.signup_date).toLocaleDateString()}</td>
                        <td className="py-2">
                          <span className={`px-2 py-1 rounded text-xs ${
                            ref.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                          }`}>
                            {ref.status}
                          </span>
                        </td>
                        <td className="py-2">${(ref.commission || 0).toFixed(2)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="4" className="text-center py-8 text-muted-foreground">
                        {t('affiliate.noReferrals', 'No referrals yet. Start sharing your link!')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Withdrawal */}
        <Card>
          <CardHeader>
            <CardTitle>{t('affiliate.requestPayout')}</CardTitle>
            <CardDescription>{t('affiliate.payoutDesc', 'Request withdrawal of your pending commission')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                type="number"
                placeholder={t('affiliate.enterAmount', 'Enter amount')}
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
                max={stats?.pending_earnings || 0}
              />
              <Button onClick={handleWithdraw} className="gradient-button text-white">
                {t('affiliate.requestPayout')}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('affiliate.availableBalance', 'Available balance')}: ${(stats?.pending_earnings || 0).toFixed(2)}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AffiliateDashboard;
