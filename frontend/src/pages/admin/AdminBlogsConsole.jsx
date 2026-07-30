import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * iter331 — AdminBlogsConsole
 *
 * Full CRUD interface for /blogs Press articles inside the Admin Panel.
 * Lives under Admin → Team → Press / Blog. Calls:
 *   GET    /api/admin/blogs/articles
 *   POST   /api/admin/blogs/articles
 *   PATCH  /api/admin/blogs/articles/{id}
 *   DELETE /api/admin/blogs/articles/{id}
 *   POST   /api/admin/blogs/articles/{id}/publish
 *   POST   /api/admin/blogs/articles/{id}/unpublish
 *   POST   /api/admin/blogs/articles/cover-upload   (multipart S3)
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plus, Edit3, Trash2, Eye, EyeOff, Loader2, Upload, X, Save,
  Newspaper, ExternalLink, ImageIcon,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../components/ui/dialog';

const TAG_OPTIONS = [
  'platform', 'compliance', 'storage', 'vehicles', 'partners', 'security',
  'marketing', 'company', 'product',
];

const ICON_OPTIONS = [
  'BookOpen', 'Gavel', 'ShieldCheck', 'Warehouse', 'Truck', 'Sparkles',
  'Newspaper', 'FileText',
];

const EMPTY_FORM = {
  id: null,
  slug: '',
  tag: 'platform',
  icon: 'BookOpen',
  title_en: '',
  title_fr: '',
  excerpt_en: '',
  excerpt_fr: '',
  body_en: '',
  body_fr: '',
  cover_url: '',
  read_min: 5,
  published: false,
};

