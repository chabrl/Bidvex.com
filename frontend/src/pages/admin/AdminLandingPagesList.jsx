/**
 * iter374 — Admin Landing Pages List
 *
 * List view for landing pages built by admin. Shows slug, title, status,
 * views, updated date. Provides Edit / Preview / Publish / Duplicate /
 * Archive actions and a "+ New Page" button that opens the editor at
 * `/admin/landing-pages/new`.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plus, Search, RefreshCw, ExternalLink, Pencil, Copy, Archive,
  Send, Ban, Eye, ArrowLeft,
} from 'lucide-react';
import API_BASE from '../../config';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';

const STATUS_META = {
  draft:     { label: 'Draft',     cls: 'bg-slate-100 text-slate-700 border-slate-200' },
  published: { label: 'Published', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  archived:  { label: 'Archived',  cls: 'bg-orange-100 text-orange-800 border-orange-200' },
};

const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

const publicBase = () => (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

export default function AdminLandingPagesList() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const authHeaders = useMemo(() => ({
    Authorization: `Bearer ${_token()}`,
  }), []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (q.trim()) params.q = q.trim();
      const res = await axios.get(`${API_BASE}/admin/landing-pages`, {
        headers: authHeaders,
        params,
      });
      setItems(res.data?.items || []);
      setTotal(res.data?.total || 0);
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Failed to load landing pages';
      toast.error(typeof msg === 'string' ? msg : 'Failed to load landing pages');
      setItems([]); setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [authHeaders, page, statusFilter, q]);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (id, action) => {
    try {
      let res;
      if (action === 'delete') {
        res = await axios.delete(`${API_BASE}/admin/landing-pages/${id}`, { headers: authHeaders });
      } else {
        res = await axios.post(`${API_BASE}/admin/landing-pages/${id}/${action}`, {}, { headers: authHeaders });
      }
      if (res?.data) {
        const labels = {
          publish: 'Published',
          unpublish: 'Moved to draft',
          duplicate: 'Duplicated',
          delete: 'Archived',
        };
        toast.success(labels[action] || 'Done');
        load();
      }
    } catch (err) {
      const msg = err?.response?.data?.detail?.message_en
                || err?.response?.data?.detail
                || `Failed to ${action}`;
      toast.error(typeof msg === 'string' ? msg : `Failed to ${action}`);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="min-h-screen bg-slate-50" data-testid="admin-landing-pages-list">
      {/* Header */}
      <div className="border-b bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 lg:px-6 py-4 flex flex-wrap items-center gap-3">
          <Button
            variant="ghost"
            onClick={() => navigate('/admin')}
            className="text-slate-600 hover:text-slate-900"
            data-testid="lp-back-to-admin"
          >
            <ArrowLeft className="h-4 w-4 mr-1" /> Admin
          </Button>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-slate-900 truncate">Landing Pages</h1>
            <p className="text-sm text-slate-500">
              Create and publish SEO landing pages under <code className="bg-slate-100 px-1 rounded">/lp/&#123;slug&#125;</code> without a deploy.
            </p>
          </div>
          <Button
            onClick={() => navigate('/admin/landing-pages/new')}
            className="bg-primary text-white"
            data-testid="lp-new-page-btn"
          >
            <Plus className="h-4 w-4 mr-1" /> New page
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-4">
        <Card>
          <CardContent className="py-4 flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search slug or title…"
                value={q}
                onChange={(e) => { setPage(1); setQ(e.target.value); }}
                className="pl-9"
                data-testid="lp-search-input"
              />
            </div>
            <Select
              value={statusFilter}
              onValueChange={(v) => { setPage(1); setStatusFilter(v); }}
            >
              <SelectTrigger className="w-[180px]" data-testid="lp-status-filter">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="published">Published</SelectItem>
                <SelectItem value="archived">Archived</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={load} disabled={loading} data-testid="lp-refresh-btn">
              <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </CardContent>
        </Card>

        {/* Table */}
        <Card className="mt-4">
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm" data-testid="lp-table">
              <thead className="bg-slate-50 border-b text-slate-600">
                <tr>
                  <th className="text-left py-3 px-4 font-semibold">Slug / Title</th>
                  <th className="text-left py-3 px-4 font-semibold">Status</th>
                  <th className="text-right py-3 px-4 font-semibold">Views</th>
                  <th className="text-left py-3 px-4 font-semibold">Updated</th>
                  <th className="text-right py-3 px-4 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr><td colSpan={5} className="text-center py-10 text-slate-500">Loading…</td></tr>
                )}
                {!loading && items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center py-16">
                      <div className="text-slate-500">No landing pages yet.</div>
                      <Button
                        onClick={() => navigate('/admin/landing-pages/new')}
                        className="mt-3 bg-primary text-white"
                        data-testid="lp-empty-new-btn"
                      >
                        <Plus className="h-4 w-4 mr-1" /> Create your first page
                      </Button>
                    </td>
                  </tr>
                )}
                {!loading && items.map((row) => {
                  const meta = STATUS_META[row.status] || STATUS_META.draft;
                  const views = row.analytics?.total_views ?? row.view_count ?? 0;
                  return (
                    <tr
                      key={row.id}
                      className="border-b hover:bg-slate-50/70"
                      data-testid={`lp-row-${row.slug}`}
                    >
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 truncate max-w-[360px]">
                          {row.title_en || <span className="text-slate-400 italic">(untitled)</span>}
                        </div>
                        <div className="text-xs text-slate-500 font-mono">/lp/{row.slug}</div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge className={`border ${meta.cls}`}>{meta.label}</Badge>
                      </td>
                      <td className="py-3 px-4 text-right tabular-nums">{views}</td>
                      <td className="py-3 px-4 text-slate-600">{fmtDate(row.updated_at)}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => navigate(`/admin/landing-pages/${row.id}`)}
                            data-testid={`lp-edit-${row.slug}`}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {row.status === 'published' ? (
                            <a
                              href={`${publicBase()}/api/lp/${row.slug}/render`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex"
                              data-testid={`lp-open-${row.slug}`}
                              title="Open public page"
                            >
                              <Button size="sm" variant="ghost">
                                <ExternalLink className="h-4 w-4" />
                              </Button>
                            </a>
                          ) : (
                            <a
                              href={`${publicBase()}/api/lp/${row.slug}/render`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex opacity-40 pointer-events-none"
                              aria-disabled
                              title="Preview available once published"
                            >
                              <Button size="sm" variant="ghost" disabled>
                                <Eye className="h-4 w-4" />
                              </Button>
                            </a>
                          )}
                          {row.status === 'published' ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleAction(row.id, 'unpublish')}
                              data-testid={`lp-unpublish-${row.slug}`}
                              title="Unpublish"
                            >
                              <Ban className="h-4 w-4 text-orange-600" />
                            </Button>
                          ) : row.status !== 'archived' ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleAction(row.id, 'publish')}
                              data-testid={`lp-publish-${row.slug}`}
                              title="Publish"
                            >
                              <Send className="h-4 w-4 text-emerald-600" />
                            </Button>
                          ) : null}
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleAction(row.id, 'duplicate')}
                            data-testid={`lp-duplicate-${row.slug}`}
                            title="Duplicate"
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          {row.status !== 'archived' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                if (window.confirm(`Archive "${row.slug}"? It won't be publicly accessible.`)) {
                                  handleAction(row.id, 'delete');
                                }
                              }}
                              data-testid={`lp-archive-${row.slug}`}
                              title="Archive"
                            >
                              <Archive className="h-4 w-4 text-rose-600" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Pagination */}
        {total > pageSize && (
          <div className="flex items-center justify-between mt-4 text-sm text-slate-600">
            <span>Page {page} of {totalPages} · {total} total</span>
            <div className="flex gap-2">
              <Button
                variant="outline" size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                data-testid="lp-page-prev"
              >Prev</Button>
              <Button
                variant="outline" size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                data-testid="lp-page-next"
              >Next</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
