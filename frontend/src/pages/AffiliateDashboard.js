import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import { DollarSign, Users, TrendingUp, Copy, ExternalLink, Download } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AffiliateDashboard = () => {
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
      toast.error('Failed to load affiliate data');
    } finally {
      setLoading(false);
    }
  };

  const copyReferralLink = () => {
    if (stats?.referral_link) {
      navigator.clipboard.writeText(stats.referral_link);
      toast.success('Referral link copied to clipboard!');
    }
  };

  const handleWithdraw = async () => {
    if (!withdrawAmount || parseFloat(withdrawAmount) <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }

    if (parseFloat(withdrawAmount) > stats?.pending_earnings) {
      toast.error('Insufficient balance');
      return;
    }

    try {
      await axios.post(`${API}/affiliate/withdraw`, {
        amount: parseFloat(withdrawAmount),
        method: 'bank_transfer'
      });
      toast.success('Withdrawal request submitted!');
      setWithdrawAmount('');
      fetchAffiliateStats();
    } catch (error) {
      toast.error('Failed to submit withdrawal request');
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
          <h1 className="text-3xl font-bold mb-2">Affiliate Program</h1>
          <p className="text-muted-foreground">Earn 3% commission on every sale from your referrals</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title="Total Earnings"
            value={`$${stats?.total_earnings?.toFixed(2) || '0.00'}`}
            color="green"
          />
          <StatCard
            icon={<TrendingUp className="h-6 w-6" />}
            title="Pending"
            value={`$${stats?.pending_earnings?.toFixed(2) || '0.00'}`}
            color="orange"
          />
          <StatCard
            icon={<Download className="h-6 w-6" />}
            title="Paid Out"
            value={`$${stats?.paid_earnings?.toFixed(2) || '0.00'}`}
            color="blue"
          />
          <StatCard
            icon={<Users className="h-6 w-6" />}
            title="Total Referrals"
            value={stats?.total_referrals || 0}
            color="purple"
          />
        </div>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Your Referral Link</CardTitle>
            <CardDescription>Share this link to earn commissions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={stats?.referral_link || ''}
                readOnly
                className="flex-1"
                data-testid="referral-link-input"
              />
              <Button variant="outline" onClick={copyReferralLink} data-testid="copy-link-btn">
                <Copy className="h-4 w-4" />
              </Button>
              <Button variant="outline" onClick={() => window.open(stats?.referral_link, '_blank')}>
                <ExternalLink className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              Your affiliate code: <span className="font-mono font-bold">{stats?.affiliate_code}</span>
            </p>
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Withdraw Earnings</CardTitle>
            <CardDescription>
              Available balance: ${stats?.pending_earnings?.toFixed(2) || '0.00'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                type="number"
                step="0.01"
                min="0"
                max={stats?.pending_earnings || 0}
                placeholder="Enter amount"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
                data-testid="withdraw-amount-input"
              />
              <Button
                onClick={handleWithdraw}
                disabled={!withdrawAmount || parseFloat(withdrawAmount) <= 0}
                className="gradient-button text-white border-0"
                data-testid="withdraw-btn"
              >
                Request Withdrawal
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Withdrawals are processed within 3-5 business days
            </p>
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Earnings History</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.earnings_history && stats.earnings_history.length > 0 ? (
              <div className="space-y-2">
                {stats.earnings_history.map((earning) => (
                  <div key={earning.id} className="flex justify-between items-center p-3 border rounded-lg">
                    <div>
                      <p className="font-medium">${earning.commission_amount?.toFixed(2)}</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(earning.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                        earning.status === 'paid'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                          : 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300'
                      }`}>
                      {earning.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No earnings yet. Start sharing your referral link!
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Your Referrals</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.referrals && stats.referrals.length > 0 ? (
              <div className="space-y-2">
                {stats.referrals.map((referral) => (
                  <div key={referral.id} className="flex justify-between items-center p-3 border rounded-lg">
                    <div>
                      <p className="font-medium">Referral #{referral.id.slice(0, 8)}</p>
                      <p className="text-sm text-muted-foreground">
                        Joined: {new Date(referral.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                        referral.status === 'active'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                          : 'bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300'
                      }`}>
                      {referral.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No referrals yet. Start inviting friends!
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>How It Works</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <Step number="1" title="Share Your Link" description="Share your unique referral link with friends and followers" />
              <Step number="2" title="They Sign Up" description="When someone signs up using your link, they become your referral" />
              <Step number="3" title="Earn Commission" description="You earn 3% commission on every sale they make on Bazario" />
              <Step number="4" title="Get Paid" description="Withdraw your earnings via bank transfer or use as bidding credits" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatCard = ({ icon, title, value, color }) => (
  <Card className="glassmorphism">
    <CardContent className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold mb-1">{value}</p>
      <p className="text-sm text-muted-foreground">{title}</p>
    </CardContent>
  </Card>
);

const Step = ({ number, title, description }) => (
  <div className="flex gap-4">
    <div className="gradient-bg w-8 h-8 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0">
      {number}
    </div>
    <div>
      <p className="font-semibold">{title}</p>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  </div>
);

export default AffiliateDashboard;
