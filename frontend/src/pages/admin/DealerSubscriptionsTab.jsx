import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { RefreshCw, CheckCircle2, XCircle, AlertTriangle, ExternalLink, Search, CreditCard, Calendar, Building2 } from 'lucide-react';

const API = API_BASE;

/**
 * iter211 follow-up — Admin view of vehicle dealer subscriptions
 *
 * Surfaces: who is approved, who has paid the $100/yr annual fee, who is
 * pending payment, and who is suspended. Pulls from the new
 * GET /api/admin/dealer-subscriptions endpoint.
 */
const DealerSubscriptionsTab = () => {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({ total: 0, paid: 0, unpaid: 0, suspended: 0 });
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all'); // all | paid | unpaid | suspended

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/dealer-subscriptions`);
      setRows(r.data?.rows || []);
      setSummary(r.data?.summary || { total: 0, paid: 0, unpaid: 0, suspended: 0 });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Dealer subs fetch failed:', e);
      toast.error('Failed to load dealer subscriptions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = rows.filter(r => {
    if (filter === 'paid' && !(r.subscription_active && !r.subscription_suspended)) return false;
    if (filter === 'unpaid' && (r.subscription_active || r.subscription_suspended)) return false;
    if (filter === 'suspended' && !r.subscription_suspended) return false;
    if (query) {
      const q = query.toLowerCase();
      const hay = `${r.email || ''} ${r.full_name || ''} ${r.business_name || ''} ${r.license_province || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const fmtDate = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return iso;
    }
  };

  const statusBadge = (row) => {
    if (row.subscription_suspended) {
      return <Badge className="bg-rose-100 text-rose-900 border border-rose-300"><AlertTriangle className="w-3 h-3 mr-1" />Suspended</Badge>;
    }
    if (row.subscription_active) {
      return <Badge className="bg-emerald-100 text-emerald-900 border border-emerald-300"><CheckCircle2 className="w-3 h-3 mr-1" />Paid</Badge>;
    }
    return <Badge className="bg-amber-100 text-amber-900 border border-amber-300"><XCircle className="w-3 h-3 mr-1" />Unpaid</Badge>;
  };

  return (
    <div className="space-y-4" data-testid="dealer-subscriptions-tab">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs text-slate-500">Total Dealers</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold" data-testid="dealer-subs-total">{summary.total}</div></CardContent>
        </Card>
        <Card className="border-emerald-200">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-emerald-700">Paid ($100/yr)</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-emerald-700" data-testid="dealer-subs-paid">{summary.paid}</div></CardContent>
        </Card>
        <Card className="border-amber-200">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-amber-700">Unpaid</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-amber-700" data-testid="dealer-subs-unpaid">{summary.unpaid}</div></CardContent>
        </Card>
        <Card className="border-rose-200">
          <CardHeader className="pb-2"><CardTitle className="text-xs text-rose-700">Suspended</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-rose-700" data-testid="dealer-subs-suspended">{summary.suspended}</div></CardContent>
        </Card>
      </div>

      {/* Filter + Search */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search email, name, business…"
            className="pl-10"
            data-testid="dealer-subs-search"
          />
        </div>
        <div className="flex gap-1">
          {['all', 'paid', 'unpaid', 'suspended'].map(f => (
            <Button
              key={f}
              size="sm"
              variant={filter === f ? 'default' : 'outline'}
              onClick={() => setFilter(f)}
              data-testid={`dealer-subs-filter-${f}`}
              className="capitalize"
            >
              {f}
            </Button>
          ))}
        </div>
        <Button size="sm" variant="outline" onClick={fetchData} disabled={loading} data-testid="dealer-subs-refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-left">
                  <th className="px-4 py-3 font-medium text-slate-600">Dealer</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Province</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Approved</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Status</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Paid On</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Renews</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Stripe</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">Loading…</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500" data-testid="dealer-subs-empty">No dealers match the current filter.</td></tr>
                ) : filtered.map(r => (
                  <tr key={r.user_id} className="border-b border-slate-100 hover:bg-slate-50/50" data-testid={`dealer-subs-row-${r.user_id}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900 flex items-center gap-1.5">
                        {r.business_name && <Building2 className="w-3.5 h-3.5 text-slate-400" />}
                        {r.business_name || r.full_name || r.email}
                        {r.is_demo_account && (
                          <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300" title="Demo account">🎭 DEMO</span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500">{r.email}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{r.license_province || '—'}</td>
                    <td className="px-4 py-3 text-slate-700"><Calendar className="w-3 h-3 inline mr-1 text-slate-400" />{fmtDate(r.approved_at)}</td>
                    <td className="px-4 py-3">{statusBadge(r)}</td>
                    <td className="px-4 py-3 text-slate-700">{fmtDate(r.subscription_start)}</td>
                    <td className="px-4 py-3 text-slate-700">{fmtDate(r.subscription_renewal)}</td>
                    <td className="px-4 py-3">
                      {r.stripe_subscription_id ? (
                        <a
                          href={`https://dashboard.stripe.com/subscriptions/${r.stripe_subscription_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1"
                        >
                          <CreditCard className="w-3 h-3" />
                          {r.stripe_subscription_id.slice(0, 16)}…
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <p className="text-xs text-slate-500">
        Data live-queried from <code>/api/admin/dealer-subscriptions</code>. Updates on next checkout webhook fire.
      </p>
    </div>
  );
};

export default DealerSubscriptionsTab;
export { DealerSubscriptionsTab };
