import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts';
import {
  TrendingUp, DollarSign, Users, Gavel, RefreshCw, Loader2, Trophy, Flame,
} from 'lucide-react';
import { toast } from 'sonner';

const API = API_BASE;

const ROLE_COLORS = {
  individual: '#2563eb',
  admin: '#0f172a',
  vehicle_dealer: '#d97706',
  storage_facility: '#7c3aed',
  partner_broker: '#059669',
};
const ROLE_LABELS = {
  individual: 'Individuals',
  admin: 'Admins',
  vehicle_dealer: 'Vehicle Dealers',
  storage_facility: 'Storage Facilities',
  partner_broker: 'Partners / Brokers',
};
const SECTION_LABELS = {
  marketplace: 'Marketplace',
  lots: 'Lots',
  vehicles: 'Vehicles',
  storage: 'Storage',
};

const fmtMoney = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

const KpiCard = ({ icon: Icon, label, value, sub, color, testId }) => (
  <Card data-testid={testId}>
    <CardContent className="pt-5 pb-4">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold mt-1 truncate">{value}</p>
          {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
        </div>
        <Icon className={`h-8 w-8 shrink-0 ${color} opacity-70`} />
      </div>
    </CardContent>
  </Card>
);

const AdvancedAnalytics = () => {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/analytics/overview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (err) {
      console.error(err);
      toast.error('Failed to load advanced analytics');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex justify-center py-16" data-testid="advanced-analytics-loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }
  if (!data) {
    return <p className="text-center text-muted-foreground py-12">No analytics data available.</p>;
  }

  const roleData = Object.entries(data.users_by_role || {}).map(([role, count]) => ({
    name: ROLE_LABELS[role] || role, role, count,
  }));
  const hammerData = Object.entries(data.avg_hammer_by_section || {}).map(([section, avg]) => ({
    name: SECTION_LABELS[section] || section, avg,
  }));
  const sectionStatusData = Object.entries(data.auctions_by_section || {}).map(([section, statuses]) => ({
    name: SECTION_LABELS[section] || section,
    active: statuses.active || 0,
    pending: (statuses.pending_review || 0) + (statuses.pending || 0),
    ended: (statuses.ended || 0) + (statuses.sold || 0) + (statuses.completed || 0) + (statuses.ended_no_sale || 0) + (statuses.expired || 0),
  }));

  return (
    <div className="space-y-6" data-testid="advanced-analytics-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-blue-600" />
            Advanced Analytics
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            GMV, platform revenue, usage and conversion across all four auction sections.
            Generated {data.generated_at ? new Date(data.generated_at).toLocaleString() : '—'}.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => fetchData(true)} disabled={refreshing}
          data-testid="advanced-analytics-refresh-btn">
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard icon={DollarSign} label="GMV (all time)" value={fmtMoney(data.gmv?.all_time)}
          color="text-emerald-600" testId="kpi-gmv-alltime" />
        <KpiCard icon={DollarSign} label="GMV (30 days)" value={fmtMoney(data.gmv?.last_30d)}
          color="text-emerald-500" testId="kpi-gmv-30d" />
        <KpiCard icon={TrendingUp} label="Revenue (all time)" value={fmtMoney(data.platform_revenue?.all_time)}
          sub={`est. ${fmtMoney(data.platform_revenue?.estimated_all_time)} @2.5%`}
          color="text-blue-600" testId="kpi-revenue-alltime" />
        <KpiCard icon={TrendingUp} label="Revenue (30 days)" value={fmtMoney(data.platform_revenue?.last_30d)}
          color="text-blue-500" testId="kpi-revenue-30d" />
        <KpiCard icon={Users} label="Total Users" value={(data.total_users || 0).toLocaleString()}
          color="text-violet-600" testId="kpi-total-users" />
        <KpiCard icon={Gavel} label="Sell-through Rate" value={`${data.conversion_rate_pct ?? 0}%`}
          sub={`${data.conversion_detail?.ended_with_bids || 0}/${data.conversion_detail?.ended_total || 0} ended w/ bids`}
          color="text-amber-600" testId="kpi-conversion-rate" />
      </div>

      {/* Revenue + Signups charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card data-testid="chart-revenue-per-day">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Platform Revenue — last 30 days</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.revenue_per_day || []} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v) => [fmtMoney(v), 'Revenue']} />
                <Area type="monotone" dataKey="amount" stroke="#2563eb" fill="#2563eb" fillOpacity={0.15} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card data-testid="chart-signups-per-day">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">New Signups — last 30 days</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.signups_per_day || []} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip formatter={(v) => [v, 'Signups']} />
                <Bar dataKey="count" fill="#7c3aed" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Sections + roles */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2" data-testid="chart-auctions-by-section">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Auctions by Section &amp; Status</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sectionStatusData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="active" name="Active" stackId="a" fill="#059669" />
                <Bar dataKey="pending" name="Pending Review" stackId="a" fill="#d97706" />
                <Bar dataKey="ended" name="Ended / Sold" stackId="a" fill="#64748b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card data-testid="chart-users-by-role">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Users by Role</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={roleData} dataKey="count" nameKey="name" cx="50%" cy="50%"
                  innerRadius={42} outerRadius={72} paddingAngle={3}>
                  {roleData.map((entry) => (
                    <Cell key={entry.role} fill={ROLE_COLORS[entry.role] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Avg hammer + leaderboards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card data-testid="chart-avg-hammer">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Avg. Hammer Price by Section</CardTitle>
          </CardHeader>
          <CardContent className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hammerData} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
                <Tooltip formatter={(v) => [fmtMoney(v), 'Avg hammer']} />
                <Bar dataKey="avg" fill="#0ea5e9" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card data-testid="top-sellers-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" /> Top Sellers by GMV
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(data.top_sellers || []).length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">No completed sales yet.</p>
            ) : (
              <div className="space-y-2">
                {data.top_sellers.map((s, i) => (
                  <div key={s.seller_id} className="flex items-center justify-between text-sm border-b last:border-0 pb-2 last:pb-0"
                    data-testid={`top-seller-row-${i}`}>
                    <span className="flex items-center gap-2 min-w-0">
                      <Badge variant="secondary" className="text-[10px] shrink-0">#{i + 1}</Badge>
                      <span className="truncate">{s.name}</span>
                    </span>
                    <span className="font-semibold shrink-0">{fmtMoney(s.gmv)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card data-testid="top-listings-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Flame className="h-4 w-4 text-rose-500" /> Most-Bid Listings
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(data.top_listings || []).length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">No bids recorded yet.</p>
            ) : (
              <div className="space-y-2">
                {data.top_listings.map((l, i) => (
                  <div key={l.listing_id} className="flex items-center justify-between text-sm border-b last:border-0 pb-2 last:pb-0"
                    data-testid={`top-listing-row-${i}`}>
                    <span className="flex items-center gap-2 min-w-0">
                      <Badge variant="secondary" className="text-[10px] shrink-0">#{i + 1}</Badge>
                      <span className="truncate" title={l.title}>{l.title}</span>
                    </span>
                    <span className="font-semibold shrink-0">{l.bids} bids</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AdvancedAnalytics;
