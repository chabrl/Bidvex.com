import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { TrendingDown, Eye, Gavel, Handshake, CheckCircle2, RefreshCw } from 'lucide-react';

const API = API_BASE;

/**
 * Phase 5.3 — Task 3
 * Admin Conversion-Rate Funnel Dashboard.
 *
 * Visualises the 4-stage marketplace funnel + drop-off percentages, with
 * a configurable time window (7 / 30 / 90 / 365 days / all-time).
 */

const STEP_ICONS = {
  views:           Eye,
  bids_proxies:    Gavel,
  binding_matches: Handshake,
  settled:         CheckCircle2,
};

const STEP_COLORS = ['#2186C6', '#3FB4CB', '#F59E0B', '#10B981'];

const fmt = (n) => (typeof n === 'number' ? n.toLocaleString() : '0');
const pct = (n) => (n === null || n === undefined ? '—' : `${n.toFixed(1)}%`);

const ConversionFunnelDashboard = () => {
  const { token } = useAuth();
  const [windowDays, setWindowDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/admin/analytics/conversion-funnel?days=${windowDays}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load funnel');
    } finally {
      setLoading(false);
    }
  }, [windowDays, token]);

  useEffect(() => { load(); }, [load]);

  const steps = data?.steps || [];
  const baseCount = steps[0]?.count || 0;

  return (
    <div className="space-y-6" data-testid="conversion-funnel-dashboard">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <TrendingDown className="h-6 w-6 text-cyan-600" /> Conversion Funnel
          </h2>
          <p className="text-muted-foreground text-sm">
            Marketplace funnel from auction views → settled transactions, with step-by-step drop-off math.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {[7, 30, 90, 365, 0].map((d) => (
            <Button
              key={d}
              size="sm"
              variant={windowDays === d ? 'default' : 'outline'}
              onClick={() => setWindowDays(d)}
              className={windowDays === d ? 'gradient-button text-white border-0' : ''}
              data-testid={`window-${d || 'all'}-btn`}
            >
              {d === 0 ? 'All-time' : `${d}d`}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={load} data-testid="refresh-funnel-btn">
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {typeof error === 'string' ? error : JSON.stringify(error)}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {steps.map((s, idx) => {
          const Icon = STEP_ICONS[s.key] || Eye;
          return (
            <Card key={s.key} data-testid={`funnel-step-${s.key}`} className="border-l-4" style={{ borderLeftColor: STEP_COLORS[idx] || '#64748B' }}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Icon className="h-4 w-4" style={{ color: STEP_COLORS[idx] }} />
                  Step {idx + 1}: {s.label_en}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="text-3xl font-bold" data-testid={`funnel-count-${s.key}`}>
                  {fmt(s.count)}
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {s.step_drop_off_pct !== null && (
                    <Badge
                      className={`text-xs ${s.step_drop_off_pct >= 70 ? 'bg-rose-100 text-rose-900 border border-rose-200' : s.step_drop_off_pct >= 40 ? 'bg-amber-100 text-amber-900 border border-amber-200' : 'bg-emerald-100 text-emerald-900 border border-emerald-200'}`}
                      data-testid={`funnel-dropoff-${s.key}`}
                    >
                      ↓ {pct(s.step_drop_off_pct)} drop-off
                    </Badge>
                  )}
                  <Badge variant="outline" className="text-xs" data-testid={`funnel-cumulative-${s.key}`}>
                    {pct(s.cumulative_conversion_pct)} of views
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{s.label_fr}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Horizontal funnel visual */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Funnel visualization</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-10">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-cyan-500 border-t-transparent"></div>
            </div>
          ) : steps.length === 0 ? (
            <p className="text-center text-muted-foreground py-8" data-testid="funnel-empty">
              No data yet for this window.
            </p>
          ) : (
            <div className="space-y-3" data-testid="funnel-bars">
              {steps.map((s, idx) => {
                const widthPct = baseCount > 0 ? Math.max(2, Math.round((s.count / baseCount) * 100)) : 2;
                return (
                  <div key={s.key} className="flex items-center gap-3">
                    <div className="w-44 text-sm font-medium flex-shrink-0">
                      {idx + 1}. {s.label_en}
                    </div>
                    <div className="flex-1 bg-slate-100 rounded-md h-9 relative overflow-hidden">
                      <div
                        className="h-full rounded-md transition-all duration-700 flex items-center px-3 text-white text-sm font-semibold"
                        style={{ width: `${widthPct}%`, background: STEP_COLORS[idx] || '#64748B' }}
                        data-testid={`funnel-bar-${s.key}`}
                      >
                        {fmt(s.count)}
                      </div>
                    </div>
                    <div className="w-24 text-right text-sm font-mono text-muted-foreground">
                      {pct(s.cumulative_conversion_pct)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Totals summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Summary</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div data-testid="summary-views">
            <p className="text-xs text-muted-foreground">Views</p>
            <p className="text-xl font-bold">{fmt(data?.totals?.views)}</p>
          </div>
          <div data-testid="summary-bids">
            <p className="text-xs text-muted-foreground">Bids + Proxies</p>
            <p className="text-xl font-bold">{fmt(data?.totals?.bids_proxies)}</p>
          </div>
          <div data-testid="summary-bindings">
            <p className="text-xs text-muted-foreground">Bindings Matched</p>
            <p className="text-xl font-bold">{fmt(data?.totals?.binding_matches)}</p>
          </div>
          <div data-testid="summary-settled">
            <p className="text-xs text-muted-foreground">Settled</p>
            <p className="text-xl font-bold">{fmt(data?.totals?.settled)}</p>
          </div>
          <div data-testid="summary-overall-pct">
            <p className="text-xs text-muted-foreground">Overall view → settled</p>
            <p className="text-xl font-bold text-cyan-700">{pct(data?.totals?.overall_conversion_pct)}</p>
          </div>
        </CardContent>
      </Card>

      {data?.generated_at && (
        <p className="text-[11px] text-muted-foreground text-right">
          Generated at {new Date(data.generated_at).toLocaleString()} · Window: {data.window_days ? `${data.window_days} days` : 'All-time'}
        </p>
      )}
    </div>
  );
};

export default ConversionFunnelDashboard;
