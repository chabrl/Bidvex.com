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
import { TrendingUp, Users, DollarSign, RefreshCw, Trophy, Zap, X, Briefcase, Mail } from 'lucide-react';
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

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
  const [windowDays, setWindowDays] = useState(30);
  const [retriggerTarget, setRetriggerTarget] = useState(null);
  const [retriggerSubmitting, setRetriggerSubmitting] = useState(false);

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

  // iter246 Mission 2 — Re-trigger flow.
  const confirmRetrigger = async () => {
    if (!retriggerTarget?.promotion_id) return;
    setRetriggerSubmitting(true);
    try {
      const res = await axios.post(
        `${API}/admin/promotions/${retriggerTarget.promotion_id}/re-trigger`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(
        `Re-launched as ${res?.data?.coupon_code || 'new coupon'}`,
        { description: 'Active immediately under a fresh code.' }
      );
      setRetriggerTarget(null);
      // Soft-refresh the dashboard matrices.
      fetchAnalytics();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Re-trigger failed');
    } finally {
      setRetriggerSubmitting(false);
    }
  };

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

  // iter249 Mission 2 — B2B Partner Acquisition ROI block.
  const partnerRoi = data?.partner_roi || {};
  // iter249 Mission 1 — Send-Preview-to-Self handler.
  const { user } = useAuth();
  const [previewSubmitting, setPreviewSubmitting] = useState(false);
  const sendPreviewToSelf = async () => {
    const adminEmail = user?.email || '';
    if (!adminEmail) {
      toast.error('Could not resolve your session email');
      return;
    }
    setPreviewSubmitting(true);
    try {
      const res = await axios.post(
        `${API}/admin/promotions/partner-outreach/send`,
        { recipient_emails: [adminEmail] },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res?.data?.is_preview) {
        toast.success(
          'Success! Check your inbox for the live email and PDF guide.',
          { description: `Sent to ${adminEmail}` },
        );
      } else {
        toast.success('Preview dispatched');
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Send preview failed');
    } finally {
      setPreviewSubmitting(false);
    }
  };

  return (
    <div
      className="space-y-4 mb-6"
      data-testid="promotion-analytics-dashboard"
    >
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-bold flex items-center gap-2 text-slate-900">
            <TrendingUp className="h-4 w-4 text-indigo-600" />
            Promotion Performance — Last {windowDays} days
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Live ROI from <code className="text-[10px] bg-slate-100 px-1 rounded">promotion_usage</code>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* iter246 Mission 1 — Ad-hoc time-window selector */}
          <Select
            value={String(windowDays)}
            onValueChange={(v) => setWindowDays(parseInt(v, 10))}
          >
            <SelectTrigger
              className="h-9 w-[150px] text-xs"
              data-testid="analytics-window-select"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7" data-testid="analytics-window-7">Last 7 days</SelectItem>
              <SelectItem value="30" data-testid="analytics-window-30">Last 30 days</SelectItem>
              <SelectItem value="90" data-testid="analytics-window-90">Last 90 days</SelectItem>
              <SelectItem value="365" data-testid="analytics-window-365">Last 365 days</SelectItem>
            </SelectContent>
          </Select>
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
          {/* iter249 Mission 1 — Self-preview blast */}
          <Button
            size="sm"
            onClick={sendPreviewToSelf}
            disabled={previewSubmitting}
            className="bg-gradient-to-r from-indigo-600 to-blue-600 text-white border-0 hover:opacity-90"
            data-testid="send-preview-to-myself-btn"
          >
            <Mail className={`h-3.5 w-3.5 mr-1.5 ${previewSubmitting ? 'animate-pulse' : ''}`} />
            {previewSubmitting ? 'Sending preview...' : '✉️ Send Preview to Myself'}
          </Button>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
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
            {/* iter249 Mission 2 — B2B Partner Acquisition ROI */}
            <KpiCard
              icon={Briefcase}
              label="B2B Partner Acquisition ROI"
              value={`${(partnerRoi.partner_conversion_rate_pct ?? 0).toFixed(2)}%`}
              sublabel={`${partnerRoi.partners_redeemed || 0} / ${partnerRoi.total_registered_partners || 0} partners · ${formatCAD(partnerRoi.projected_gmv_lift_cad || 0)} 90-day GMV`}
              accent="indigo"
              testid="kpi-b2b-partner-roi"
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
                    <div className="flex items-center justify-between mb-1.5 gap-2">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
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
                      <div className="flex items-center gap-1.5 whitespace-nowrap">
                        <span className="text-xs font-bold text-emerald-700 tabular-nums">
                          {formatCAD(c.saved_amount_cad)}
                        </span>
                        {/* iter246 Mission 2 — Re-trigger CTA */}
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                          title="Clone & re-launch this campaign"
                          onClick={() => setRetriggerTarget(c)}
                          data-testid={`top-campaign-retrigger-${idx}`}
                        >
                          <Zap className="h-3.5 w-3.5" />
                        </Button>
                      </div>
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

      {/* iter246 Mission 2 — Re-trigger confirmation modal */}
      <Dialog
        open={!!retriggerTarget}
        onOpenChange={(open) => {
          if (!open) setRetriggerTarget(null);
        }}
      >
        <DialogContent
          className="max-w-md"
          data-testid="retrigger-confirm-dialog"
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Zap className="h-4 w-4 text-amber-500" />
              Re-launch Campaign
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to clone and re-launch this high-performing
              campaign target group immediately under a new coupon code?
            </DialogDescription>
          </DialogHeader>
          {retriggerTarget && (
            <div className="bg-slate-50 border border-slate-200 rounded-md p-3 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-500">Source coupon</span>
                <code className="font-mono text-slate-900">
                  {retriggerTarget.coupon_code}
                </code>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Type</span>
                <span className="text-slate-900">{retriggerTarget.promotion_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Past saved</span>
                <span className="text-emerald-700 font-semibold tabular-nums">
                  {formatCAD(retriggerTarget.saved_amount_cad)} from{' '}
                  {retriggerTarget.redemption_count} redemption
                  {retriggerTarget.redemption_count === 1 ? '' : 's'}
                </span>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setRetriggerTarget(null)}
              disabled={retriggerSubmitting}
              data-testid="retrigger-cancel-btn"
            >
              <X className="h-3.5 w-3.5 mr-1.5" />
              Cancel
            </Button>
            <Button
              type="button"
              onClick={confirmRetrigger}
              disabled={retriggerSubmitting}
              className="bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0"
              data-testid="retrigger-confirm-btn"
            >
              <Zap className={`h-3.5 w-3.5 mr-1.5 ${retriggerSubmitting ? 'animate-pulse' : ''}`} />
              {retriggerSubmitting ? 'Re-launching…' : 'Re-launch now'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PromotionAnalyticsDashboard;
