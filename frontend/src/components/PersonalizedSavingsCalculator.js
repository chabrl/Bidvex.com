import React, { useState, useEffect } from 'react';
import { Calculator, TrendingUp, History, Sparkles, ArrowRight, ToggleLeft, ToggleRight, Lightbulb } from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { Slider } from './ui/slider';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * PersonalizedSavingsCalculator - Shows ROI based on user's actual transaction history
 * Features:
 * - Fetches user's 12-month transaction volume
 * - Calculates personalized savings for Premium/VIP
 * - Fallback to manual slider for non-logged users
 * - "What If" toggle to project future savings with hypothetical volume
 */
const PersonalizedSavingsCalculator = ({ currentTier = 'free' }) => {
  const { user } = useAuth();
  const [annualVolume, setAnnualVolume] = useState([50000]);
  const [whatIfVolume, setWhatIfVolume] = useState([100000]); // Hypothetical volume for "What If" mode
  const [userStats, setUserStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [usePersonalized, setUsePersonalized] = useState(false);
  const [whatIfMode, setWhatIfMode] = useState(false); // Toggle between real stats and "What If"

  // Fetch user's transaction history
  useEffect(() => {
    const fetchUserStats = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        // Try to get user's bid/purchase history from the last 12 months
        const response = await axios.get(`${API}/users/me/stats`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
        });
        
        if (response.data && response.data.annual_volume) {
          setUserStats(response.data);
          setAnnualVolume([response.data.annual_volume]);
          setUsePersonalized(true);
        }
      } catch (error) {
        console.log('User stats not available, using manual slider');
      } finally {
        setLoading(false);
      }
    };

    fetchUserStats();
  }, [user]);

  // Determine active volume based on mode
  const volume = whatIfMode ? whatIfVolume[0] : annualVolume[0];

  // Fee rates by tier (NO CAP)
  const feeRates = {
    free: { buyer: 0.05, seller: 0.04, combined: 0.09 },
    premium: { buyer: 0.035, seller: 0.025, combined: 0.06 },
    vip: { buyer: 0.03, seller: 0.02, combined: 0.05 }
  };

  // Calculate fees for each tier
  const freeFees = volume * feeRates.free.combined;
  const premiumFees = volume * feeRates.premium.combined;
  const vipFees = volume * feeRates.vip.combined;

  const premiumSavings = freeFees - premiumFees;
  const vipSavings = freeFees - vipFees;

  // ROI calculation
  const premiumROI = (premiumSavings / 99.99).toFixed(1);
  const vipROI = (vipSavings / 299.99).toFixed(1);

  // Format currency
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="personalized-savings-calculator">
      {/* Personalized Message for Logged-in Users */}
      {user && usePersonalized && userStats && (
        <Card className="bg-gradient-to-r from-blue-600 to-purple-600 border-0 text-white overflow-hidden">
          <CardContent className="p-6 relative">
            <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-3">
                <History className="h-5 w-5" />
                <span className="text-sm font-medium text-blue-100">Based on Your Activity</span>
              </div>
              <p className="text-2xl font-bold mb-2">
                Your Last 12 Months: {formatCurrency(userStats.annual_volume)}
              </p>
              <p className="text-blue-100">
                {userStats.total_bids || 0} bids placed • {userStats.auctions_won || 0} auctions won
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Savings Calculator Card */}
      <Card className="bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-800 dark:via-slate-900 dark:to-slate-800 border-2 border-slate-200 dark:border-slate-700 overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl shadow-lg">
              <Calculator className="h-6 w-6 text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                {usePersonalized ? 'Your Personalized Savings' : 'Fee Savings Calculator'}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {usePersonalized 
                  ? 'Based on your actual transaction history' 
                  : 'See how much you could save'}
              </p>
            </div>
          </div>

          {/* "What If" Toggle for Personalized Users */}
          {user && usePersonalized && userStats && (
            <div className="mb-6 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-200 dark:border-indigo-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-5 w-5 text-indigo-600" />
                  <span className="font-medium text-indigo-900 dark:text-indigo-100">
                    {whatIfMode ? 'What If Mode' : 'My Real Stats'}
                  </span>
                </div>
                <button
                  onClick={() => setWhatIfMode(!whatIfMode)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white dark:bg-slate-800 border-2 border-indigo-300 dark:border-indigo-600 hover:border-indigo-500 transition-colors"
                  data-testid="what-if-toggle"
                >
                  {whatIfMode ? (
                    <>
                      <ToggleRight className="h-5 w-5 text-indigo-600" />
                      <span className="text-sm font-medium text-indigo-700 dark:text-indigo-300">Switch to Real</span>
                    </>
                  ) : (
                    <>
                      <ToggleLeft className="h-5 w-5 text-slate-400" />
                      <span className="text-sm font-medium text-slate-600 dark:text-slate-400">Try "What If"</span>
                    </>
                  )}
                </button>
              </div>
              {whatIfMode && (
                <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-2">
                  Project your savings for next year with hypothetical transaction volume
                </p>
              )}
            </div>
          )}

          {/* Volume Slider - Show for non-personalized OR "What If" mode */}
          {(!usePersonalized || whatIfMode) && (
            <div className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {whatIfMode ? 'Projected Annual Volume (Next Year)' : 'Estimated Annual Volume'}
                </label>
                <span className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  {formatCurrency(volume)}
                </span>
              </div>
              <Slider
                value={whatIfMode ? whatIfVolume : annualVolume}
                onValueChange={whatIfMode ? setWhatIfVolume : setAnnualVolume}
                max={500000}
                min={1000}
                step={1000}
                className="w-full"
                data-testid={whatIfMode ? "what-if-volume-slider" : "savings-volume-slider"}
              />
              <div className="flex justify-between text-xs text-slate-400 mt-2">
                <span>$1K</span>
                <span>$100K</span>
                <span>$250K</span>
                <span>$500K</span>
              </div>
              {whatIfMode && userStats && (
                <p className="text-xs text-center text-indigo-500 mt-2">
                  Your current volume: {formatCurrency(userStats.annual_volume)} → Projected: {formatCurrency(whatIfVolume[0])}
                </p>
              )}
            </div>
          )}

          {/* Savings Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Premium Savings */}
            <div className={`p-5 rounded-xl border-2 transition-all duration-300 ${
              currentTier === 'premium' 
                ? 'bg-purple-100 dark:bg-purple-900/30 border-purple-400' 
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-purple-300 hover:shadow-lg'
            }`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-purple-600 dark:text-purple-400">
                  With Premium
                </span>
                <span className="text-xs bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-200 px-2 py-1 rounded-full">
                  $99.99/yr
                </span>
              </div>
              <p className="text-3xl font-bold text-purple-700 dark:text-purple-300 mb-1">
                {formatCurrency(premiumSavings)}
              </p>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                saved in fees per year
              </p>
              <div className="flex items-center gap-2 p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <TrendingUp className="h-4 w-4 text-green-600" />
                <span className="text-sm font-bold text-green-700 dark:text-green-400">
                  {premiumROI}x ROI
                </span>
                <span className="text-xs text-green-600 dark:text-green-500">
                  on subscription
                </span>
              </div>
            </div>

            {/* VIP Savings */}
            <div className={`p-5 rounded-xl border-2 transition-all duration-300 ${
              currentTier === 'vip' 
                ? 'bg-amber-100 dark:bg-amber-900/30 border-amber-400' 
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-amber-300 hover:shadow-lg'
            }`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-amber-600 dark:text-amber-400">
                  With VIP Elite
                </span>
                <span className="text-xs bg-amber-100 dark:bg-amber-800 text-amber-700 dark:text-amber-200 px-2 py-1 rounded-full">
                  $299.99/yr
                </span>
              </div>
              <p className="text-3xl font-bold text-amber-700 dark:text-amber-300 mb-1">
                {formatCurrency(vipSavings)}
              </p>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                saved in fees per year
              </p>
              <div className="flex items-center gap-2 p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <TrendingUp className="h-4 w-4 text-green-600" />
                <span className="text-sm font-bold text-green-700 dark:text-green-400">
                  {vipROI}x ROI
                </span>
                <span className="text-xs text-green-600 dark:text-green-500">
                  on subscription
                </span>
              </div>
            </div>
          </div>

          {/* Personalized Insight */}
          {volume >= 10000 && currentTier === 'free' && (
            <div className="mt-6 p-4 bg-gradient-to-r from-emerald-50 to-green-50 dark:from-emerald-900/20 dark:to-green-900/20 rounded-xl border border-green-200 dark:border-green-800">
              <div className="flex items-start gap-3">
                <Sparkles className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-green-800 dark:text-green-200">
                    {usePersonalized 
                      ? `Based on your last 12 months of activity (${formatCurrency(volume)} volume), you would have saved ${formatCurrency(vipSavings)} with a VIP membership.`
                      : `With ${formatCurrency(volume)} in annual transactions, you would save ${formatCurrency(vipSavings)} with VIP.`
                    }
                  </p>
                  <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                    Your subscription pays for itself <strong>{vipROI}x over!</strong>
                  </p>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PersonalizedSavingsCalculator;
