/**
 * iter374 — Admin Landing Page Editor.
 *
 * Three-tab editor:
 *   1. Settings — slug, EN/FR titles/meta, OG image, header/footer toggles, status
 *   2. HTML Editor — EN HTML, FR HTML, CSS, JS (textarea + monospace + Tab→spaces)
 *   3. Preview — iframe against /api/lp/{slug}/render + device + language toggles.
 *
 * Loads existing page when :id present, otherwise creates a new draft on
 * first save. Warns the user on unsaved changes (via beforeunload + local
 * dirty flag).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ArrowLeft, Save, Send, Ban, RefreshCw, Monitor, Tablet, Smartphone,
  ExternalLink, Loader2, AlertCircle, Copy,
} from 'lucide-react';
import API_BASE from '../../config';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { Textarea } from '../../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';

const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

const publicBase = () => (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

const DEFAULT_STATE = {
  slug: '',
  title_en: '',
  title_fr: '',
  meta_description_en: '',
  meta_description_fr: '',
  html_en: '',
  html_fr: '',
  css: '',
  js: '',
  show_bidvex_header: true,
  show_bidvex_footer: true,
  og_image_url: '',
};

const STATUS_META = {
  draft:     { label: 'Draft',     cls: 'bg-slate-100 text-slate-700 border-slate-200' },
  published: { label: 'Published', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  archived:  { label: 'Archived',  cls: 'bg-orange-100 text-orange-800 border-orange-200' },
};

const DEVICE_SIZES = {
  desktop: { w: '100%',  h: '100%', label: 'Desktop' },
  tablet:  { w: '768px', h: '1024px', label: 'Tablet' },
  mobile:  { w: '390px', h: '780px',  label: 'Mobile' },
};

/**
 * Custom monospace textarea with Tab-to-spaces + Shift+Tab dedent.
 * Prevents the browser from tab-focusing away from the editor while the
 * author is writing HTML/CSS/JS.
 */
function CodeArea({ value, onChange, testId, rows = 20, placeholder }) {
  const handleKeyDown = (e) => {
    if (e.key !== 'Tab') return;
    e.preventDefault();
    const ta = e.currentTarget;
    const { selectionStart: s, selectionEnd: eEnd, value: v } = ta;
    const TAB = '  '; // two-space soft tab
    if (!e.shiftKey && s === eEnd) {
      // simple insert
      const next = v.slice(0, s) + TAB + v.slice(eEnd);
      onChange(next);
      // restore caret
      requestAnimationFrame(() => {
        ta.selectionStart = ta.selectionEnd = s + TAB.length;
      });
      return;
    }
    // block-indent (multi-line selection or shift+tab)
    const before = v.slice(0, s);
    const after = v.slice(eEnd);
    const lineStart = before.lastIndexOf('\n') + 1;
    const block = v.slice(lineStart, eEnd);
    let updatedBlock;
    if (e.shiftKey) {
      updatedBlock = block
        .split('\n')
        .map((line) => line.startsWith(TAB) ? line.slice(TAB.length)
                     : line.startsWith(' ') ? line.slice(1)
                     : line)
        .join('\n');
    } else {
      updatedBlock = block.split('\n').map((line) => TAB + line).join('\n');
    }
    const next = v.slice(0, lineStart) + updatedBlock + after;
    onChange(next);
    const delta = updatedBlock.length - block.length;
    requestAnimationFrame(() => {
      ta.selectionStart = s + (e.shiftKey ? Math.max(-TAB.length, delta) : TAB.length);
      ta.selectionEnd = eEnd + delta;
    });
  };
  return (
    <textarea
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      spellCheck={false}
      autoCorrect="off"
      autoCapitalize="off"
      rows={rows}
      placeholder={placeholder}
      data-testid={testId}
      className="w-full font-mono text-[13px] leading-6 bg-slate-950 text-slate-100 rounded-md p-3 border border-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 resize-vertical"
      style={{ tabSize: 2, minHeight: '360px' }}
    />
  );
}

