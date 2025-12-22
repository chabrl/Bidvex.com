import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  TrendingUp, Eye, MousePointer, Gavel, BarChart3, 
  RefreshCw, Calendar, Package, DollarSign, Target,
  ArrowUpRight, ArrowDownRight, Loader2
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Simple line chart component using CSS
const SimpleLineChart = ({ data, color, label }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-slate-400 text-sm">
        No data available
      </div>
    );
  }

  const maxValue = Math.max(...data.map(d => d.count), 1);
  const points = data.map((d, i) => ({
    x: (i / (data.length - 1 || 1)) * 100,
    y: 100 - (d.count / maxValue) * 100
  }));

  const pathD = points.map((p, i) => 
    `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
  ).join(' ');

  return (
    <div className="relative h-32">
      <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {/* Grid lines */}
        <line x1="0" y1="25" x2="100" y2="25" stroke="currentColor" strokeOpacity="0.1" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="currentColor" strokeOpacity="0.1" />
        <line x1="0" y1="75" x2="100" y2="75" stroke="currentColor" strokeOpacity="0.1" />
        
        {/* Area fill */}
        <path 
          d={`${pathD} L 100 100 L 0 100 Z`}
          fill={color}
          fillOpacity="0.1"
        />
        
        {/* Line */}
        <path 
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        
        {/* Points */}
        {points.map((p, i) => (
          <circle 
            key={i}
            cx={p.x}
            cy={p.y}
            r="3"
            fill={color}
            className="opacity-0 hover:opacity-100 transition-opacity"
          />
        ))}
      </svg>
      
      {/* Labels */}
      <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-slate-400 mt-1">
        <span>{data[0]?.date?.slice(5) || ''}</span>
        <span>{data[data.length - 1]?.date?.slice(5) || ''}</span>
      </div>
    </div>
  );
};

// Stat Card Component
const StatCard = ({ icon: Icon, label, value, change, changeType, color }) => (
  <Card className="bg-white dark:bg-slate-800/50 border-slate-200 dark:border-slate-700">
    <CardContent className="p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <p className="text-3xl font-bold mt-2" style={{ color }}>{value}</p>
          {change !== undefined && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${
              changeType === 'up' ? 'text-green-500' : changeType === 'down' ? 'text-red-500' : 'text-slate-400'
            }`}>
              {changeType === 'up' ? <ArrowUpRight className="h-4 w-4" /> : 
               changeType === 'down' ? <ArrowDownRight className="h-4 w-4" /> : null}
              <span>{change}</span>
            </div>
          )}
        </div>
        <div className="p-3 rounded-xl" style={{ backgroundColor: `${color}20` }}>
          <Icon className="h-6 w-6" style={{ color }} />
        </div>
      </div>
    </CardContent>
  </Card>
);

