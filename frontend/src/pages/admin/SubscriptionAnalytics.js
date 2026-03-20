/**
 * SubscriptionAnalytics - Admin dashboard for subscription metrics
 * Features: Revenue tracking, subscriber counts, coupon analytics, growth charts
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import {
  DollarSign, Users, TrendingUp, TrendingDown, Crown, Star, 
  UserIcon, Ticket, RefreshCw, ArrowUpRight, ArrowDownRight,
  CreditCard, Gift, BarChart3, PieChart, Calendar, Percent,
  Sparkles, Zap, ChevronRight
} from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SubscriptionAnalytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/admin/subscription-analytics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data.success) {
        setAnalytics(response.data);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No analytics data available</p>
        <Button onClick={fetchAnalytics} className="mt-4">
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  const { overview, subscribers, coupons, chart_data, recent_changes } = analytics;

  return (
    <div className="space-y-6" data-testid="subscription-analytics">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-primary" />
            Subscription Analytics
          </h2>
          <p className="text-muted-foreground">Revenue, subscribers, and coupon performance</p>
        </div>
        <Button variant="outline" onClick={fetchAnalytics} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Revenue Overview */}
      <div className="grid md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-green-200 dark:border-green-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600 dark:text-green-400">Total Revenue</p>
                <h3 className="text-3xl font-bold text-green-700 dark:text-green-300">
                  {formatCurrency(overview.total_revenue)}
                </h3>
              </div>
              <div className="p-3 bg-green-100 dark:bg-green-800 rounded-xl">
                <DollarSign className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border-blue-200 dark:border-blue-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-600 dark:text-blue-400">This Month</p>
                <h3 className="text-3xl font-bold text-blue-700 dark:text-blue-300">
                  {formatCurrency(overview.this_month_revenue)}
                </h3>
                <div className="flex items-center gap-1 mt-1">
                  {overview.growth_percentage >= 0 ? (
                    <ArrowUpRight className="h-4 w-4 text-green-500" />
                  ) : (
                    <ArrowDownRight className="h-4 w-4 text-red-500" />
                  )}
                  <span className={`text-sm font-medium ${overview.growth_percentage >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {overview.growth_percentage >= 0 ? '+' : ''}{overview.growth_percentage}%
                  </span>
                  <span className="text-xs text-muted-foreground">vs last month</span>
                </div>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-800 rounded-xl">
                <TrendingUp className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-violet-50 dark:from-purple-900/20 dark:to-violet-900/20 border-purple-200 dark:border-purple-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-600 dark:text-purple-400">Est. MRR</p>
                <h3 className="text-3xl font-bold text-purple-700 dark:text-purple-300">
                  {formatCurrency(overview.mrr_estimate)}
                </h3>
                <p className="text-xs text-muted-foreground mt-1">Monthly recurring</p>
              </div>
              <div className="p-3 bg-purple-100 dark:bg-purple-800 rounded-xl">
                <Sparkles className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border-amber-200 dark:border-amber-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-amber-600 dark:text-amber-400">Active Subscribers</p>
                <h3 className="text-3xl font-bold text-amber-700 dark:text-amber-300">
                  {subscribers.active_subscribers}
                </h3>
                <p className="text-xs text-muted-foreground mt-1">of {subscribers.total_users} users</p>
              </div>
              <div className="p-3 bg-amber-100 dark:bg-amber-800 rounded-xl">
                <Users className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Plan Distribution & Revenue Chart */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Plan Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PieChart className="h-5 w-5 text-primary" />
              Plan Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Free */}
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                  <UserIcon className="h-6 w-6 text-slate-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">Free</span>
                    <span className="font-bold">{subscribers.free_users}</span>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-slate-400 rounded-full transition-all duration-500"
                      style={{ width: `${(subscribers.free_users / subscribers.total_users) * 100}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Premium */}
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-100 to-indigo-100 dark:from-purple-900/30 dark:to-indigo-900/30 flex items-center justify-center">
                  <Star className="h-6 w-6 text-purple-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">Premium</span>
                    <span className="font-bold text-purple-600">{subscribers.premium_users}</span>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 rounded-full transition-all duration-500"
                      style={{ width: `${(subscribers.premium_users / subscribers.total_users) * 100}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* VIP */}
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/30 flex items-center justify-center">
                  <Crown className="h-6 w-6 text-amber-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">VIP</span>
                    <span className="font-bold text-amber-600">{subscribers.vip_users}</span>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full transition-all duration-500"
                      style={{ width: `${(subscribers.vip_users / subscribers.total_users) * 100}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Subscription Source */}
              <div className="pt-4 border-t mt-4">
                <p className="text-sm font-medium text-muted-foreground mb-3">Subscription Source</p>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2">
                    <CreditCard className="h-4 w-4 text-blue-500" />
                    <span className="text-sm">Stripe: <strong>{subscribers.stripe_subscriptions}</strong></span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-500" />
                    <span className="text-sm">Manual: <strong>{subscribers.manual_subscriptions}</strong></span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Revenue Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              Revenue Trend (6 Months)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {chart_data.map((item, idx) => {
                const maxRevenue = Math.max(...chart_data.map(d => d.revenue), 1);
                const percentage = (item.revenue / maxRevenue) * 100;
                
                return (
                  <div key={idx} className="flex items-center gap-4">
                    <span className="text-sm text-muted-foreground w-16">{item.month}</span>
                    <div className="flex-1">
                      <div className="h-6 bg-slate-100 dark:bg-slate-800 rounded-lg overflow-hidden relative">
                        <div 
                          className="h-full bg-gradient-to-r from-primary to-primary/70 rounded-lg transition-all duration-500 flex items-center"
                          style={{ width: `${Math.max(percentage, 2)}%` }}
                        >
                          {percentage > 30 && (
                            <span className="text-xs text-white font-medium pl-2">
                              {formatCurrency(item.revenue)}
                            </span>
                          )}
                        </div>
                        {percentage <= 30 && item.revenue > 0 && (
                          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium">
                            {formatCurrency(item.revenue)}
                          </span>
                        )}
                      </div>
                    </div>
                    <Badge variant="secondary" className="w-8 justify-center">
                      {item.subscriptions}
                    </Badge>
                  </div>
                );
              })}
            </div>
            
            {/* Revenue Split */}
            <div className="pt-4 border-t mt-4">
              <p className="text-sm font-medium text-muted-foreground mb-3">Billing Period Split</p>
              <div className="flex gap-4">
                <div className="flex-1 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <p className="text-xs text-blue-600 dark:text-blue-400">Monthly</p>
                  <p className="font-bold text-blue-700 dark:text-blue-300">{formatCurrency(overview.monthly_revenue_split)}</p>
                </div>
                <div className="flex-1 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <p className="text-xs text-green-600 dark:text-green-400">Yearly</p>
                  <p className="font-bold text-green-700 dark:text-green-300">{formatCurrency(overview.yearly_revenue_split)}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Coupon Analytics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ticket className="h-5 w-5 text-primary" />
            Coupon Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-4 mb-6">
            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl">
              <p className="text-sm text-muted-foreground">Total Coupons</p>
              <p className="text-2xl font-bold">{coupons.total_coupons}</p>
            </div>
            <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-xl">
              <p className="text-sm text-green-600 dark:text-green-400">Active</p>
              <p className="text-2xl font-bold text-green-700 dark:text-green-300">{coupons.active_coupons}</p>
            </div>
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
              <p className="text-sm text-blue-600 dark:text-blue-400">Total Uses</p>
              <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{coupons.total_uses}</p>
            </div>
            <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-xl">
              <p className="text-sm text-amber-600 dark:text-amber-400">Discounts Given</p>
              <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">{formatCurrency(coupons.total_discount_given)}</p>
            </div>
          </div>

          {/* Top Coupons */}
          {coupons.top_coupons && coupons.top_coupons.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-3">Top Performing Coupons</h4>
              <div className="space-y-2">
                {coupons.top_coupons.map((coupon, idx) => (
                  <div 
                    key={idx} 
                    className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        idx === 0 ? 'bg-amber-100 text-amber-600' :
                        idx === 1 ? 'bg-slate-200 text-slate-600' :
                        idx === 2 ? 'bg-orange-100 text-orange-600' :
                        'bg-slate-100 text-slate-500'
                      }`}>
                        {idx + 1}
                      </div>
                      <div>
                        <p className="font-mono font-bold">{coupon.code}</p>
                        <p className="text-xs text-muted-foreground">
                          {coupon.discount_type === 'percentage' 
                            ? `${coupon.value}% off` 
                            : `${formatCurrency(coupon.value)} off`}
                        </p>
                      </div>
                    </div>
                    <Badge variant="secondary" className="gap-1">
                      <Gift className="h-3 w-3" />
                      {coupon.uses} uses
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Pricing Changes */}
      {recent_changes && recent_changes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-primary" />
              Recent Pricing Changes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recent_changes.slice(0, 5).map((change, idx) => (
                <div 
                  key={idx}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="font-medium">
                        {change.plan_id.charAt(0).toUpperCase() + change.plan_id.slice(1)} - {change.field_changed}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {change.old_value} → {change.new_value}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">
                      {change.changed_at ? new Date(change.changed_at).toLocaleDateString() : 'N/A'}
                    </p>
                    <p className="text-xs text-muted-foreground">{change.changed_by}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default SubscriptionAnalytics;
