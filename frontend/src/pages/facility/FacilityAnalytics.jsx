/**
 * BidVex — Phase 6.2 Task 6C
 * Analytics tab — 6 metric cards + revenue chart + status donut + top-units.
 *
 * Backend: GET /api/facility/analytics?range=30d (cached 5 min server-side).
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';

import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const RANGES = [
  { key: '7d',  label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: '90d', label: 'Last 90 days' },
  { key: 'all', label: 'All time' },
];

const fmtMoney = (v) => `$${Number(v || 0).toLocaleString('en-CA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

export default function FacilityAnalytics() {
  const [range, setRange] = useState('30d');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const token = window.localStorage.getItem('token');
      const res = await axios.get(`${API}/api/facility/analytics?range=${range}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setData(res.data);
    } catch (e) {
      console.error('[FacilityAnalytics] load failed', e);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const m = data?.metrics || {};
  const charts = data?.charts || {};

  // Compute scale for revenue chart bars
  const revenue = charts.revenue_over_time || [];
  const maxRevenue = Math.max(...revenue.map((p) => p.revenue || 0), 1);

  return (
    <Card data-testid="facility-analytics-card">
      <CardHeader>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <CardTitle>Facility Analytics</CardTitle>
          <div className="flex flex-wrap gap-1.5" data-testid="facility-analytics-range">
            {RANGES.map((r) => (
              <button
                type="button"
                key={r.key}
                onClick={() => setRange(r.key)}
                data-testid={`facility-range-${r.key}`}
                className={`rounded-full border px-3 py-1 text-xs font-medium ${
                  range === r.key
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-700 border-slate-200'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="text-center py-12"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></div>
        )}

        {!loading && data && (
          <div className="space-y-6">
            {/* Metric cards */}
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3" data-testid="facility-metric-cards">
              <Metric label="Total Revenue" value={fmtMoney(m.total_revenue)} suffix="CAD" testId="metric-revenue" />
              <Metric label="Total Auctions" value={m.completed_auctions ?? 0} suffix="completed" testId="metric-auctions" />
              <Metric label="Avg Hammer Price" value={fmtMoney(m.avg_hammer_price)} suffix="CAD" testId="metric-avg-hammer" />
              <Metric label="Total Bids" value={m.total_bids ?? 0} suffix="received" testId="metric-bids" />
              <Metric label="Avg Bids / Unit" value={Number(m.avg_bids_per_unit || 0).toFixed(1)} testId="metric-bids-per-unit" />
              <Metric label="Deposit Forfeited" value={m.deposit_forfeited ?? 0} suffix="cases" testId="metric-forfeited" />
            </div>

            {/* Revenue over time — simple CSS bar chart */}
            <div>
              <h3 className="text-sm font-semibold mb-2">Revenue over time</h3>
              {revenue.length === 0 ? (
                <div className="text-xs text-muted-foreground py-4">No revenue in this date range.</div>
              ) : (
                <div className="flex items-end gap-1 h-32 border-l border-b pl-2 pb-1" data-testid="revenue-chart">
                  {revenue.map((p) => (
                    <div
                      key={p.bucket}
                      title={`${p.bucket}: ${fmtMoney(p.revenue)}`}
                      className="flex flex-col items-center justify-end flex-1 min-w-[20px]"
                    >
                      <div
                        className="w-full bg-emerald-500 rounded-t"
                        style={{ height: `${(p.revenue / maxRevenue) * 100}%`, minHeight: '2px' }}
                      />
                      <div className="text-[9px] text-muted-foreground mt-1 truncate w-full text-center">
                        {p.bucket}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Status donut — text-only summary (visual donut needs chart lib) */}
            <div>
              <h3 className="text-sm font-semibold mb-2">Auctions by status</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs" data-testid="status-donut">
                {Object.entries(charts.status_donut || {}).map(([k, v]) => (
                  <div key={k} className="border rounded px-2 py-1 flex justify-between">
                    <span className="capitalize">{k}</span>
                    <span className="font-semibold tabular-nums">{v}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Top units */}
            <div>
              <h3 className="text-sm font-semibold mb-2">Top 5 units by hammer price</h3>
              {(charts.top_units || []).length === 0 ? (
                <div className="text-xs text-muted-foreground py-2">No completed auctions yet.</div>
              ) : (
                <ol className="space-y-1 text-sm" data-testid="top-units-list">
                  {(charts.top_units || []).map((u, idx) => (
                    <li key={u.id} className="flex items-center justify-between border-b py-1">
                      <span className="truncate flex-1 mr-2">#{idx + 1} {u.title}</span>
                      <span className="font-semibold tabular-nums whitespace-nowrap">{fmtMoney(u.hammer)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            {data.cached_at && (
              <p className="text-[10px] text-muted-foreground">
                Data cached at {new Date(data.cached_at).toLocaleTimeString()} (refreshes every 5 min)
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value, suffix, testId }) {
  return (
    <div className="border rounded-lg p-3" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">{label}</div>
      <div className="text-2xl font-bold tabular-nums mt-0.5">{value}</div>
      {suffix && <div className="text-[10px] text-muted-foreground">{suffix}</div>}
    </div>
  );
}