const SellerAnalyticsDashboard = () => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('7d');
  const [refreshing, setRefreshing] = useState(false);

  const fetchAnalytics = async () => {
    if (!user?.id || !token) return;
    
    try {
      setRefreshing(true);
      const response = await axios.get(`${API}/analytics/seller/${user.id}?period=${period}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAnalytics(response.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [user?.id, token, period]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-[#06B6D4]" />
      </div>
    );
  }

  const summary = analytics?.summary || {};
  const charts = analytics?.charts || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <BarChart3 className="h-7 w-7 text-[#06B6D4]" />
            Seller Analytics
          </h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Track your listing performance and engagement
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Period Selector */}
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
            {['7d', '30d', '90d'].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  period === p
                    ? 'bg-[#1E3A8A] text-white'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                }`}
              >
                {p === '7d' ? '7 Days' : p === '30d' ? '30 Days' : '90 Days'}
              </button>
            ))}
          </div>
          
          <Button
            variant="outline"
            size="icon"
            onClick={fetchAnalytics}
            disabled={refreshing}
            className="border-slate-200 dark:border-slate-700"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Eye}
          label="Total Impressions"
          value={summary.total_impressions?.toLocaleString() || 0}
          color="#06B6D4"
        />
        <StatCard
          icon={MousePointer}
          label="Total Clicks"
          value={summary.total_clicks?.toLocaleString() || 0}
          color="#1E3A8A"
        />
        <StatCard
          icon={Gavel}
          label="Total Bids"
          value={summary.total_bids?.toLocaleString() || 0}
          color="#10B981"
        />
        <StatCard
          icon={Target}
          label="Click-Through Rate"
          value={`${summary.click_through_rate || 0}%`}
          color="#F59E0B"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Impressions Chart */}
        <Card className="bg-white dark:bg-slate-800/50 border-slate-200 dark:border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Eye className="h-5 w-5 text-[#06B6D4]" />
              Impressions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SimpleLineChart 
              data={charts.impressions || []} 
              color="#06B6D4"
              label="Impressions"
            />
          </CardContent>
        </Card>

        {/* Clicks Chart */}
        <Card className="bg-white dark:bg-slate-800/50 border-slate-200 dark:border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <MousePointer className="h-5 w-5 text-[#1E3A8A]" />
              Clicks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SimpleLineChart 
              data={charts.clicks || []} 
              color="#1E3A8A"
              label="Clicks"
            />
          </CardContent>
        </Card>

        {/* Bids Chart */}
        <Card className="bg-white dark:bg-slate-800/50 border-slate-200 dark:border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Gavel className="h-5 w-5 text-[#10B981]" />
              Bid Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SimpleLineChart 
              data={charts.bids || []} 
              color="#10B981"
              label="Bids"
            />
          </CardContent>
        </Card>
      </div>

      {/* Traffic Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sources Breakdown */}
        <Card className="bg-white dark:bg-slate-800/50 border-slate-200 dark:border-slate-700">
          <CardHeader>
            <CardTitle className="text-lg">Traffic Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(analytics?.sources || {}).map(([source, count]) => {
                const total = Object.values(analytics?.sources || {}).reduce((a, b) => a + b, 0) || 1;
                const percentage = ((count / total) * 100).toFixed(1);
                const colors = {
                  homepage: '#06B6D4',
                  marketplace: '#1E3A8A',
                  search: '#10B981',
                  hot_items: '#F59E0B',
                  direct: '#8B5CF6',
                  unknown: '#64748B'
                };
                return (
                  <div key={source}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="capitalize text-slate-600 dark:text-slate-300">{source.replace('_', ' ')}</span>
                      <span className="font-medium text-slate-900 dark:text-white">{count} ({percentage}%)</span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full rounded-full transition-all duration-500"
                        style={{ 
                          width: `${percentage}%`,
                          backgroundColor: colors[source] || '#64748B'
                        }}
                      />
                    </div>
                  </div>
                );
              })}
              {Object.keys(analytics?.sources || {}).length === 0 && (
                <p className="text-center text-slate-400 py-8">No traffic data yet</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Top Performing Listings */}
        <Card className="bg-white dark:bg-slate-800/50 border-slate-200 dark:border-slate-700">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-[#06B6D4]" />
              Top Performing Listings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(analytics?.top_listings || []).map((listing, idx) => (
                <div 
                  key={listing.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#06B6D4] flex items-center justify-center text-white text-sm font-bold">
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-900 dark:text-white truncate">{listing.title}</p>
                    <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span className="flex items-center gap-1">
                        <Eye className="h-3 w-3" /> {listing.views || 0}
                      </span>
                      <span className="flex items-center gap-1">
                        <MousePointer className="h-3 w-3" /> {listing.clicks || 0}
                      </span>
                    </div>
                  </div>
                  <Badge className={`${listing.status === 'active' ? 'bg-green-500' : 'bg-slate-500'} text-white border-0`}>
                    {listing.status}
                  </Badge>
                </div>
              ))}
              {(analytics?.top_listings || []).length === 0 && (
                <p className="text-center text-slate-400 py-8">No listings yet</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Stats Footer */}
      <Card className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <Package className="h-10 w-10 text-white/80" />
              <div>
                <p className="text-white/80 text-sm">Active Listings</p>
                <p className="text-3xl font-bold">{summary.active_listings || 0}</p>
              </div>
            </div>
            <div className="h-12 w-px bg-white/20 hidden sm:block" />
            <div className="flex items-center gap-4">
              <DollarSign className="h-10 w-10 text-white/80" />
              <div>
                <p className="text-white/80 text-sm">Total Listings</p>
                <p className="text-3xl font-bold">{summary.total_listings || 0}</p>
              </div>
            </div>
            <div className="h-12 w-px bg-white/20 hidden sm:block" />
            <div className="text-center sm:text-right">
              <p className="text-white/80 text-sm">Data Period</p>
              <p className="text-lg font-semibold">
                {period === '7d' ? 'Last 7 Days' : period === '30d' ? 'Last 30 Days' : 'Last 90 Days'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SellerAnalyticsDashboard;
