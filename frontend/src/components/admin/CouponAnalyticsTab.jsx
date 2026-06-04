/**
 * iter275 — Admin Coupon Conversion Analytics.
 *
 * Side-by-side performance tab that surfaces the full auctioneer
 * acquisition funnel per external campaign:
 *
 *     minted → emailed → opened → clicked → REDEEMED (paid trial signup)
 *
 * All data is computed client-side from two existing endpoints — no
 * new backend models were required:
 *
 *   • GET /api/admin/promotions/coupons      — per-coupon timeline
 *     (`created_at`, `redeemed_at`, `status`, `source`, `campaign_id`,
 *      `campaign_slug`)
 *   • GET /api/admin/external-campaigns      — campaign metadata
 *     (`name`, `subject_en`, `analytics.opened`, `.clicked`,
 *      `.delivered`)
 *
 * The view aggregates coupons by `campaign_id`, joins each row to its
 * SendGrid analytics, and renders:
 *
 *   1. A summary KPI strip (totals across all coupons).
 *   2. A per-campaign side-by-side table sorted by redemption rate
 *      so admins can pick the winning subject line at a glance.
 *   3. A recharts horizontal bar chart comparing minted vs redeemed
 *      counts across the top campaigns.
 *
 * Three tabs surface different cuts of the same dataset so an admin
 * can answer "which subject converts?" and "what's the average
 * mint-to-redeem latency?" without leaving the page.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, Legend,
} from 'recharts';
import {
  Card, CardContent, CardHeader, CardTitle,
} from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../components/ui/tabs';
import { RefreshCw, TrendingUp, Target, Ticket, Mail } from 'lucide-react';
import API_BASE from '../../config';

const API = API_BASE;

const safePct = (num, denom) => {
  const n = Number(num) || 0;
  const d = Number(denom) || 0;
  if (d <= 0) return 0;
  return Math.round((n / d) * 1000) / 10;
};

const hoursBetween = (startIso, endIso) => {
  try {
    const a = new Date(startIso).getTime();
    const b = new Date(endIso).getTime();
    if (!a || !b || b < a) return null;
    return Math.round((b - a) / 36e5);
  } catch {
    return null;
  }
};

// Numeric formatter — keeps cells aligned across the table.
const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());

const CouponAnalyticsTab = ({ token }) => {
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }),
    [token],
  );

  const [coupons, setCoupons] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [partnerFilter, setPartnerFilter] = useState('all');

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [couponsRes, campaignsRes] = await Promise.all([
        axios.get(`${API}/admin/promotions/coupons`, { headers, params: { limit: 500 } }),
        axios.get(`${API}/admin/external-campaigns`, { headers, params: { limit: 100 } }),
      ]);
      setCoupons(Array.isArray(couponsRes.data?.items) ? couponsRes.data.items : []);
      setCampaigns(Array.isArray(campaignsRes.data?.campaigns) ? campaignsRes.data.campaigns : []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load coupon analytics');
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ── Aggregate per-campaign rows ─────────────────────────────────────
  //
  // For each campaign that issued ≥1 coupon (`source==='external_campaign'`)
  // we compute mint/redeem totals + the average mint→redeem latency.
  // Manual coupons (no campaign_id) are bucketed under a synthetic
  // "Manual / Direct" row so the admin still sees the volume.
  const { rows, totals } = useMemo(() => {
    const filteredCoupons = (partnerFilter === 'all')
      ? coupons
      : coupons.filter((c) => c.partner_type === partnerFilter);

    const campMap = new Map();
    for (const camp of campaigns) {
      campMap.set(camp.id, camp);
    }
    const buckets = new Map();
    const MANUAL_KEY = '__manual__';

    for (const c of filteredCoupons) {
      const key = c.campaign_id || MANUAL_KEY;
      if (!buckets.has(key)) {
        const camp = campMap.get(c.campaign_id);
        buckets.set(key, {
          campaign_id:   c.campaign_id || null,
          campaign_name: camp?.name || (c.campaign_id ? c.campaign_id : 'Manual / Direct'),
          subject_en:    camp?.subject_en || (key === MANUAL_KEY ? '— (no campaign)' : '—'),
          partner_types: new Set(),
          minted: 0,
          redeemed: 0,
          revoked: 0,
          expired: 0,
          delivered: camp?.analytics?.delivered || 0,
          opened:    camp?.analytics?.opened    || 0,
          clicked:   camp?.analytics?.clicked   || 0,
          mint_dates: [],
          redeem_latencies_hours: [],
          first_minted: null,
          last_minted:  null,
        });
      }
      const b = buckets.get(key);
      b.minted += 1;
      b.partner_types.add(c.partner_type);
      if (c.status === 'redeemed') {
        b.redeemed += 1;
        const lat = hoursBetween(c.created_at, c.redeemed_at);
        if (lat != null) b.redeem_latencies_hours.push(lat);
      } else if (c.status === 'revoked') {
        b.revoked += 1;
      } else if (c.status === 'expired') {
        b.expired += 1;
      }
      if (c.created_at) {
        b.mint_dates.push(c.created_at);
        if (!b.first_minted || c.created_at < b.first_minted) b.first_minted = c.created_at;
        if (!b.last_minted || c.created_at > b.last_minted)   b.last_minted = c.created_at;
      }
    }

    const out = [];
    for (const b of buckets.values()) {
      const avgLatencyH = b.redeem_latencies_hours.length
        ? Math.round(
            b.redeem_latencies_hours.reduce((a, x) => a + x, 0) / b.redeem_latencies_hours.length,
          )
        : null;
      out.push({
        ...b,
        partner_types_list:  Array.from(b.partner_types).sort(),
        redemption_rate_pct: safePct(b.redeemed, b.minted),
        click_to_redeem_pct: safePct(b.redeemed, b.clicked),
        delivered_to_redeem_pct: safePct(b.redeemed, b.delivered),
        avg_mint_to_redeem_hours: avgLatencyH,
      });
    }
    // Sort by redemption_rate_pct DESC so the winning subject lines
    // surface at the top of the side-by-side comparison.
    out.sort((a, b) => (b.redemption_rate_pct - a.redemption_rate_pct) || (b.minted - a.minted));

    // Totals strip (across the filter).
    const t = {
      minted:   filteredCoupons.length,
      redeemed: filteredCoupons.filter((c) => c.status === 'redeemed').length,
      revoked:  filteredCoupons.filter((c) => c.status === 'revoked').length,
      campaigns_active: out.filter((b) => b.campaign_id).length,
    };
    t.redemption_rate_pct = safePct(t.redeemed, t.minted);

    return { rows: out, totals: t };
  }, [coupons, campaigns, partnerFilter]);

  // Top-10 campaigns for the recharts bar comparison.
  const chartData = useMemo(() => {
    return rows
      .filter((r) => r.campaign_id)
      .slice(0, 10)
      .map((r) => ({
        name: (r.campaign_name || '—').slice(0, 24),
        minted: r.minted,
        redeemed: r.redeemed,
      }));
  }, [rows]);

  return (
    <Card data-testid="coupon-analytics-tab">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
              📊 Coupon Conversion Analytics
            </CardTitle>
            <p className="text-xs text-slate-500 mt-1">
              Acquisition funnel per external campaign — minted →
              clicked → redeemed (paid trial signup).
            </p>
          </div>
          <div className="flex gap-2">
            <select
              className="border border-slate-300 rounded-md text-xs px-2 py-1.5"
              value={partnerFilter}
              onChange={(e) => setPartnerFilter(e.target.value)}
              data-testid="coupon-analytics-partner-filter"
            >
              <option value="all">All partner types</option>
              <option value="dealer">Dealers (30d)</option>
              <option value="broker">Brokers (60d)</option>
              <option value="storage">Storage (45d)</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={loadAll}
              data-testid="coupon-analytics-refresh"
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── KPI strip ── */}
        <div
          className="grid grid-cols-2 md:grid-cols-4 gap-3"
          data-testid="coupon-analytics-kpis"
        >
          <KpiCard
            testid="kpi-total-minted"
            label="Total Minted"
            value={totals.minted}
            sub="across all sources"
            icon={<Ticket className="h-4 w-4 text-blue-500" />}
            tone="blue"
          />
          <KpiCard
            testid="kpi-total-redeemed"
            label="Total Redeemed"
            value={totals.redeemed}
            sub={`${totals.redemption_rate_pct}% conversion rate`}
            icon={<Target className="h-4 w-4 text-emerald-500" />}
            tone="emerald"
          />
          <KpiCard
            testid="kpi-active-campaigns"
            label="Active Campaigns"
            value={totals.campaigns_active}
            sub="with ≥1 mint"
            icon={<Mail className="h-4 w-4 text-indigo-500" />}
            tone="indigo"
          />
          <KpiCard
            testid="kpi-revoked"
            label="Revoked / Expired"
            value={totals.revoked}
            sub={`${safePct(totals.revoked, totals.minted)}% of minted`}
            icon={<Ticket className="h-4 w-4 text-rose-500" />}
            tone="rose"
          />
        </div>

        {/* ── Tabbed views ── */}
        <Tabs defaultValue="comparison" className="w-full">
          <TabsList
            className="grid grid-cols-3 w-full max-w-md"
            data-testid="coupon-analytics-tabs"
          >
            <TabsTrigger value="comparison" data-testid="coupon-analytics-tab-comparison">
              Subject A/B
            </TabsTrigger>
            <TabsTrigger value="chart" data-testid="coupon-analytics-tab-chart">
              Bar Chart
            </TabsTrigger>
            <TabsTrigger value="timeline" data-testid="coupon-analytics-tab-timeline">
              Timeline
            </TabsTrigger>
          </TabsList>

          {/* ── Subject-line A/B comparison table ── */}
          <TabsContent value="comparison" className="mt-3">
            <div className="overflow-x-auto rounded-md border border-slate-200">
              {loading ? (
                <p className="text-xs text-slate-500 text-center py-6">Loading…</p>
              ) : rows.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">
                  No coupons issued yet. Mint one from the Partner Trial Offers
                  card above, or attach a coupon to an external campaign.
                </p>
              ) : (
                <table
                  className="w-full text-xs"
                  data-testid="coupon-analytics-comparison-table"
                >
                  <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                    <tr>
                      <th className="text-left p-2">Campaign / Subject</th>
                      <th className="text-left p-2">Partner</th>
                      <th className="text-right p-2">Minted</th>
                      <th className="text-right p-2">Delivered</th>
                      <th className="text-right p-2">Opened</th>
                      <th className="text-right p-2">Clicked</th>
                      <th className="text-right p-2 bg-emerald-50">Redeemed</th>
                      <th className="text-right p-2 bg-emerald-50">Mint→Redeem %</th>
                      <th className="text-right p-2">Click→Redeem %</th>
                      <th className="text-right p-2">Avg Latency (h)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, idx) => (
                      <tr
                        key={r.campaign_id || `manual-${idx}`}
                        className="border-t border-slate-100 hover:bg-slate-50"
                        data-testid={`coupon-row-${r.campaign_id || 'manual'}`}
                      >
                        <td className="p-2">
                          <div className="font-semibold text-slate-900 truncate max-w-[260px]">
                            {r.campaign_name}
                          </div>
                          <div
                            className="text-slate-500 truncate max-w-[260px]"
                            title={r.subject_en}
                          >
                            {r.subject_en}
                          </div>
                        </td>
                        <td className="p-2">
                          {r.partner_types_list.map((p) => (
                            <Badge key={p} className="mr-1 text-[10px] bg-slate-100 text-slate-700 border border-slate-300">
                              {p}
                            </Badge>
                          ))}
                        </td>
                        <td className="text-right p-2 font-mono">{fmt(r.minted)}</td>
                        <td className="text-right p-2 font-mono text-slate-500">{fmt(r.delivered)}</td>
                        <td className="text-right p-2 font-mono text-slate-500">{fmt(r.opened)}</td>
                        <td className="text-right p-2 font-mono text-slate-500">{fmt(r.clicked)}</td>
                        <td className="text-right p-2 font-mono font-bold text-emerald-700 bg-emerald-50/60">
                          {fmt(r.redeemed)}
                        </td>
                        <td
                          className="text-right p-2 font-mono font-bold bg-emerald-50/60"
                          data-testid={`coupon-redemption-rate-${r.campaign_id || 'manual'}`}
                        >
                          <span
                            className={
                              r.redemption_rate_pct >= 10 ? 'text-emerald-700'
                                : r.redemption_rate_pct >= 3 ? 'text-amber-700'
                                : 'text-slate-500'
                            }
                          >
                            {r.redemption_rate_pct}%
                          </span>
                        </td>
                        <td className="text-right p-2 font-mono text-slate-500">
                          {r.clicked > 0 ? `${r.click_to_redeem_pct}%` : '—'}
                        </td>
                        <td className="text-right p-2 font-mono text-slate-500">
                          {r.avg_mint_to_redeem_hours != null ? r.avg_mint_to_redeem_hours : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <p className="text-[10px] text-slate-400 mt-2">
              Rows sorted by redemption-rate descending. Color coding:
              ≥10% emerald (winning subjects), ≥3% amber, &lt;3% slate.
            </p>
          </TabsContent>

          {/* ── Recharts comparison ── */}
          <TabsContent value="chart" className="mt-3">
            <div
              className="rounded-md border border-slate-200 p-2"
              data-testid="coupon-analytics-chart-container"
            >
              {loading ? (
                <p className="text-xs text-slate-500 text-center py-6">Loading…</p>
              ) : chartData.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">
                  No campaign-attached coupons to chart yet.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 36)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis type="number" allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
                    <RechartsTooltip />
                    <Legend />
                    <Bar dataKey="minted"   fill="#60a5fa" name="Minted" />
                    <Bar dataKey="redeemed" fill="#10b981" name="Redeemed" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </TabsContent>

          {/* ── Timeline view ── */}
          <TabsContent value="timeline" className="mt-3">
            <div
              className="overflow-x-auto rounded-md border border-slate-200"
              data-testid="coupon-analytics-timeline"
            >
              {loading ? (
                <p className="text-xs text-slate-500 text-center py-6">Loading…</p>
              ) : rows.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">
                  No coupon timeline data yet.
                </p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-600 uppercase tracking-wide">
                    <tr>
                      <th className="text-left p-2">Campaign</th>
                      <th className="text-left p-2">First minted</th>
                      <th className="text-left p-2">Last minted</th>
                      <th className="text-right p-2">Window (h)</th>
                      <th className="text-right p-2">Redemption %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, idx) => (
                      <tr
                        key={r.campaign_id || `tl-${idx}`}
                        className="border-t border-slate-100"
                      >
                        <td className="p-2 font-semibold truncate max-w-[260px]">
                          {r.campaign_name}
                        </td>
                        <td className="p-2 font-mono text-slate-500">
                          {(r.first_minted || '—').slice(0, 16).replace('T', ' ')}
                        </td>
                        <td className="p-2 font-mono text-slate-500">
                          {(r.last_minted || '—').slice(0, 16).replace('T', ' ')}
                        </td>
                        <td className="text-right p-2 font-mono">
                          {hoursBetween(r.first_minted, r.last_minted) ?? '—'}
                        </td>
                        <td className="text-right p-2 font-bold text-emerald-700">
                          {r.redemption_rate_pct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};


const KpiCard = ({ testid, label, value, sub, icon, tone }) => (
  <div
    className={`rounded-lg border border-${tone}-200 bg-${tone}-50/60 p-3`}
    data-testid={testid}
  >
    <div className="flex items-center justify-between mb-1">
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      {icon}
    </div>
    <div className={`text-2xl font-bold text-${tone}-700`} data-testid={`${testid}-value`}>
      {fmt(value)}
    </div>
    <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>
  </div>
);

export default CouponAnalyticsTab;
