import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Crown, 
  Star, 
  Zap,
  Check,
  Loader2,
  AlertTriangle,
  Sparkles,
  TrendingDown,
  ShieldCheck
} from 'lucide-react';

const API = `${API_BASE}/api`;

const SubscriptionPlans = () => {
  const { t, i18n } = useTranslation();
  const isFrench = i18n.language === 'fr';
  
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(null);
  const [error, setError] = useState(null);
  const [tiers, setTiers] = useState([]);
  const [currentStatus, setCurrentStatus] = useState(null);
  
  useEffect(() => {
    fetchData();
  }, []);
  
  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Get available tiers
      const tiersRes = await axios.get(`${API}/payments/subscriptions/tiers`);
      setTiers(tiersRes.data.tiers || []);
      
      // Get current subscription status
      const token = localStorage.getItem('token');
      if (token) {
        const statusRes = await axios.get(`${API}/payments/subscriptions/my-status`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setCurrentStatus(statusRes.data);
      }
      
    } catch (err) {
      console.error('Failed to load subscription data:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleUpgrade = async (tierId) => {
    try {
      setUpgrading(tierId);
      setError(null);
      
      const token = localStorage.getItem('token');
      if (!token) {
        window.location.href = '/auth?redirect=' + encodeURIComponent(window.location.pathname);
        return;
      }
      
      const returnUrl = `${window.location.origin}/profile/subscription`;
      
      const response = await axios.post(`${API}/payments/subscriptions/upgrade`, {
        tier: tierId,
        return_url: returnUrl
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Redirect to Stripe Checkout
      window.location.href = response.data.checkout_url;
      
    } catch (err) {
      console.error('Failed to start upgrade:', err);
      setError(err.response?.data?.detail || 'Failed to start upgrade process');
      setUpgrading(null);
    }
  };
  
  const currentTier = currentStatus?.tier || 'free';
  
  const getTierIcon = (tierId) => {
    switch (tierId) {
      case 'vip': return <Crown className="h-6 w-6" />;
      case 'premium': return <Star className="h-6 w-6" />;
      default: return <Zap className="h-6 w-6" />;
    }
  };
  
  const getTierColor = (tierId) => {
    switch (tierId) {
      case 'vip': return 'from-purple-500 to-pink-500';
      case 'premium': return 'from-blue-500 to-cyan-500';
      default: return 'from-slate-400 to-slate-500';
    }
  };
  
  const getTierBorderColor = (tierId) => {
    switch (tierId) {
      case 'vip': return 'border-purple-300 dark:border-purple-700';
      case 'premium': return 'border-blue-300 dark:border-blue-700';
      default: return 'border-slate-200 dark:border-slate-700';
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }
  
  return (
    <div className="space-y-8" data-testid="subscription-plans">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-3xl font-bold mb-2">
          {isFrench ? 'Choisissez votre forfait' : 'Choose Your Plan'}
        </h2>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          {isFrench 
            ? 'Économisez sur les frais avec nos forfaits Premium et VIP. Plus vous vendez, plus vous économisez!'
            : 'Save on fees with our Premium and VIP plans. The more you sell, the more you save!'}
        </p>
      </div>
      
      {/* Current Plan Badge */}
      {currentStatus && (
        <div className="flex justify-center">
          <Badge variant="outline" className="text-sm py-2 px-4">
            <ShieldCheck className="h-4 w-4 mr-2" />
            {isFrench ? 'Forfait actuel:' : 'Current Plan:'}{' '}
            <span className="font-bold ml-1 capitalize">{currentStatus.tier_name}</span>
          </Badge>
        </div>
      )}
      
      {/* Error Alert */}
      {error && (
        <Alert variant="destructive" className="max-w-md mx-auto">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      {/* Plans Grid */}
      <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {tiers.map((tier) => {
          const isCurrentPlan = currentTier === tier.id || (currentTier === 'basic' && tier.id === 'free');
          const canUpgrade = !isCurrentPlan && tier.id !== 'free';
          const isPopular = tier.id === 'premium';
          
          return (
            <Card 
              key={tier.id}
              className={`relative overflow-hidden transition-all hover:shadow-lg ${
                isCurrentPlan ? 'ring-2 ring-primary' : ''
              } ${getTierBorderColor(tier.id)}`}
            >
              {/* Popular Badge */}
              {isPopular && (
                <div className="absolute top-0 right-0">
                  <Badge className="rounded-bl-lg rounded-tr-lg rounded-br-none rounded-tl-none bg-gradient-to-r from-blue-500 to-cyan-500">
                    <Sparkles className="h-3 w-3 mr-1" />
                    {isFrench ? 'Populaire' : 'Popular'}
                  </Badge>
                </div>
              )}
              
              {/* Header */}
              <CardHeader className="text-center pb-2">
                <div className={`w-14 h-14 rounded-full bg-gradient-to-r ${getTierColor(tier.id)} flex items-center justify-center mx-auto mb-3 text-white`}>
                  {getTierIcon(tier.id)}
                </div>
                <CardTitle className="text-xl">{tier.name}</CardTitle>
                <CardDescription>
                  {tier.id === 'free' && (isFrench ? 'Pour commencer' : 'Get started')}
                  {tier.id === 'premium' && (isFrench ? 'Pour les vendeurs actifs' : 'For active sellers')}
                  {tier.id === 'vip' && (isFrench ? 'Pour les professionnels' : 'For professionals')}
                </CardDescription>
              </CardHeader>
              
              <CardContent className="text-center">
                {/* Price */}
                <div className="mb-6">
                  {tier.price === 0 ? (
                    <p className="text-4xl font-bold">{isFrench ? 'Gratuit' : 'Free'}</p>
                  ) : (
                    <>
                      <p className="text-4xl font-bold">${tier.price / 100}</p>
                      <p className="text-sm text-slate-500">/{isFrench ? 'mois' : 'month'}</p>
                    </>
                  )}
                </div>
                
                {/* Fee Rates */}
                <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4 mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      {isFrench ? 'Prime acheteur' : "Buyer's Premium"}
                    </span>
                    <span className="font-bold text-lg">{tier.buyer_premium}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      {isFrench ? 'Commission vendeur' : 'Seller Commission'}
                    </span>
                    <span className="font-bold text-lg">{tier.seller_commission}</span>
                  </div>
                  
                  {tier.savings_example && (
                    <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                      <div className="flex items-center justify-center gap-1 text-green-600 dark:text-green-400">
                        <TrendingDown className="h-4 w-4" />
                        <span className="text-sm font-medium">{tier.savings_example}</span>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Features */}
                <ul className="space-y-2 text-left">
                  {tier.features?.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      <Check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
              
              <CardFooter>
                {isCurrentPlan ? (
                  <Button className="w-full" disabled variant="outline">
                    <Check className="mr-2 h-4 w-4" />
                    {isFrench ? 'Forfait actuel' : 'Current Plan'}
                  </Button>
                ) : canUpgrade ? (
                  <Button 
                    className={`w-full ${tier.id === 'vip' ? 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600' : ''}`}
                    onClick={() => handleUpgrade(tier.id)}
                    disabled={upgrading === tier.id}
                    data-testid={`upgrade-to-${tier.id}-btn`}
                  >
                    {upgrading === tier.id ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {isFrench ? 'Redirection...' : 'Redirecting...'}
                      </>
                    ) : (
                      <>
                        {isFrench ? 'Passer à ' : 'Upgrade to '}{tier.name}
                      </>
                    )}
                  </Button>
                ) : (
                  <Button className="w-full" variant="outline" disabled>
                    {isFrench ? 'Gratuit' : 'Free Forever'}
                  </Button>
                )}
              </CardFooter>
            </Card>
          );
        })}
      </div>
      
      {/* Fee Comparison Table */}
      <Card className="max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle className="text-lg">
            {isFrench ? 'Comparaison des frais' : 'Fee Comparison'}
          </CardTitle>
          <CardDescription>
            {isFrench 
              ? 'Voyez combien vous pouvez économiser avec chaque forfait'
              : 'See how much you can save with each plan'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-medium">{isFrench ? 'Forfait' : 'Plan'}</th>
                  <th className="text-center py-3 px-4 font-medium">{isFrench ? 'Prime acheteur' : "Buyer's Premium"}</th>
                  <th className="text-center py-3 px-4 font-medium">{isFrench ? 'Commission vendeur' : 'Seller Commission'}</th>
                  <th className="text-center py-3 px-4 font-medium">{isFrench ? 'Économies / 1 000 $' : 'Savings / $1,000'}</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-3 px-4">Free / Basic</td>
                  <td className="text-center py-3 px-4">5.0%</td>
                  <td className="text-center py-3 px-4">4.0%</td>
                  <td className="text-center py-3 px-4 text-slate-400">-</td>
                </tr>
                <tr className="border-b bg-blue-50 dark:bg-blue-950/30">
                  <td className="py-3 px-4 font-medium text-blue-700 dark:text-blue-400">Premium</td>
                  <td className="text-center py-3 px-4">3.5%</td>
                  <td className="text-center py-3 px-4">2.5%</td>
                  <td className="text-center py-3 px-4 text-green-600 font-medium">$30</td>
                </tr>
                <tr className="bg-purple-50 dark:bg-purple-950/30">
                  <td className="py-3 px-4 font-medium text-purple-700 dark:text-purple-400">VIP Elite</td>
                  <td className="text-center py-3 px-4">3.0%</td>
                  <td className="text-center py-3 px-4">2.0%</td>
                  <td className="text-center py-3 px-4 text-green-600 font-medium">$40</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      
      {/* Trust Badges */}
      <div className="flex flex-wrap justify-center gap-6 text-slate-500 text-sm">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          <span>{isFrench ? 'Paiement sécurisé' : 'Secure Payment'}</span>
        </div>
        <div className="flex items-center gap-2">
          <Check className="h-5 w-5" />
          <span>{isFrench ? 'Annulez à tout moment' : 'Cancel Anytime'}</span>
        </div>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          <span>{isFrench ? 'Mise à niveau instantanée' : 'Instant Upgrade'}</span>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionPlans;
