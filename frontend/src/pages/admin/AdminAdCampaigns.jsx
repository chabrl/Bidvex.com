/**
 * iter337 — Admin: Ad Campaigns
 *
 * Admin selects existing listings to feature in Google / Meta ad
 * campaigns. Gemini generates bilingual (EN + FR) headline (≤40) +
 * description (≤90) per listing. Admin reviews / edits, marks ready,
 * and exports a Google Merchant / Meta Catalog-compatible CSV feed.
 *
 * Directive 3 scope: build the DATA LAYER + copy generation. Actual
 * publish-to-Meta / publish-to-Google Ads is a manual CSV upload by
 * the BidVex team — the export CSV column names are canonical (id,
 * title, description, link, image_link, availability, condition,
 * price, brand, custom_label_0/1) so both platforms ingest cleanly.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Megaphone, Loader2, RefreshCw, Sparkles, ExternalLink, X, Save,
  CheckCircle2, Download, Plus, Trash2, PenLine,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';

const HEADLINE_MAX = 40;
const DESCRIPTION_MAX = 90;

const STATUS_BADGE_CLASSES = {
  draft:     'bg-slate-100 text-slate-800 border-slate-300',
  ready:     'bg-emerald-100 text-emerald-800 border-emerald-300',
  published: 'bg-blue-100 text-blue-800 border-blue-300',
};

export default function AdminAdCampaigns() {
  const { token } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPlatform, setFilterPlatform] = useState('');
  const [creating, setCreating] = useState(false);
  const [newListingIds, setNewListingIds] = useState('');
  const [newPlatform, setNewPlatform] = useState('both');
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({});

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const q = new URLSearchParams();
      if (filterStatus)   q.append('status', filterStatus);
      if (filterPlatform) q.append('platform', filterPlatform);
      const r = await axios.get(`${API_BASE}/admin/ad-campaigns?${q.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCampaigns(r.data?.items || []);
    } catch (e) {
      toast.error(`Failed to load campaigns: ${e?.response?.data?.detail || e?.message}`);
    } finally { setLoading(false); }
  }, [token, filterStatus, filterPlatform]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    const ids = newListingIds.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    if (ids.length === 0) {
      toast.error('Enter at least one listing ID.');
      return;
    }
    setCreating(true);
    try {
      const r = await axios.post(
        `${API_BASE}/admin/ad-campaigns`,
        { listing_ids: ids, platform: newPlatform },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const created = r.data?.total_created || 0;
      const skipped = (r.data?.skipped || []).length;
      toast.success(`Created ${created} draft${created !== 1 ? 's' : ''}${skipped > 0 ? ` (${skipped} skipped)` : ''}`);
      if (skipped > 0) {
        (r.data?.skipped || []).slice(0, 5).forEach((s) => {
          toast.warning(`Skipped ${s.listing_id}: ${s.reason}`);
        });
      }
      setNewListingIds('');
      await load();
    } catch (e) {
      toast.error(`Create failed: ${e?.response?.data?.detail || e?.message}`);
    } finally { setCreating(false); }
  };

  const handleRegenerate = async (c) => {
    try {
      const r = await axios.post(
        `${API_BASE}/admin/ad-campaigns/${c.id}/regenerate`, {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setCampaigns((prev) => prev.map((x) => (x.id === c.id ? r.data : x)));
      toast.success('Regenerated');
    } catch (e) {
      const st = e?.response?.status;
      if (st === 429) {
        toast.error('Max regenerations reached (3).');
      } else {
        toast.error(`Regenerate failed: ${e?.response?.data?.detail || e?.message}`);
      }
    }
  };

  const startEdit = (c) => {
    setEditingId(c.id);
    setEditDraft({
      headline_en:    c.headline_en || '',
      headline_fr:    c.headline_fr || '',
      description_en: c.description_en || '',
      description_fr: c.description_fr || '',
    });
  };

  const saveEdit = async (c) => {
    try {
      const r = await axios.patch(
        `${API_BASE}/admin/ad-campaigns/${c.id}`,
        editDraft,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setCampaigns((prev) => prev.map((x) => (x.id === c.id ? r.data : x)));
      setEditingId(null);
      toast.success('Saved');
    } catch (e) {
      toast.error(`Save failed: ${e?.response?.data?.detail || e?.message}`);
    }
  };

  const flipStatus = async (c, nextStatus) => {
    try {
      const r = await axios.patch(
        `${API_BASE}/admin/ad-campaigns/${c.id}`,
        { status: nextStatus },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setCampaigns((prev) => prev.map((x) => (x.id === c.id ? r.data : x)));
      toast.success(`Marked ${nextStatus}`);
    } catch (e) {
      toast.error(`Update failed: ${e?.response?.data?.detail || e?.message}`);
    }
  };

  const handleDelete = async (c) => {
    if (!window.confirm(`Delete campaign for listing ${c.listing_id}?`)) return;
    try {
      await axios.delete(`${API_BASE}/admin/ad-campaigns/${c.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCampaigns((prev) => prev.filter((x) => x.id !== c.id));
      toast.success('Deleted');
    } catch (e) {
      toast.error(`Delete failed: ${e?.response?.data?.detail || e?.message}`);
    }
  };

  const downloadCsv = (platform) => {
    const url = `${API_BASE}/admin/ad-campaigns/export.csv?platform=${platform}&status=ready`;
    // Fetch with auth header, then trigger download.
    axios.get(url, { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' })
      .then((r) => {
        const blobUrl = URL.createObjectURL(new Blob([r.data], { type: 'text/csv' }));
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `bidvex-ad-campaigns-${platform}-${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(blobUrl);
      })
      .catch((e) => toast.error(`Export failed: ${e?.response?.data?.detail || e?.message}`));
  };

  return (
    <div className="space-y-4" data-testid="admin-ad-campaigns">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Megaphone className="h-6 w-6 text-purple-600" />
            Ad Campaigns
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            AI-generated bilingual ad copy per listing. Google Merchant & Meta Catalog-ready CSV export.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline" size="sm"
            onClick={() => downloadCsv('google')}
            data-testid="export-google-csv-btn"
          >
            <Download className="h-4 w-4 mr-1" /> Google CSV
          </Button>
          <Button
            variant="outline" size="sm"
            onClick={() => downloadCsv('meta')}
            data-testid="export-meta-csv-btn"
          >
            <Download className="h-4 w-4 mr-1" /> Meta CSV
          </Button>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="ad-campaigns-refresh-btn">
            {loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
            Refresh
          </Button>
        </div>
      </div>

      {/* Create form */}
      <Card data-testid="ad-campaigns-create-card">
        <CardContent className="p-3 space-y-2">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Plus className="h-4 w-4" /> Create campaigns from listing IDs
          </h3>
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex-1 min-w-[260px]">
              <Label htmlFor="ad-listing-ids" className="text-xs">Listing IDs (comma or space separated)</Label>
              <Input
                id="ad-listing-ids"
                data-testid="ad-new-listing-ids"
                value={newListingIds}
                onChange={(e) => setNewListingIds(e.target.value)}
                placeholder="listing-id-1, listing-id-2, ..."
              />
            </div>
            <div>
              <Label htmlFor="ad-platform" className="text-xs">Platform</Label>
              <select
                id="ad-platform"
                data-testid="ad-new-platform"
                value={newPlatform}
                onChange={(e) => setNewPlatform(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-2 text-sm block"
              >
                <option value="both">Both (Google + Meta)</option>
                <option value="google">Google</option>
                <option value="meta">Meta</option>
              </select>
            </div>
            <Button
              onClick={handleCreate}
              disabled={creating || !newListingIds.trim()}
              className="bg-purple-600 hover:bg-purple-700 text-white"
              data-testid="ad-create-btn"
            >
              {creating ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Sparkles className="h-4 w-4 mr-1" />}
              Generate with AI
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardContent className="p-3 flex flex-wrap gap-2">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            data-testid="ad-filter-status"
          >
            <option value="">Any status</option>
            <option value="draft">Draft</option>
            <option value="ready">Ready</option>
            <option value="published">Published</option>
          </select>
          <select
            value={filterPlatform}
            onChange={(e) => setFilterPlatform(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            data-testid="ad-filter-platform"
          >
            <option value="">Any platform</option>
            <option value="google">Google</option>
            <option value="meta">Meta</option>
            <option value="both">Both</option>
          </select>
        </CardContent>
      </Card>

      {/* Campaigns list */}
      {loading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading…</div>
      ) : campaigns.length === 0 ? (
        <Card data-testid="ad-campaigns-empty">
          <CardContent className="p-8 text-center text-slate-500">
            <Megaphone className="h-10 w-10 mx-auto mb-3 text-slate-400" />
            <p>No ad campaigns yet — enter listing IDs above and click &quot;Generate with AI&quot;.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {campaigns.map((c) => (
            <Card key={c.id} className="border-slate-200" data-testid={`ad-card-${c.id}`}>
              <CardContent className="p-3 space-y-2">
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] font-mono text-slate-400 truncate">{c.listing_id}</p>
                    <div className="flex gap-1 flex-wrap mt-1">
                      <Badge className={STATUS_BADGE_CLASSES[c.status] || 'bg-slate-200'}>{c.status}</Badge>
                      <Badge variant="outline" className="text-[10px]">{c.platform}</Badge>
                      <Badge variant="outline" className="text-[10px]">{c.listing_type}</Badge>
                      {c.used_fallback && (
                        <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-[10px]">fallback</Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {editingId === c.id ? (
                      <>
                        <Button size="sm" variant="outline" onClick={() => setEditingId(null)} data-testid={`ad-cancel-edit-${c.id}`}>
                          <X className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => saveEdit(c)} data-testid={`ad-save-edit-${c.id}`}>
                          <Save className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button size="sm" variant="outline" onClick={() => startEdit(c)} data-testid={`ad-edit-btn-${c.id}`}>
                          <PenLine className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleRegenerate(c)} disabled={(c.regenerated_count || 0) >= 3} data-testid={`ad-regenerate-btn-${c.id}`}>
                          <Sparkles className="h-3.5 w-3.5" />
                        </Button>
                        {c.status === 'draft' && (
                          <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => flipStatus(c, 'ready')} data-testid={`ad-mark-ready-btn-${c.id}`}>
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button size="sm" variant="outline" onClick={() => handleDelete(c)} data-testid={`ad-delete-btn-${c.id}`}>
                          <Trash2 className="h-3.5 w-3.5 text-rose-600" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {editingId === c.id ? (
                  <div className="space-y-2">
                    <div>
                      <Label className="text-[10px]">Headline EN ({(editDraft.headline_en || '').length}/{HEADLINE_MAX})</Label>
                      <Input
                        value={editDraft.headline_en}
                        onChange={(e) => setEditDraft({ ...editDraft, headline_en: e.target.value.slice(0, HEADLINE_MAX) })}
                        data-testid={`ad-edit-headline-en-${c.id}`}
                        className="text-xs h-8"
                      />
                    </div>
                    <div>
                      <Label className="text-[10px]">Headline FR ({(editDraft.headline_fr || '').length}/{HEADLINE_MAX})</Label>
                      <Input
                        value={editDraft.headline_fr}
                        onChange={(e) => setEditDraft({ ...editDraft, headline_fr: e.target.value.slice(0, HEADLINE_MAX) })}
                        data-testid={`ad-edit-headline-fr-${c.id}`}
                        className="text-xs h-8"
                      />
                    </div>
                    <div>
                      <Label className="text-[10px]">Description EN ({(editDraft.description_en || '').length}/{DESCRIPTION_MAX})</Label>
                      <Textarea
                        value={editDraft.description_en}
                        onChange={(e) => setEditDraft({ ...editDraft, description_en: e.target.value.slice(0, DESCRIPTION_MAX) })}
                        data-testid={`ad-edit-desc-en-${c.id}`}
                        className="text-xs"
                        rows={2}
                      />
                    </div>
                    <div>
                      <Label className="text-[10px]">Description FR ({(editDraft.description_fr || '').length}/{DESCRIPTION_MAX})</Label>
                      <Textarea
                        value={editDraft.description_fr}
                        onChange={(e) => setEditDraft({ ...editDraft, description_fr: e.target.value.slice(0, DESCRIPTION_MAX) })}
                        data-testid={`ad-edit-desc-fr-${c.id}`}
                        className="text-xs"
                        rows={2}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="text-xs space-y-1">
                    <p><span className="text-slate-500 font-medium">EN Headline:</span> <span className="text-slate-900">{c.headline_en}</span></p>
                    <p><span className="text-slate-500 font-medium">EN Description:</span> <span className="text-slate-700">{c.description_en}</span></p>
                    <p><span className="text-slate-500 font-medium">FR Headline:</span> <span className="text-slate-900">{c.headline_fr}</span></p>
                    <p><span className="text-slate-500 font-medium">FR Description:</span> <span className="text-slate-700">{c.description_fr}</span></p>
                    <p className="pt-1 flex items-center gap-1 text-[10px] text-slate-400">
                      <ExternalLink className="h-3 w-3" />
                      <a href={c.landing_url} target="_blank" rel="noreferrer" className="hover:underline truncate">{c.landing_url}</a>
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
