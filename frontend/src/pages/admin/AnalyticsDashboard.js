import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  TrendingUp, Download, RefreshCw, Trophy, Tag, Target, Users,
  ShoppingBag, Eye,
} from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const AnalyticsDashboard = () => {
  const { t } = useTranslation();
  const [revenueData, setRevenueData] = useState([]);
  const [listingData, setListingData] = useState({});
  const [summary, setSummary] = useState({ active_listings: 0, total_users: 0, total_revenue: 0 });
  const [advanced, setAdvanced] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const [revenueRes, listingsRes, summaryRes, advancedRes] = await Promise.all([
        axios.get(`${API}/admin/analytics/revenue?days=${days}`).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/analytics/listings`).catch(() => ({ data: {} })),
        axios.get(`${API}/admin/analytics?days=${days}`).catch(() => ({ data: {} })),
        axios.get(`${API}/admin/analytics/advanced?days=${days}`).catch(() => ({ data: null })),
      ]);
      const revData = revenueRes.data;
      setRevenueData(Array.isArray(revData) ? revData : (revData.daily || revData.revenue_data || []));
      const listData = listingsRes.data;
      setListingData(listData && !Array.isArray(listData) ? listData : (listData.daily || {}));
      setSummary(summaryRes.data || {});
      setAdvanced(advancedRes.data || null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const exportToCSV = () => {
    if (!revenueData.length) {
      toast.error('No data to export / Aucune donnée à exporter');
      return;
    }
    const csv = [
      ['Date', 'Revenue'],
      ...revenueData.map(d => [d.date || '', d.revenue ?? 0])
    ].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bidvex-analytics-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Analytics exported to CSV');
  };

  const totalRevenue = revenueData.reduce((sum, d) => sum + (d.revenue || 0), 0);

  return (
    <div className="space-y-6" data-testid="analytics-dashboard">
      <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><TrendingUp className="h-6 w-6" />Advanced Analytics</h2>
          <p className="text-muted-foreground">Revenue trends and platform insights</p>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <label className="text-sm text-muted-foreground">Period:</label>
          <select value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="h-10 px-3 border rounded-md bg-background text-sm"
            data-testid="analytics-date-range">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last 12 months</option>
          </select>
          <Button variant="outline" size="sm" onClick={fetchAnalytics} disabled={loading}
            data-testid="analytics-refresh">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Button onClick={exportToCSV} variant="outline" data-testid="analytics-export-csv">
            <Download className="h-4 w-4 mr-2" />Export CSV
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)
        ) : (
          <>
            <Card><CardContent className="p-6">
              <p className="text-2xl font-bold gradient-text">{formatCurrency(totalRevenue || summary.total_revenue || 0)}</p>
              <p className="text-sm text-muted-foreground">Total Revenue ({days}d)</p>
            </CardContent></Card>
            <Card><CardContent className="p-6">
              <p className="text-2xl font-bold text-green-600">{summary.active_listings || listingData.active || 0}</p>
              <p className="text-sm text-muted-foreground">Active Listings</p>
            </CardContent></Card>
            <Card><CardContent className="p-6">
              <p className="text-2xl font-bold text-blue-600">{summary.total_users || 0}</p>
              <p className="text-sm text-muted-foreground">Total Users</p>
            </CardContent></Card>
            <Card><CardContent className="p-6">
              <p className="text-2xl font-bold text-yellow-600">{listingData.pending || 0}</p>
              <p className="text-sm text-muted-foreground">Pending Review</p>
            </CardContent></Card>
          </>
        )}
      </div>

      <Card>
        <CardHeader><CardTitle>Revenue Trend ({days} days)</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : revenueData.length > 0 ? (
            <div className="space-y-2">
              {revenueData.slice().reverse().slice(0, 10).map((data, i) => (
                <div key={data.date || i} className="flex justify-between items-center p-3 border rounded-lg">
                  <span className="text-sm font-medium">
                    {data.date ? new Date(data.date).toLocaleDateString() : `Day ${i+1}`}
                  </span>
                  <span className="text-lg font-bold gradient-text">{formatCurrency(data.revenue || 0)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              No revenue data yet<br /><span className="text-xs">Aucune donnée de revenu</span>
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("admin.listingStatusDistribution")}</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 border rounded-lg">
                <p className="text-3xl font-bold text-green-600">{listingData.active || 0}</p>
                <p className="text-sm text-muted-foreground">Active</p>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <p className="text-3xl font-bold text-blue-600">{listingData.sold || 0}</p>
                <p className="text-sm text-muted-foreground">Sold</p>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <p className="text-3xl font-bold text-yellow-600">{listingData.pending || 0}</p>
                <p className="text-sm text-muted-foreground">Pending</p>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <p className="text-3xl font-bold text-red-600">{listingData.cancelled || 0}</p>
                <p className="text-sm text-muted-foreground">Cancelled</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ─────────────── ADVANCED ANALYTICS ─────────────── */}
      {/* Conversion rates */}
      <Card data-testid="conversion-rate-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-emerald-600" />
            Conversion Rates ({days}d)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading || !advanced ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-5 border rounded-lg bg-gradient-to-br from-emerald-50 to-white dark:from-emerald-950/40 dark:to-slate-900">
                <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  <ShoppingBag className="h-3.5 w-3.5" /> Listing &rarr; Sale
                </div>
                <p className="text-3xl font-bold text-emerald-600" data-testid="conv-listing-rate">
                  {(advanced.conversion.listing_to_sale.rate * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  {advanced.conversion.listing_to_sale.sold_listings} sold / {advanced.conversion.listing_to_sale.total_listings} listings
                </p>
              </div>
              <div className="p-5 border rounded-lg bg-gradient-to-br from-blue-50 to-white dark:from-blue-950/40 dark:to-slate-900">
                <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  <Eye className="h-3.5 w-3.5" /> Visitor &rarr; Bidder
                </div>
                <p className="text-3xl font-bold text-blue-600" data-testid="conv-bidder-rate">
                  {(advanced.conversion.visitor_to_bidder.rate * 100).toFixed(2)}%
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  {advanced.conversion.visitor_to_bidder.total_bids.toLocaleString()} bids / {advanced.conversion.visitor_to_bidder.total_views.toLocaleString()} views
                </p>
              </div>
              <div className="p-5 border rounded-lg bg-gradient-to-br from-violet-50 to-white dark:from-violet-950/40 dark:to-slate-900">
                <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  <Users className="h-3.5 w-3.5" /> Signup &rarr; Action
                </div>
                <p className="text-3xl font-bold text-violet-600" data-testid="conv-signup-rate">
                  {(advanced.conversion.signup_to_action.rate * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  {advanced.conversion.signup_to_action.users_with_action} active / {advanced.conversion.signup_to_action.new_users} signups
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Top sellers */}
      <Card data-testid="top-sellers-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-500" />
            Top Sellers ({days}d)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading || !advanced ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : advanced.top_sellers.length === 0 ? (
            <p className="text-center text-muted-foreground py-8 text-sm">
              No sales recorded in this period.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wider">
                    <th className="text-left py-2 pr-2 w-8">#</th>
                    <th className="text-left py-2 pr-3">Seller</th>
                    <th className="text-right py-2 px-3">Items Sold</th>
                    <th className="text-right py-2 px-3">Avg. Price</th>
                    <th className="text-right py-2 pl-3">Total Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {advanced.top_sellers.map((s, idx) => (
                    <tr key={s.seller_id} className="border-b last:border-0 hover:bg-accent/30 transition-colors">
                      <td className="py-2 pr-2 font-semibold text-muted-foreground">{idx + 1}</td>
                      <td className="py-2 pr-3">
                        <p className="font-medium truncate max-w-[220px]" title={s.name}>{s.name}</p>
                        <p className="text-xs text-muted-foreground truncate max-w-[220px]" title={s.email}>{s.email}</p>
                      </td>
                      <td className="py-2 px-3 text-right font-semibold">{s.items_sold}</td>
                      <td className="py-2 px-3 text-right">{formatCurrency(s.avg_sale_price)}</td>
                      <td className="py-2 pl-3 text-right">
                        <span className="font-bold gradient-text">{formatCurrency(s.total_revenue)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Top categories */}
      <Card data-testid="top-categories-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-5 w-5 text-cyan-600" />
            Top Categories ({days}d)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading || !advanced ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : advanced.top_categories.length === 0 ? (
            <p className="text-center text-muted-foreground py-8 text-sm">
              No listings in this period.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wider">
                    <th className="text-left py-2 pr-2 w-8">#</th>
                    <th className="text-left py-2 pr-3">Category</th>
                    <th className="text-right py-2 px-3">Listings</th>
                    <th className="text-right py-2 px-3">Sold</th>
                    <th className="text-right py-2 px-3">Sell-through</th>
                    <th className="text-right py-2 pl-3">Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {advanced.top_categories.map((c, idx) => (
                    <tr key={c.category} className="border-b last:border-0 hover:bg-accent/30 transition-colors">
                      <td className="py-2 pr-2 font-semibold text-muted-foreground">{idx + 1}</td>
                      <td className="py-2 pr-3">
                        <Badge variant="outline" className="capitalize">{c.category}</Badge>
                      </td>
                      <td className="py-2 px-3 text-right font-semibold">{c.total_listings}</td>
                      <td className="py-2 px-3 text-right">{c.sold_count}</td>
                      <td className="py-2 px-3 text-right">
                        <span className={`font-medium ${c.sell_through_rate >= 0.5 ? 'text-emerald-600' : c.sell_through_rate >= 0.25 ? 'text-amber-600' : 'text-muted-foreground'}`}>
                          {(c.sell_through_rate * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-2 pl-3 text-right font-bold gradient-text">{formatCurrency(c.total_revenue)}</td>
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
};

export default AnalyticsDashboard;
