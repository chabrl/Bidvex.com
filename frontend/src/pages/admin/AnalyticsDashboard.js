import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { TrendingUp, Download, RefreshCw } from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const AnalyticsDashboard = () => {
  const { t } = useTranslation();
  const [revenueData, setRevenueData] = useState([]);
  const [listingData, setListingData] = useState({});
  const [summary, setSummary] = useState({ active_listings: 0, total_users: 0, total_revenue: 0 });
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const [revenueRes, listingsRes, summaryRes] = await Promise.all([
        axios.get(`${API}/admin/analytics/revenue?days=${days}`).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/analytics/listings`).catch(() => ({ data: {} })),
        axios.get(`${API}/admin/analytics?days=${days}`).catch(() => ({ data: {} })),
      ]);
      const revData = revenueRes.data;
      setRevenueData(Array.isArray(revData) ? revData : (revData.daily || revData.revenue_data || []));
      const listData = listingsRes.data;
      setListingData(listData && !Array.isArray(listData) ? listData : (listData.daily || {}));
      setSummary(summaryRes.data || {});
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
    </div>
  );
};

export default AnalyticsDashboard;
