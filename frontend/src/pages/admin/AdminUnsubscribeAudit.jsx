/**
 * iter310 — Admin Unsubscribe Audit
 *
 * Surfaces the `unsubscribe_events` collection so admins can spot
 * deliverability spikes before they tank sender reputation.
 *
 * Endpoints:
 *   GET /api/admin/unsubscribe-audit/summary    — daily counts + facets
 *   GET /api/admin/unsubscribe-audit            — paginated rows
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const authHeaders = () => {
  const tok = localStorage.getItem('access_token') || localStorage.getItem('token') || '';
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const SourceBadge = ({ source }) => {
  const isPlatform = source === 'platform';
  return (
    <Badge
      className={isPlatform ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}
      data-testid={`unsub-source-${source}`}
    >
      {isPlatform ? 'Platform' : 'External campaign'}
    </Badge>
  );
};

const Sparkline = ({ data }) => {
  if (!Array.isArray(data) || data.length < 2) return null;
  const counts = data.map((d) => d.count);
  const max = Math.max(1, ...counts);
  return (
    <div className="flex items-end gap-0.5 h-8" aria-label="daily unsubscribe trend">
      {data.map((d) => (
        <div
          key={d.date}
          title={`${d.date}: ${d.count}`}
          className="bg-rose-400/80 rounded-sm w-2"
          style={{ height: `${Math.max(6, (d.count / max) * 100)}%` }}
        />
      ))}
    </div>
  );
};

const AdminUnsubscribeAudit = () => {
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 50;
  const [filters, setFilters] = useState({ start_date: '', end_date: '', campaign_id: '', source: '' });
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const [s, l] = await Promise.all([
        axios.get(`${API}/admin/unsubscribe-audit/summary`, { headers: authHeaders() }),
        axios.get(`${API}/admin/unsubscribe-audit`, {
          headers: authHeaders(),
          params: {
            page,
            per_page: perPage,
            ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
          },
        }),
      ]);
      setSummary(s.data);
      setRows(l.data?.events || []);
      setTotal(l.data?.count || 0);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load audit data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // refresh intentionally excluded from deps to avoid loop
  }, [page]);

  const pages = useMemo(() => Math.max(1, Math.ceil(total / perPage)), [total]);

  return (
    <div className="space-y-4" data-testid="admin-unsubscribe-audit">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card data-testid="unsub-stat-today">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tabular-nums">{summary?.today ?? '—'}</div>
          </CardContent>
        </Card>
        <Card data-testid="unsub-stat-last7">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Last 7 days</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tabular-nums">{summary?.last_7 ?? '—'}</div>
          </CardContent>
        </Card>
        <Card data-testid="unsub-stat-last30">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Last 30 days</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tabular-nums">{summary?.last_30 ?? '—'}</div>
          </CardContent>
        </Card>
        <Card data-testid="unsub-stat-trend">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">30-day trend</CardTitle>
          </CardHeader>
          <CardContent>
            <Sparkline data={summary?.by_day || []} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
            <div>
              <Label className="text-xs">Start date</Label>
              <Input
                type="date"
                value={filters.start_date}
                onChange={(e) => setFilters({ ...filters, start_date: e.target.value })}
                data-testid="unsub-filter-start"
              />
            </div>
            <div>
              <Label className="text-xs">End date</Label>
              <Input
                type="date"
                value={filters.end_date}
                onChange={(e) => setFilters({ ...filters, end_date: e.target.value })}
                data-testid="unsub-filter-end"
              />
            </div>
            <div>
              <Label className="text-xs">Campaign ID</Label>
              <Input
                value={filters.campaign_id}
                onChange={(e) => setFilters({ ...filters, campaign_id: e.target.value })}
                placeholder="optional"
                data-testid="unsub-filter-campaign"
              />
            </div>
            <div>
              <Label className="text-xs">Source</Label>
              <select
                className="block w-full border border-slate-300 rounded-md text-sm py-2 px-2"
                value={filters.source}
                onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                data-testid="unsub-filter-source"
              >
                <option value="">Any</option>
                <option value="platform">Platform</option>
                <option value="external_campaign">External campaign</option>
              </select>
            </div>
            <Button
              onClick={() => { setPage(1); refresh(); }}
              disabled={loading}
              data-testid="unsub-filter-apply"
            >
              {loading ? 'Loading…' : 'Apply'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Audit Trail ({total})</CardTitle>
          <div className="text-xs text-muted-foreground">Page {page} of {pages}</div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="unsub-audit-table">
              <thead className="text-xs uppercase text-muted-foreground border-b">
                <tr>
                  <th className="text-left p-3">Timestamp</th>
                  <th className="text-left p-3">Email</th>
                  <th className="text-left p-3">Source</th>
                  <th className="text-left p-3">Campaign</th>
                  <th className="text-left p-3">Language</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center p-6 text-muted-foreground">
                      {loading ? 'Loading…' : 'No unsubscribe events yet.'}
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.id} className="border-b hover:bg-slate-50" data-testid={`unsub-row-${r.id}`}>
                      <td className="p-3 text-xs">{r.unsubscribed_at ? new Date(r.unsubscribed_at).toLocaleString() : '—'}</td>
                      <td className="p-3 font-mono text-xs">{r.email_masked}</td>
                      <td className="p-3"><SourceBadge source={r.source} /></td>
                      <td className="p-3 text-xs">
                        {r.campaign_name ? (
                          <span>{r.campaign_name}</span>
                        ) : r.campaign_id ? (
                          <span className="font-mono text-muted-foreground">{r.campaign_id.slice(0, 8)}…</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="p-3 uppercase text-xs">{r.lang || 'en'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-end gap-2 p-3 border-t">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              data-testid="unsub-page-prev"
            >
              Prev
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= pages || loading}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              data-testid="unsub-page-next"
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminUnsubscribeAudit;
