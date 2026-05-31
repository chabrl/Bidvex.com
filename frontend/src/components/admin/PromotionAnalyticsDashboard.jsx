/**
 * iter245 Mission 2 — Promotion Performance Dashboard
 *
 * Renders three production-grade tiles on top of the Admin Promotions
 * Engine view: gross-metrics KPI strip, top-5 campaigns leaderboard
 * with progress bars, and a 30-day redemption velocity chart.
 *
 * Data: GET /api/admin/promotions/analytics/dashboard
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import API_BASE from '../../config';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { Button } from '../ui/button';
import { TrendingUp, Users, DollarSign, RefreshCw, Trophy } from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';

const API = API_BASE;

const formatCAD = (v) =>
  new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 2,
  }).format(Number(v || 0));

const formatDayShort = (iso) => {
  // "2026-02-15" → "Feb 15"
  if (!iso || typeof iso !== 'string') return iso;
  const [, m, d] = iso.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const mi = parseInt(m, 10) - 1;
  return `${months[mi] || m} ${parseInt(d, 10)}`;
};

const KpiCard = ({ icon: Icon, label, value, sublabel, testid, accent = 'amber' }) => {
  const accentMap = {
    amber: 'from-amber-500 to-orange-500',
    emerald: 'from-emerald-500 to-teal-500',
    indigo: 'from-indigo-500 to-blue-500',
  };
  return (
    <Card
      data-testid={testid}
      className="relative overflow-hidden border border-slate-200 hover:shadow-md transition-shadow"
    >
      <div
        className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${accentMap[accent] || accentMap.amber}`}
      />
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
              {label}
            </p>
            <p
              className="text-3xl font-extrabold text-slate-900 mt-2 tabular-nums"
              data-testid={`${testid}-value`}
            >
              {value}
            </p>
            {sublabel && (
              <p className="text-xs text-slate-500 mt-1.5">{sublabel}</p>
            )}
          </div>
          <div className={`p-2.5 rounded-lg bg-gradient-to-br ${accentMap[accent] || accentMap.amber} text-white shadow-sm`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const PromotionAnalyticsDashboard = () => {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [windowDays] = useState(30);

  const fetchAnalytics = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await axios.get(
        `${API}/admin/promotions/analytics/dashboard?window_days=${windowDays}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setData(res.data);
    } catch (e) {
      toast.error(
        e?.response?.data?.detail || 'Could not load promotion analytics'
      );
    } finally {
      setLoading(false);
    }
  }, [token, windowDays]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const gross = data?.gross_metrics || {};
  const topCampaigns = data?.top_campaigns || [];
  const velocity = data?.velocity_timeline || [];

  // Conversion-lift heuristic: redemption_count / unique_redeemers. Higher
  // means power-users come back. Falls back to 0 when no redemptions exist.
  const conversionLift =
    gross.unique_user_redeemers_count > 0
      ? (gross.total_active_redemptions / gross.unique_user_redeemers_count).toFixed(2)
      : '0.00';

  // Pre-format chart rows so XAxis labels stay compact.
  const chartData = velocity.map((row) => ({
    ...row,
    label: formatDayShort(row.date),
  }));

  return (
    <div
      className="space-y-4 mb-6"
      data-testid="promotion-analytics-dashboard"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold flex items-center gap-2 text-slate-900">
            <TrendingUp className="h-4 w-4 text-indigo-600" />
            Promotion Performance — Last {windowDays} days
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Live ROI from <code className="text-[10px] bg-slate-100 px-1 rounded">promotion_usage</code>
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchAnalytics}
          disabled={loading}
          data-testid="promotion-analytics-refresh-btn"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[112px] w-full rounded-lg" data-testid={`kpi-skeleton-${i}`} />
          ))
        ) : (
          <>
            <KpiCard
              icon={DollarSign}
              label="Total Saved GMV"
              value={formatCAD(gross.total_gmv_saved_cad)}
              sublabel="Sum of discount across all promo redemptions"
              accent="emerald"
              testid="kpi-total-saved-gmv"
            />
            <KpiCard
              icon={Trophy}
              label="Coupon Redemptions"
              value={gross.total_active_redemptions || 0}
              sublabel={`${gross.unique_user_redeemers_count || 0} unique users`}
              accent="amber"
              testid="kpi-total-redemptions"
            />
            <KpiCard
              icon={Users}
              label="Conversion Lift"
              value={`${conversionLift}×`}
              sublabel="Redemptions per unique user"
              accent="indigo"
              testid="kpi-conversion-lift"
            />
          </>
        )}
      </div>

      {/* Top Campaigns + Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
        {/* Top 5 leaderboard — 2 columns */}
        <Card className="lg:col-span-2 border border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              Top 5 Campaigns
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {loading ? (
              <div className="space-y-2" data-testid="top-campaigns-loading">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : topCampaigns.length === 0 ? (
              <div
                className="py-10 text-center text-xs text-slate-500"
                data-testid="top-campaigns-empty"
              >
                No redemptions yet in the last {windowDays} days.
              </div>
            ) : (
              <div className="space-y-2" data-testid="top-campaigns-list">
                {topCampaigns.map((c, idx) => (
                  <div
                    key={c.promotion_id || idx}
                    className="border border-slate-100 rounded-md p-2.5 hover:bg-slate-50 transition-colors"
                    data-testid={`top-campaign-row-${idx}`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-[10px] font-bold text-slate-400 w-4">
                          #{idx + 1}
                        </span>
                        <code className="text-[11px] bg-slate-100 px-1.5 py-0.5 rounded font-mono truncate">
                          {c.coupon_code}
                        </code>
                        <Badge variant="outline" className="text-[9px] py-0">
                          {c.promotion_type}
                        </Badge>
                      </div>
                      <span className="text-xs font-bold text-emerald-700 tabular-nums whitespace-nowrap">
                        {formatCAD(c.saved_amount_cad)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all"
                          style={{
                            width: `${Math.min(100, Math.max(2, c.percent_of_total || 0))}%`,
                          }}
                          data-testid={`top-campaign-bar-${idx}`}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 tabular-nums w-12 text-right">
                        {(c.percent_of_total || 0).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1">
                      {c.redemption_count} redemption{c.redemption_count === 1 ? '' : 's'} ·{' '}
                      <span className="text-slate-600">{c.name_en}</span>
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Velocity chart — 3 columns */}
        <Card className="lg:col-span-3 border border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-indigo-500" />
              Redemption Velocity
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {loading ? (
              <Skeleton
                className="h-[240px] w-full"
                data-testid="velocity-chart-skeleton"
              />
            ) : (
              <div
                className="h-[240px] w-full"
                data-testid="velocity-chart-wrapper"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="#f1f5f9" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="label"
                      stroke="#94a3b8"
                      fontSize={10}
                      tickMargin={6}
                      interval={Math.max(0, Math.floor(chartData.length / 8) - 1)}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={10}
                      allowDecimals={false}
                      width={28}
                    />
                    <Tooltip
                      contentStyle={{
                        fontSize: 11,
                        borderRadius: 6,
                        border: '1px solid #e2e8f0',
                        boxShadow: '0 4px 14px rgba(15, 23, 42, 0.08)',
                      }}
                      formatter={(value, name) => {
                        if (name === 'amount') return [formatCAD(value), 'Saved (CAD)'];
                        return [value, 'Redemptions'];
                      }}
                    />
                    <Legend
                      verticalAlign="top"
                      iconSize={8}
                      wrapperStyle={{ fontSize: 11, paddingBottom: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="uses"
                      name="Redemptions"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="amount"
                      name="Saved (CAD)"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default PromotionAnalyticsDashboard;