export default function AdminBlogsConsole() {
  const { token } = useAuth();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editorOpen, setEditorOpen] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [coverUploading, setCoverUploading] = useState(false);
  const [deleteId, setDeleteId] = useState(null);

  const fetchArticles = useCallback(async () => {
    if (!token) return;
    try {
      const r = await axios.get(`${API_BASE}/admin/blogs/articles?include_drafts=true`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setArticles(r.data?.articles || []);
    } catch (e) {
      toast.error(`Failed to load articles: ${extractErrorMessage(e) || e?.message}`);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchArticles(); }, [fetchArticles]);

  const openNew = () => {
    setForm({ ...EMPTY_FORM });
    setEditorOpen(true);
  };

  const openEdit = (article) => {
    setForm({
      id: article.id,
      slug: article.slug || '',
      tag: article.tag || 'platform',
      icon: article.icon || 'BookOpen',
      title_en: article.title_en || '',
      title_fr: article.title_fr || '',
      excerpt_en: article.excerpt_en || '',
      excerpt_fr: article.excerpt_fr || '',
      body_en: article.body_en || '',
      body_fr: article.body_fr || '',
      cover_url: article.cover_url || '',
      read_min: article.read_min || 5,
      published: !!article.published,
    });
    setEditorOpen(true);
  };

  const handleCoverUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCoverUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await axios.post(`${API_BASE}/admin/blogs/articles/cover-upload`, fd, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      if (r.data?.cover_url) {
        setForm((f) => ({ ...f, cover_url: r.data.cover_url }));
        toast.success('Cover uploaded.');
      }
    } catch (err) {
      toast.error(`Upload failed: ${extractErrorMessage(err) || err?.message}`);
    } finally {
      setCoverUploading(false);
      e.target.value = '';  // reset input so re-uploading the same file works
    }
  };

  const validate = () => {
    if (!form.title_en || form.title_en.length < 3) return 'Title (EN) must be at least 3 chars';
    if (!form.title_fr || form.title_fr.length < 3) return 'Title (FR) must be at least 3 chars';
    if (!form.excerpt_en || form.excerpt_en.length < 10) return 'Excerpt (EN) must be at least 10 chars';
    if (!form.excerpt_fr || form.excerpt_fr.length < 10) return 'Excerpt (FR) must be at least 10 chars';
    if (!form.body_en || form.body_en.length < 10) return 'Body (EN) must be at least 10 chars';
    if (!form.body_fr || form.body_fr.length < 10) return 'Body (FR) must be at least 10 chars';
    return null;
  };

  const saveArticle = async () => {
    const err = validate();
    if (err) { toast.error(err); return; }
    setSaving(true);
    try {
      const payload = {
        slug: form.slug || undefined,
        tag: form.tag,
        icon: form.icon,
        title_en: form.title_en,
        title_fr: form.title_fr,
        excerpt_en: form.excerpt_en,
        excerpt_fr: form.excerpt_fr,
        body_en: form.body_en,
        body_fr: form.body_fr,
        cover_url: form.cover_url || null,
        read_min: parseInt(form.read_min, 10) || 5,
        published: form.published,
      };
      if (form.id) {
        await axios.patch(`${API_BASE}/admin/blogs/articles/${form.id}`, payload, {
          headers: { Authorization: `Bearer ${token}` },
        });
        toast.success('Article updated.');
      } else {
        await axios.post(`${API_BASE}/admin/blogs/articles`, payload, {
          headers: { Authorization: `Bearer ${token}` },
        });
        toast.success('Article created.');
      }
      setEditorOpen(false);
      await fetchArticles();
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message;
      toast.error(`Save failed: ${typeof msg === 'string' ? msg : JSON.stringify(msg)}`);
    } finally {
      setSaving(false);
    }
  };

  const togglePublish = async (article) => {
    const next = !article.published;
    try {
      await axios.post(
        `${API_BASE}/admin/blogs/articles/${article.id}/${next ? 'publish' : 'unpublish'}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(next ? 'Published.' : 'Unpublished.');
      await fetchArticles();
    } catch (e) {
      toast.error(`Toggle failed: ${extractErrorMessage(e) || e?.message}`);
    }
  };

  const confirmDelete = async () => {
    if (!deleteId) return;
    try {
      await axios.delete(`${API_BASE}/admin/blogs/articles/${deleteId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success('Article deleted.');
      setDeleteId(null);
      await fetchArticles();
    } catch (e) {
      toast.error(`Delete failed: ${extractErrorMessage(e) || e?.message}`);
    }
  };

  return (
    <div className="space-y-4" data-testid="admin-blogs-console">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Newspaper className="h-6 w-6 text-indigo-600" />
            Press / Blog Manager
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Full CRUD for /blogs articles. Markdown-supported body.
          </p>
        </div>
        <Button
          onClick={openNew}
          className="bg-indigo-600 hover:bg-indigo-700 text-white"
          data-testid="admin-blogs-new-btn"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Article
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span>Loading…</span>
        </div>
      ) : articles.length === 0 ? (
        <Card data-testid="admin-blogs-empty">
          <CardContent className="p-8 text-center text-slate-500">
            <Newspaper className="w-10 h-10 mx-auto mb-3 text-slate-400" />
            <p>No articles yet. Click &quot;New Article&quot; to create one.</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="admin-blogs-table">
                <thead className="bg-slate-50">
                  <tr className="text-xs text-slate-500 text-left border-b">
                    <th className="px-4 py-3">Title (EN)</th>
                    <th className="px-4 py-3">Slug</th>
                    <th className="px-4 py-3">Tag</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Updated</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {articles.map((a) => (
                    <tr key={a.id} className="border-b last:border-b-0" data-testid={`admin-blogs-row-${a.slug}`}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900 max-w-md truncate">{a.title_en}</div>
                        <div className="text-xs text-slate-500 max-w-md truncate">{a.excerpt_en}</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600">{a.slug}</td>
                      <td className="px-4 py-3"><Badge variant="outline">{a.tag}</Badge></td>
                      <td className="px-4 py-3">
                        {a.published ? (
                          <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300">Published</Badge>
                        ) : (
                          <Badge className="bg-slate-100 text-slate-700">Draft</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">
                        {a.updated_at ? new Date(a.updated_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => togglePublish(a)}
                            data-testid={`admin-blogs-toggle-publish-${a.slug}`}
                            title={a.published ? 'Unpublish' : 'Publish'}
                          >
                            {a.published ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openEdit(a)}
                            data-testid={`admin-blogs-edit-${a.slug}`}
                          >
                            <Edit3 className="h-3.5 w-3.5" />
                          </Button>
                          {a.published && (
                            <a
                              href={`/blogs/${a.slug}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center justify-center px-2 py-1 border rounded text-xs hover:bg-slate-50"
                              data-testid={`admin-blogs-view-${a.slug}`}
                              title="View on site"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                            onClick={() => setDeleteId(a.id)}
                            data-testid={`admin-blogs-delete-${a.slug}`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Editor dialog */}
      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="admin-blogs-editor">
          <DialogHeader>
            <DialogTitle>{form.id ? 'Edit Article' : 'New Article'}</DialogTitle>
            <DialogDescription>
              Bilingual EN/FR. Body supports Markdown (## headings, **bold**, - lists, `code`).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-3">
            {/* Meta row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-semibold">Slug (optional — auto-generated from title)</label>
                <Input
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase() })}
                  placeholder="my-article-slug"
                  data-testid="admin-blogs-input-slug"
                />
              </div>
              <div>
                <label className="text-xs font-semibold">Tag</label>
                <select
                  value={form.tag}
                  onChange={(e) => setForm({ ...form, tag: e.target.value })}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                  data-testid="admin-blogs-input-tag"
                >
                  {TAG_OPTIONS.map((t) => (<option key={t} value={t}>{t}</option>))}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold">Icon</label>
                <select
                  value={form.icon}
                  onChange={(e) => setForm({ ...form, icon: e.target.value })}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                  data-testid="admin-blogs-input-icon"
                >
                  {ICON_OPTIONS.map((i) => (<option key={i} value={i}>{i}</option>))}
                </select>
              </div>
            </div>

            {/* Titles */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold">Title (EN) *</label>
                <Input
                  value={form.title_en}
                  onChange={(e) => setForm({ ...form, title_en: e.target.value })}
                  data-testid="admin-blogs-input-title-en"
                />
              </div>
              <div>
                <label className="text-xs font-semibold">Title (FR) *</label>
                <Input
                  value={form.title_fr}
                  onChange={(e) => setForm({ ...form, title_fr: e.target.value })}
                  data-testid="admin-blogs-input-title-fr"
                />
              </div>
            </div>

            {/* Excerpts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold">Excerpt (EN) *</label>
                <Textarea
                  rows={3}
                  value={form.excerpt_en}
                  onChange={(e) => setForm({ ...form, excerpt_en: e.target.value })}
                  data-testid="admin-blogs-input-excerpt-en"
                />
              </div>
              <div>
                <label className="text-xs font-semibold">Excerpt (FR) *</label>
                <Textarea
                  rows={3}
                  value={form.excerpt_fr}
                  onChange={(e) => setForm({ ...form, excerpt_fr: e.target.value })}
                  data-testid="admin-blogs-input-excerpt-fr"
                />
              </div>
            </div>

            {/* Bodies */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold">Body Markdown (EN) *</label>
                <Textarea
                  rows={14}
                  value={form.body_en}
                  onChange={(e) => setForm({ ...form, body_en: e.target.value })}
                  className="font-mono text-xs"
                  data-testid="admin-blogs-input-body-en"
                />
              </div>
              <div>
                <label className="text-xs font-semibold">Body Markdown (FR) *</label>
                <Textarea
                  rows={14}
                  value={form.body_fr}
                  onChange={(e) => setForm({ ...form, body_fr: e.target.value })}
                  className="font-mono text-xs"
                  data-testid="admin-blogs-input-body-fr"
                />
              </div>
            </div>

            {/* Cover + read time + publish */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <label className="text-xs font-semibold flex items-center gap-1">
                  <ImageIcon className="h-3 w-3" /> Cover image
                </label>
                <div className="flex gap-2 items-center">
                  <Input
                    value={form.cover_url}
                    onChange={(e) => setForm({ ...form, cover_url: e.target.value })}
                    placeholder="https://… or upload"
                    data-testid="admin-blogs-input-cover-url"
                  />
                  <label className="cursor-pointer inline-flex items-center gap-1 px-3 h-9 border rounded-md text-xs hover:bg-slate-50 whitespace-nowrap">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleCoverUpload}
                      className="hidden"
                      disabled={coverUploading}
                      data-testid="admin-blogs-cover-upload-input"
                    />
                    {coverUploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
                    {coverUploading ? 'Uploading…' : 'Upload'}
                  </label>
                </div>
                {form.cover_url && (
                  <img src={form.cover_url} alt="cover" className="mt-2 h-20 rounded border" data-testid="admin-blogs-cover-preview" />
                )}
              </div>
              <div>
                <label className="text-xs font-semibold">Read time (min)</label>
                <Input
                  type="number"
                  min="1"
                  max="60"
                  value={form.read_min}
                  onChange={(e) => setForm({ ...form, read_min: e.target.value })}
                  data-testid="admin-blogs-input-read-min"
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.published}
                onChange={(e) => setForm({ ...form, published: e.target.checked })}
                data-testid="admin-blogs-input-published"
              />
              Publish immediately (visible on /blogs)
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorOpen(false)} disabled={saving} data-testid="admin-blogs-cancel-btn">
              <X className="h-4 w-4 mr-1" /> Cancel
            </Button>
            <Button
              onClick={saveArticle}
              disabled={saving}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              data-testid="admin-blogs-save-btn"
            >
              {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
              {form.id ? 'Save' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <DialogContent data-testid="admin-blogs-delete-confirm">
          <DialogHeader>
            <DialogTitle>Delete article?</DialogTitle>
            <DialogDescription>
              This is permanent and removes the row from the database. Consider unpublishing instead if you might restore it later.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)} data-testid="admin-blogs-delete-cancel-btn">Cancel</Button>
            <Button
              className="bg-rose-600 hover:bg-rose-700 text-white"
              onClick={confirmDelete}
              data-testid="admin-blogs-delete-confirm-btn"
            >
              <Trash2 className="h-4 w-4 mr-1" /> Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