export default function AdminLandingPageEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(null);
  const [form, setForm] = useState(DEFAULT_STATE);
  const [dirty, setDirty] = useState(false);
  const [tab, setTab] = useState('settings');

  // Preview controls (Tab 3)
  const [previewDevice, setPreviewDevice] = useState('desktop');
  const [previewLang, setPreviewLang] = useState('en');
  const [previewNonce, setPreviewNonce] = useState(0);

  const authHeaders = useMemo(() => ({
    Authorization: `Bearer ${_token()}`,
  }), []);

  const load = useCallback(async () => {
    if (isNew) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/admin/landing-pages/${id}`, { headers: authHeaders });
      const p = res.data || {};
      setPage(p);
      setForm({
        slug: p.slug || '',
        title_en: p.title_en || '',
        title_fr: p.title_fr || '',
        meta_description_en: p.meta_description_en || '',
        meta_description_fr: p.meta_description_fr || '',
        html_en: p.html_en || '',
        html_fr: p.html_fr || '',
        css: p.css || '',
        js: p.js || '',
        show_bidvex_header: p.show_bidvex_header !== false,
        show_bidvex_footer: p.show_bidvex_footer !== false,
        og_image_url: p.og_image_url || '',
      });
      setDirty(false);
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Failed to load page';
      toast.error(typeof msg === 'string' ? msg : 'Failed to load page');
      navigate('/admin/landing-pages');
    } finally {
      setLoading(false);
    }
  }, [id, isNew, authHeaders, navigate]);

  useEffect(() => { load(); }, [load]);

  // Unsaved-changes warning
  useEffect(() => {
    const beforeUnload = (e) => {
      if (dirty) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty]);

  const patch = (updates) => {
    setForm((prev) => ({ ...prev, ...updates }));
    setDirty(true);
  };

  const validate = () => {
    const errs = [];
    const slugTrim = (form.slug || '').trim();
    if (!slugTrim) errs.push('Slug is required.');
    if (slugTrim && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slugTrim)) {
      errs.push('Slug must be lowercase letters/digits and single hyphens.');
    }
    if (!form.title_en?.trim()) errs.push('English title is required.');
    return errs;
  };

  const handleSave = async () => {
    const errs = validate();
    if (errs.length) { toast.error(errs[0]); return; }
    setSaving(true);
    try {
      let res;
      if (isNew) {
        res = await axios.post(`${API_BASE}/admin/landing-pages`, form, { headers: authHeaders });
        const created = res.data;
        toast.success('Draft created');
        setDirty(false);
        navigate(`/admin/landing-pages/${created.id}`, { replace: true });
      } else {
        res = await axios.patch(`${API_BASE}/admin/landing-pages/${id}`, form, { headers: authHeaders });
        const updated = res.data;
        setPage(updated);
        setForm((prev) => ({
          ...prev,
          html_en: updated.html_en || '',
          html_fr: updated.html_fr || '',
          css: updated.css || '',
          js: updated.js || '',
        }));
        setDirty(false);
        setPreviewNonce((n) => n + 1);
        toast.success('Saved');
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = detail?.message_en || (typeof detail === 'string' ? detail : null)
                || (Array.isArray(detail) ? detail[0]?.msg : null)
                || 'Save failed';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (dirty) {
      const ok = window.confirm('You have unsaved changes. Save first and then publish?');
      if (!ok) return;
      await handleSave();
    }
    try {
      const res = await axios.post(`${API_BASE}/admin/landing-pages/${id}/publish`, {}, { headers: authHeaders });
      setPage(res.data);
      toast.success('Published — live at /lp/' + form.slug);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(detail?.message_en || (typeof detail === 'string' ? detail : null) || 'Publish failed');
    }
  };

  const handleUnpublish = async () => {
    try {
      const res = await axios.post(`${API_BASE}/admin/landing-pages/${id}/unpublish`, {}, { headers: authHeaders });
      setPage(res.data);
      toast.success('Moved back to draft');
    } catch {
      toast.error('Failed to unpublish');
    }
  };

  const previewUrl = useMemo(() => {
    if (!page?.slug) return '';
    const params = new URLSearchParams();
    params.set('lang', previewLang);
    // The public renderer honours show_bidvex_header/footer from the DB.
    // We add a nonce query param to bust the iframe cache after saving.
    params.set('_n', String(previewNonce));
    return `${publicBase()}/api/lp/${page.slug}/render?${params.toString()}`;
  }, [page?.slug, previewLang, previewNonce]);

  const copySlugUrl = () => {
    const url = `${publicBase()}/api/lp/${form.slug}/render`;
    navigator.clipboard.writeText(url).then(() => toast.success('Copied public URL'));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
      </div>
    );
  }

  const statusMeta = STATUS_META[page?.status || 'draft'];

  return (
    <div className="min-h-screen bg-slate-50" data-testid="admin-landing-page-editor">
      {/* Header */}
      <div className="border-b bg-white sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 lg:px-6 py-3 flex flex-wrap items-center gap-3">
          <Button
            variant="ghost"
            onClick={() => {
              if (dirty && !window.confirm('Discard unsaved changes?')) return;
              navigate('/admin/landing-pages');
            }}
            className="text-slate-600"
            data-testid="lp-editor-back"
          >
            <ArrowLeft className="h-4 w-4 mr-1" /> Pages
          </Button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-slate-900 truncate">
                {isNew ? 'New Landing Page' : (form.title_en || form.slug || 'Untitled')}
              </h1>
              {!isNew && <Badge className={`border ${statusMeta.cls}`}>{statusMeta.label}</Badge>}
              {dirty && (
                <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800">
                  <AlertCircle className="h-3 w-3 mr-1" /> Unsaved
                </Badge>
              )}
            </div>
            {form.slug && (
              <div className="text-xs text-slate-500 font-mono flex items-center gap-1">
                /lp/{form.slug}
                {!isNew && (
                  <button
                    type="button"
                    onClick={copySlugUrl}
                    className="ml-1 text-slate-400 hover:text-slate-700"
                    title="Copy public URL"
                    data-testid="lp-editor-copy-url"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleSave}
              disabled={saving}
              data-testid="lp-editor-save"
            >
              {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
              {isNew ? 'Save draft' : 'Save'}
            </Button>
            {!isNew && page?.status !== 'published' && (
              <Button
                onClick={handlePublish}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
                data-testid="lp-editor-publish"
              >
                <Send className="h-4 w-4 mr-1" /> Publish
              </Button>
            )}
            {!isNew && page?.status === 'published' && (
              <Button
                variant="outline"
                onClick={handleUnpublish}
                data-testid="lp-editor-unpublish"
              >
                <Ban className="h-4 w-4 mr-1" /> Unpublish
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-6">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="justify-start">
            <TabsTrigger value="settings" data-testid="lp-tab-settings">Settings</TabsTrigger>
            <TabsTrigger value="html" data-testid="lp-tab-html">HTML Editor</TabsTrigger>
            <TabsTrigger
              value="preview"
              disabled={isNew}
              data-testid="lp-tab-preview"
              title={isNew ? 'Save first to enable preview' : undefined}
            >
              Preview
            </TabsTrigger>
          </TabsList>

          {/* ─── Settings ─────────────────────────────────────────── */}
          <TabsContent value="settings">
            <Card>
              <CardContent className="py-6 space-y-6">
                {/* Row: slug + status */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="lp-slug">Slug *</Label>
                    <Input
                      id="lp-slug"
                      value={form.slug}
                      onChange={(e) => patch({ slug: e.target.value.toLowerCase() })}
                      placeholder="e.g. spring-auction-2026"
                      data-testid="lp-input-slug"
                      className="font-mono"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Lowercase letters, digits and single hyphens. Final URL: <code>/lp/{form.slug || '…'}</code>
                    </p>
                  </div>
                  <div>
                    <Label>OG Image URL</Label>
                    <Input
                      value={form.og_image_url}
                      onChange={(e) => patch({ og_image_url: e.target.value })}
                      placeholder="https://…/social-share.png"
                      data-testid="lp-input-og-image"
                    />
                  </div>
                </div>

                {/* EN / FR titles */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="lp-title-en">Title (English) *</Label>
                    <Input
                      id="lp-title-en"
                      value={form.title_en}
                      onChange={(e) => patch({ title_en: e.target.value })}
                      placeholder="Big Spring Auction — Live Bidding"
                      data-testid="lp-input-title-en"
                    />
                    <div className="text-xs text-slate-500 mt-1">{(form.title_en || '').length}/160</div>
                  </div>
                  <div>
                    <Label htmlFor="lp-title-fr">Title (French)</Label>
                    <Input
                      id="lp-title-fr"
                      value={form.title_fr}
                      onChange={(e) => patch({ title_fr: e.target.value })}
                      placeholder="Grande vente aux enchères du printemps"
                      data-testid="lp-input-title-fr"
                    />
                    <div className="text-xs text-slate-500 mt-1">{(form.title_fr || '').length}/160</div>
                  </div>
                </div>

                {/* EN / FR meta descriptions */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="lp-meta-en">Meta description (English)</Label>
                    <Textarea
                      id="lp-meta-en"
                      value={form.meta_description_en}
                      onChange={(e) => patch({ meta_description_en: e.target.value })}
                      placeholder="A short SEO description (140–160 chars)."
                      rows={3}
                      data-testid="lp-input-meta-en"
                    />
                    <div className="text-xs text-slate-500 mt-1">{(form.meta_description_en || '').length}/320</div>
                  </div>
                  <div>
                    <Label htmlFor="lp-meta-fr">Meta description (French)</Label>
                    <Textarea
                      id="lp-meta-fr"
                      value={form.meta_description_fr}
                      onChange={(e) => patch({ meta_description_fr: e.target.value })}
                      placeholder="Une courte description SEO (140–160 caractères)."
                      rows={3}
                      data-testid="lp-input-meta-fr"
                    />
                    <div className="text-xs text-slate-500 mt-1">{(form.meta_description_fr || '').length}/320</div>
                  </div>
                </div>

                {/* Header / footer toggles */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
                    <div>
                      <div className="font-medium">Show BidVex header</div>
                      <div className="text-xs text-slate-500">Adds the BidVex brand bar at the top of the page.</div>
                    </div>
                    <Switch
                      checked={form.show_bidvex_header}
                      onCheckedChange={(v) => patch({ show_bidvex_header: !!v })}
                      data-testid="lp-toggle-header"
                    />
                  </div>
                  <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
                    <div>
                      <div className="font-medium">Show BidVex footer</div>
                      <div className="text-xs text-slate-500">Adds the BidVex copyright/footer at the bottom.</div>
                    </div>
                    <Switch
                      checked={form.show_bidvex_footer}
                      onCheckedChange={(v) => patch({ show_bidvex_footer: !!v })}
                      data-testid="lp-toggle-footer"
                    />
                  </div>
                </div>

                {!isNew && page && (
                  <div className="text-xs text-slate-500 pt-2 border-t">
                    Created {new Date(page.created_at).toLocaleString()}
                    {page.updated_at ? ` · Updated ${new Date(page.updated_at).toLocaleString()}` : ''}
                    {page.published_at ? ` · Published ${new Date(page.published_at).toLocaleString()}` : ''}
                    {typeof page.analytics?.total_views === 'number' && ` · ${page.analytics.total_views} total views`}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ─── HTML Editor ─────────────────────────────────────── */}
          <TabsContent value="html">
            <Card>
              <CardContent className="py-6 space-y-6">
                <div className="text-xs text-slate-500 flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                  Tab inserts 2 spaces · Shift+Tab dedents · &lt;script&gt; tags in body HTML are stripped — use the JS panel for code.
                </div>
                <div>
                  <Label>English HTML</Label>
                  <CodeArea
                    value={form.html_en}
                    onChange={(v) => patch({ html_en: v })}
                    placeholder="<section>Your English body HTML…</section>"
                    testId="lp-code-html-en"
                    rows={16}
                  />
                </div>
                <div>
                  <Label>French HTML</Label>
                  <CodeArea
                    value={form.html_fr}
                    onChange={(v) => patch({ html_fr: v })}
                    placeholder="<section>Votre contenu HTML français…</section>"
                    testId="lp-code-html-fr"
                    rows={16}
                  />
                </div>
                <div>
                  <Label>Custom CSS</Label>
                  <CodeArea
                    value={form.css}
                    onChange={(v) => patch({ css: v })}
                    placeholder=".hero { color: white; }"
                    testId="lp-code-css"
                    rows={10}
                  />
                </div>
                <div>
                  <Label>Custom JS</Label>
                  <CodeArea
                    value={form.js}
                    onChange={(v) => patch({ js: v })}
                    placeholder="document.querySelector('.cta')?.addEventListener('click', …);"
                    testId="lp-code-js"
                    rows={8}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ─── Preview ─────────────────────────────────────────── */}
          <TabsContent value="preview">
            <Card>
              <CardContent className="py-6">
                {isNew || !page?.slug ? (
                  <div className="text-center py-10 text-slate-500">
                    Save the page first — preview is available once a slug exists.
                  </div>
                ) : (
                  <>
                    <div className="flex flex-wrap items-center gap-2 justify-between mb-4">
                      {/* Device toggles */}
                      <div className="inline-flex items-center gap-1 rounded-lg border bg-white p-1" role="group">
                        {Object.entries(DEVICE_SIZES).map(([key, meta]) => {
                          const Icon = key === 'desktop' ? Monitor : key === 'tablet' ? Tablet : Smartphone;
                          const active = previewDevice === key;
                          return (
                            <button
                              key={key}
                              type="button"
                              onClick={() => setPreviewDevice(key)}
                              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm ${
                                active ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                              }`}
                              data-testid={`lp-preview-device-${key}`}
                            >
                              <Icon className="h-4 w-4" /> {meta.label}
                            </button>
                          );
                        })}
                      </div>

                      {/* Language toggles */}
                      <div className="inline-flex items-center gap-1 rounded-lg border bg-white p-1" role="group">
                        {['en', 'fr'].map((lang) => {
                          const active = previewLang === lang;
                          return (
                            <button
                              key={lang}
                              type="button"
                              onClick={() => setPreviewLang(lang)}
                              className={`px-3 py-1.5 rounded-md text-sm font-medium ${
                                active ? 'bg-cyan-600 text-white' : 'text-slate-600 hover:bg-slate-100'
                              }`}
                              data-testid={`lp-preview-lang-${lang}`}
                            >
                              {lang.toUpperCase()}
                            </button>
                          );
                        })}
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPreviewNonce((n) => n + 1)}
                          data-testid="lp-preview-refresh"
                        >
                          <RefreshCw className="h-4 w-4 mr-1" /> Refresh
                        </Button>
                        <a
                          href={previewUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          data-testid="lp-preview-open"
                        >
                          <Button variant="outline" size="sm">
                            <ExternalLink className="h-4 w-4 mr-1" /> Open
                          </Button>
                        </a>
                      </div>
                    </div>

                    {page?.status !== 'published' && (
                      <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 text-amber-800 px-3 py-2 text-sm">
                        This page is a <strong>draft</strong>. Preview shows the latest saved content but the public URL will 404 until you publish.
                      </div>
                    )}

                    {dirty && (
                      <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 text-slate-700 px-3 py-2 text-sm">
                        Unsaved changes are not reflected in the preview — save to refresh.
                      </div>
                    )}

                    {/* Iframe frame */}
                    <div className="mx-auto rounded-lg border shadow-inner bg-white overflow-hidden"
                         style={{
                           width: DEVICE_SIZES[previewDevice].w,
                           maxWidth: '100%',
                           height: previewDevice === 'desktop' ? '700px' : DEVICE_SIZES[previewDevice].h,
                         }}>
                      {/* When page is a draft, /api/lp/{slug} returns 404. To still let
                          admin preview draft content, we fall back to a "render preview"
                          note. Once published, iframe shows the real public page. */}
                      {page?.status === 'published' ? (
                        <iframe
                          key={previewUrl}
                          src={previewUrl}
                          title="Landing page preview"
                          className="w-full h-full border-0"
                          data-testid="lp-preview-iframe"
                        />
                      ) : (
                        <DraftPreview form={form} lang={previewLang} />
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

/**
 * Draft preview renderer — mirrors the backend `/api/lp/{slug}/render`
 * pipeline (title, meta, header/footer, custom CSS/JS) so admins can
 * preview the exact same layout while the page is still a draft.
 *
 * IMPORTANT: We render into an iframe via srcDoc to keep the custom
 * CSS/JS scoped and unable to touch the admin UI.
 */
function DraftPreview({ form, lang }) {
  const html = useMemo(() => {
    const locale = lang === 'fr' && (form.html_fr || form.title_fr) ? 'fr' : 'en';
    const title = (locale === 'fr' && form.title_fr) ? form.title_fr : (form.title_en || 'BidVex');
    const desc = (locale === 'fr' && form.meta_description_fr) ? form.meta_description_fr : (form.meta_description_en || '');
    const body = (locale === 'fr' && form.html_fr) ? form.html_fr : (form.html_en || '');
    const css = form.css || '';
    const js = form.js || '';
    const header = form.show_bidvex_header
      ? '<header class="bidvex-lp-header" data-testid="bidvex-lp-header" style="border-bottom:1px solid #e2e8f0;padding:16px 24px;font-family:sans-serif;font-weight:700;color:#0f172a;"><a href="#" style="color:#0891b2;text-decoration:none;">BidVex</a></header>'
      : '';
    const footer = form.show_bidvex_footer
      ? '<footer class="bidvex-lp-footer" data-testid="bidvex-lp-footer" style="border-top:1px solid #e2e8f0;padding:16px 24px;font-size:12px;color:#64748b;text-align:center;font-family:sans-serif;">© BidVex — <a href="#" style="color:#0891b2;">bidvex.com</a></footer>'
      : '';
    const esc = (s) => String(s || '').replace(/[&<>"']/g, (m) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[m]));
    return `<!DOCTYPE html><html lang="${locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><meta name="description" content="${esc(desc)}"><style>${css}</style></head><body style="margin:0;font-family:'Inter',system-ui,sans-serif;color:#0f172a;background:#fff;">${header}<main class="bidvex-lp-body">${body}</main>${footer}<script>${js}<\/script></body></html>`;
  }, [form, lang]);

  return (
    <iframe
      srcDoc={html}
      title="Draft preview"
      className="w-full h-full border-0"
      sandbox="allow-scripts allow-same-origin"
      data-testid="lp-preview-draft-iframe"
    />
  );
}
