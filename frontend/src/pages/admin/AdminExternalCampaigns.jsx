/**
 * iter271 — Admin External Email Campaigns.
 *
 * Acquisition-focused marketing emails sent to NON-registered contacts.
 * Strictly isolated from the existing platform email-campaigns tab.
 *
 * Includes:
 *   • Campaign list with status badges + analytics summary
 *   • 4-step wizard (Content → Recipients → Attachments → Review)
 *   • Manual paste + CSV upload for recipients
 *   • Attachment upload with size/type validation (PDF/JPG/PNG/DOCX/XLSX)
 *   • Test-send button, schedule picker, Send Now confirmation
 *   • Analytics view + Suppression list sub-tab
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  Mail, Send, Users, Paperclip, RefreshCw, Trash2,
  CheckCircle2, AlertTriangle, Loader2, Plus, X, Eye, Calendar,
  Download, Ban,
} from 'lucide-react';

const API = API_BASE;

const STATUS_BADGES = {
  draft:      { label: '🟡 Draft',       cls: 'bg-slate-100 text-slate-700 border-slate-300' },
  scheduled:  { label: '📅 Scheduled',   cls: 'bg-blue-100 text-blue-800 border-blue-300' },
  sending:    { label: '🔄 Sending…',    cls: 'bg-indigo-100 text-indigo-800 border-indigo-300 animate-pulse' },
  sent:       { label: '✅ Sent',         cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  failed:     { label: '❌ Failed',       cls: 'bg-rose-100 text-rose-800 border-rose-300' },
  paused:     { label: '⏸️ Paused',       cls: 'bg-amber-100 text-amber-800 border-amber-300' },
};

const TABS = [
  { id: 'campaigns',    label: '📬 Campaigns' },
  { id: 'suppressions', label: '🚫 Suppression List' },
];

export default function AdminExternalCampaigns() {
  const { token } = useAuth();
  const headers = { Authorization: `Bearer ${token}` };
  const [activeTab, setActiveTab] = useState('campaigns');
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [analyticsId, setAnalyticsId] = useState(null);
  const [showWizard, setShowWizard] = useState(false);

  const fetchCampaigns = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      if (search) params.set('search', search);
      const r = await axios.get(
        `${API}/admin/external-campaigns?${params.toString()}`, { headers },
      );
      setCampaigns(r.data?.campaigns || []);
    } catch (e) {
      toast.error('Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search, token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  return (
    <div className="space-y-5" data-testid="external-campaigns">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Mail className="h-6 w-6" /> External Email Campaigns
          </h2>
          <p className="text-sm text-slate-500">
            Send marketing emails to non-registered contacts.
          </p>
        </div>
        <Button
          onClick={() => { setEditingId(null); setShowWizard(true); }}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          data-testid="new-external-campaign-btn"
        >
          <Plus className="h-4 w-4 mr-1" /> New Campaign
        </Button>
      </header>

      <div className="flex gap-2 border-b">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-2 text-sm font-medium ${
              activeTab === t.id
                ? 'border-b-2 border-emerald-600 text-emerald-700'
                : 'text-slate-500 hover:text-slate-700'
            }`}
            data-testid={`tab-${t.id}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'campaigns' && (
        <CampaignsList
          campaigns={campaigns}
          loading={loading}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          search={search}
          setSearch={setSearch}
          onRefresh={fetchCampaigns}
          onEdit={(id) => { setEditingId(id); setShowWizard(true); }}
          onAnalytics={setAnalyticsId}
          onDeleted={fetchCampaigns}
          headers={headers}
        />
      )}

      {activeTab === 'suppressions' && (
        <SuppressionList headers={headers} />
      )}

      {showWizard && (
        <CampaignWizard
          campaignId={editingId}
          headers={headers}
          onClose={() => { setShowWizard(false); fetchCampaigns(); }}
        />
      )}

      {analyticsId && (
        <AnalyticsView
          campaignId={analyticsId}
          headers={headers}
          onClose={() => setAnalyticsId(null)}
        />
      )}
    </div>
  );
}


// ── Campaign list ──

function CampaignsList({ campaigns, loading, statusFilter, setStatusFilter, search, setSearch, onRefresh, onEdit, onAnalytics, onDeleted, headers }) {
  const handleDelete = async (id) => {
    if (!window.confirm('Delete this draft campaign?')) return;
    try {
      await axios.delete(`${API}/admin/external-campaigns/${id}`, { headers });
      toast.success('Campaign deleted');
      onDeleted();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  if (loading) {
    return <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin inline" /></div>;
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-slate-200 rounded px-2 py-1 text-sm"
            data-testid="campaign-status-filter"
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="scheduled">Scheduled</option>
            <option value="sending">Sending</option>
            <option value="sent">Sent</option>
            <option value="paused">Paused</option>
            <option value="failed">Failed</option>
          </select>
          <Input
            placeholder="Search campaigns…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
            data-testid="campaign-search"
          />
          <Button variant="outline" size="sm" onClick={onRefresh} data-testid="campaign-refresh">
            <RefreshCw className="h-3 w-3 mr-1" /> Refresh
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="campaign-list-table">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Name</th>
                <th className="px-3 py-2 text-right font-semibold">Recipients</th>
                <th className="px-3 py-2 text-left font-semibold">Status</th>
                <th className="px-3 py-2 text-left font-semibold">Sent At</th>
                <th className="px-3 py-2 text-left font-semibold">Open Rate</th>
                <th className="px-3 py-2 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.length === 0 && (
                <tr><td colSpan={6} className="py-10 text-center text-slate-400">
                  No external campaigns yet — click "New Campaign" to start.
                </td></tr>
              )}
              {campaigns.map(c => {
                const badge = STATUS_BADGES[c.status] || STATUS_BADGES.draft;
                const openRate = c.analytics?.open_rate_pct ?? 0;
                return (
                  <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`campaign-row-${c.id}`}>
                    <td className="px-3 py-2 font-medium">{c.name}</td>
                    <td className="px-3 py-2 text-right">{c.recipient_count || 0}</td>
                    <td className="px-3 py-2">
                      <Badge className={`border ${badge.cls}`}>{badge.label}</Badge>
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-500">
                      {c.sent_at ? new Date(c.sent_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {c.status === 'sent' ? `${openRate}%` : '—'}
                    </td>
                    <td className="px-3 py-2 text-right space-x-1">
                      {c.status === 'draft' && (
                        <Button size="sm" variant="outline" onClick={() => onEdit(c.id)} data-testid={`edit-${c.id}`}>
                          Edit
                        </Button>
                      )}
                      {c.status === 'sent' && (
                        <Button size="sm" variant="outline" onClick={() => onAnalytics(c.id)} data-testid={`analytics-${c.id}`}>
                          <Eye className="h-3 w-3 mr-1" /> Analytics
                        </Button>
                      )}
                      {(c.status === 'draft' || c.status === 'scheduled') && (
                        <Button size="sm" variant="outline" onClick={() => handleDelete(c.id)} className="text-rose-600 border-rose-300" data-testid={`delete-${c.id}`}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}


// ── 4-step wizard ──

function CampaignWizard({ campaignId, headers, onClose }) {
  const [step, setStep] = useState(1);
  const [doc, setDoc] = useState({
    name: '', subject_en: '', subject_fr: '',
    body_html_en: '', body_html_fr: '',
    cta_label_en: 'Register Now',
    cta_label_fr: "S'inscrire maintenant",
    cta_url: 'https://bidvex.com/register',
    reply_to_email: 'support@bidvex.com',
  });
  const [savedId, setSavedId] = useState(campaignId || null);
  const [manualEmails, setManualEmails] = useState('');
  const [stats, setStats] = useState({ recipient_count: 0, attachments: [] });
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!campaignId) return;
    (async () => {
      try {
        const r = await axios.get(`${API}/admin/external-campaigns/${campaignId}`, { headers });
        setDoc({
          name: r.data.name || '',
          subject_en: r.data.subject_en || '',
          subject_fr: r.data.subject_fr || '',
          body_html_en: r.data.body_html_en || '',
          body_html_fr: r.data.body_html_fr || '',
          cta_label_en: r.data.cta_label_en || 'Register Now',
          cta_label_fr: r.data.cta_label_fr || "S'inscrire maintenant",
          cta_url: r.data.cta_url || 'https://bidvex.com/register',
          reply_to_email: r.data.reply_to_email || 'support@bidvex.com',
        });
        setStats({
          recipient_count: r.data.recipient_count || 0,
          attachments: r.data.attachments || [],
        });
        setSavedId(campaignId);
      } catch (e) {
        toast.error('Failed to load campaign');
      }
    })();
  }, [campaignId]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveDraft = async () => {
    try {
      if (!savedId) {
        const r = await axios.post(`${API}/admin/external-campaigns`, doc, { headers });
        setSavedId(r.data.campaign_id);
        toast.success('Draft saved');
        return r.data.campaign_id;
      } else {
        await axios.patch(`${API}/admin/external-campaigns/${savedId}`, doc, { headers });
        toast.success('Draft updated');
        return savedId;
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
      return null;
    }
  };

  const addManualRecipients = async () => {
    if (!savedId) {
      const id = await saveDraft();
      if (!id) return;
    }
    const emails = manualEmails
      .split(/[\n,]+/).map(e => e.trim()).filter(Boolean);
    try {
      const r = await axios.post(
        `${API}/admin/external-campaigns/${savedId}/recipients/manual`,
        { emails },
        { headers },
      );
      const d = r.data;
      toast.success(
        `Added ${d.added} · Duplicates ${d.duplicates} · Invalid ${d.invalid} · Suppressed ${d.suppressed}`,
      );
      setStats(s => ({ ...s, recipient_count: d.total }));
      setManualEmails('');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to add recipients');
    }
  };

  const uploadCSV = async (file) => {
    if (!savedId) {
      const id = await saveDraft();
      if (!id) return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post(
        `${API}/admin/external-campaigns/${savedId}/recipients/csv`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } },
      );
      const d = r.data;
      toast.success(
        `Processed ${d.processed} · Added ${d.added} · Invalid ${d.invalid} · Suppressed ${d.suppressed}`,
      );
      setStats(s => ({ ...s, recipient_count: d.total }));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'CSV upload failed');
    }
  };

  const uploadAttachment = async (file) => {
    if (!savedId) {
      const id = await saveDraft();
      if (!id) return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post(
        `${API}/admin/external-campaigns/${savedId}/attachments`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } },
      );
      toast.success(`Attached ${r.data.filename}`);
      // Refetch the campaign to update the attachments list
      const cdoc = await axios.get(`${API}/admin/external-campaigns/${savedId}`, { headers });
      setStats(s => ({ ...s, attachments: cdoc.data.attachments || [] }));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Attachment upload failed');
    }
  };

  const deleteAttachment = async (attId) => {
    try {
      await axios.delete(
        `${API}/admin/external-campaigns/${savedId}/attachments/${attId}`,
        { headers },
      );
      const cdoc = await axios.get(`${API}/admin/external-campaigns/${savedId}`, { headers });
      setStats(s => ({ ...s, attachments: cdoc.data.attachments || [] }));
      toast.success('Attachment removed');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  const sendTest = async () => {
    if (!savedId) {
      const id = await saveDraft();
      if (!id) return;
    }
    const to = window.prompt('Send test email to:', '');
    if (!to) return;
    try {
      await axios.post(
        `${API}/admin/external-campaigns/${savedId}/send-test`,
        { to_email: to },
        { headers },
      );
      toast.success(`Test sent to ${to}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Test send failed');
    }
  };

  const sendNow = async () => {
    if (!savedId) return toast.error('Save the draft first.');
    if (!window.confirm(`Send to ${stats.recipient_count} real recipients? This cannot be undone.`)) return;
    try {
      setSending(true);
      const r = await axios.post(
        `${API}/admin/external-campaigns/${savedId}/send-now`, {}, { headers },
      );
      toast.success(`Sent: ${r.data.sent} · Skipped: ${r.data.skipped} · Failures: ${r.data.failures}`);
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-[720px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {savedId ? 'Edit Campaign' : 'New External Campaign'}
          </DialogTitle>
          <div className="text-xs text-slate-500 mt-1">
            Step {step} of 4 — {['Content', 'Recipients', 'Attachments', 'Review & Send'][step - 1]}
          </div>
          <div className="flex gap-1 mt-2">
            {[1, 2, 3, 4].map(s => (
              <div
                key={s}
                className={`h-1 flex-1 rounded ${
                  s <= step ? 'bg-emerald-500' : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
        </DialogHeader>

        {/* Step 1 — Content */}
        {step === 1 && (
          <div className="space-y-3" data-testid="step-content">
            <div>
              <Label>Campaign Name (internal)</Label>
              <Input
                value={doc.name}
                onChange={(e) => setDoc({ ...doc, name: e.target.value })}
                data-testid="campaign-name-input"
                placeholder="Summer Promo 2026"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div>
                <Label>Subject — English</Label>
                <Input
                  value={doc.subject_en}
                  onChange={(e) => setDoc({ ...doc, subject_en: e.target.value })}
                  data-testid="subject-en-input"
                />
              </div>
              <div>
                <Label>Subject — Français</Label>
                <Input
                  value={doc.subject_fr}
                  onChange={(e) => setDoc({ ...doc, subject_fr: e.target.value })}
                  data-testid="subject-fr-input"
                />
              </div>
            </div>
            <div>
              <Label>Body HTML — English (must include <code>{'{unsubscribe_url}'}</code>)</Label>
              <Textarea
                rows={8}
                value={doc.body_html_en}
                onChange={(e) => setDoc({ ...doc, body_html_en: e.target.value })}
                placeholder="<p>Discover Canada's leading auction platform...</p>"
                data-testid="body-en-input"
                className="font-mono text-xs"
              />
              {doc.body_html_en && !doc.body_html_en.includes('{unsubscribe_url}') && (
                <p className="text-xs text-amber-600 mt-1">
                  ⚠️ Add <code>{'{unsubscribe_url}'}</code> for CASL compliance — a footer will be auto-appended if missing.
                </p>
              )}
            </div>
            <div>
              <Label>Body HTML — Français</Label>
              <Textarea
                rows={4}
                value={doc.body_html_fr}
                onChange={(e) => setDoc({ ...doc, body_html_fr: e.target.value })}
                data-testid="body-fr-input"
                className="font-mono text-xs"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div>
                <Label className="text-xs">CTA Label EN</Label>
                <Input
                  value={doc.cta_label_en}
                  onChange={(e) => setDoc({ ...doc, cta_label_en: e.target.value })}
                  data-testid="cta-label-en-input"
                />
              </div>
              <div>
                <Label className="text-xs">CTA Label FR</Label>
                <Input
                  value={doc.cta_label_fr}
                  onChange={(e) => setDoc({ ...doc, cta_label_fr: e.target.value })}
                  data-testid="cta-label-fr-input"
                />
              </div>
              <div>
                <Label className="text-xs">CTA URL</Label>
                <Input
                  value={doc.cta_url}
                  onChange={(e) => setDoc({ ...doc, cta_url: e.target.value })}
                  data-testid="cta-url-input"
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 2 — Recipients */}
        {step === 2 && (
          <div className="space-y-3" data-testid="step-recipients">
            <p className="text-sm text-slate-500">
              Currently {stats.recipient_count} recipient(s) in this campaign.
            </p>
            <div>
              <Label>Paste email addresses (comma or newline separated)</Label>
              <Textarea
                rows={5}
                value={manualEmails}
                onChange={(e) => setManualEmails(e.target.value)}
                placeholder={"foo@example.com\nbar@example.ca, baz@example.org"}
                data-testid="manual-emails-input"
              />
              <Button size="sm" className="mt-2" onClick={addManualRecipients} data-testid="add-emails-btn">
                <Plus className="h-3 w-3 mr-1" /> Add Emails
              </Button>
            </div>
            <div className="border-t pt-3">
              <Label>Or upload CSV (column "email" required)</Label>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => e.target.files?.[0] && uploadCSV(e.target.files[0])}
                className="block mt-1 text-sm"
                data-testid="csv-upload-input"
              />
              <p className="text-xs text-slate-500 mt-1">
                Max 10,000 rows · 5 MB · Suppressed emails are filtered out.
              </p>
            </div>
          </div>
        )}

        {/* Step 3 — Attachments */}
        {step === 3 && (
          <div className="space-y-3" data-testid="step-attachments">
            <p className="text-sm text-slate-500">
              📎 PDF, JPG, PNG, DOCX, XLSX · Max 3 MB each · Max 3 files
            </p>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx"
              onChange={(e) => e.target.files?.[0] && uploadAttachment(e.target.files[0])}
              className="block text-sm"
              data-testid="attachment-upload-input"
            />
            <div className="space-y-1">
              {(stats.attachments || []).map(att => (
                <div
                  key={att.id}
                  className="flex items-center justify-between border rounded p-2 text-sm"
                  data-testid={`attachment-${att.id}`}
                >
                  <span className="flex items-center gap-2">
                    <Paperclip className="h-3 w-3" />
                    {att.filename}{' '}
                    <span className="text-xs text-slate-500">
                      ({(att.file_size_bytes / 1024).toFixed(0)} KB)
                    </span>
                  </span>
                  <Button size="sm" variant="outline" onClick={() => deleteAttachment(att.id)} className="text-rose-600">
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
            <p className="text-xs text-amber-600">
              ⚠️ Large attachments hurt deliverability — prefer linking to hosted files.
            </p>
          </div>
        )}

        {/* Step 4 — Review */}
        {step === 4 && (
          <div className="space-y-3 text-sm" data-testid="step-review">
            <div className="bg-slate-50 rounded p-3 space-y-1">
              <div><strong>Name:</strong> {doc.name}</div>
              <div><strong>Subject EN:</strong> {doc.subject_en}</div>
              <div><strong>Subject FR:</strong> {doc.subject_fr}</div>
              <div><strong>Recipients:</strong> {stats.recipient_count}</div>
              <div><strong>Attachments:</strong> {(stats.attachments || []).length}</div>
              <div><strong>From:</strong> BidVex Canada &lt;noreply@bidvex.ca&gt;</div>
              <div><strong>Reply-To:</strong> {doc.reply_to_email}</div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={sendTest} data-testid="send-test-btn">
                <Send className="h-3 w-3 mr-1" /> Send Test to My Email
              </Button>
            </div>
            <div className="border border-rose-200 bg-rose-50 rounded p-3 text-rose-800 text-xs">
              ⚠️ This will send to {stats.recipient_count} real email addresses. This action cannot be undone.
            </div>
            <Button
              className="w-full bg-rose-600 hover:bg-rose-700 text-white"
              onClick={sendNow}
              disabled={sending || stats.recipient_count === 0}
              data-testid="send-now-btn"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
              🚀 Send Campaign Now
            </Button>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={saveDraft} data-testid="save-draft-btn">
            💾 Save Draft
          </Button>
          {step > 1 && (
            <Button variant="outline" onClick={() => setStep(step - 1)} data-testid="prev-step-btn">
              ← Back
            </Button>
          )}
          {step < 4 && (
            <Button
              onClick={async () => {
                await saveDraft();
                setStep(step + 1);
              }}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid="next-step-btn"
            >
              Next →
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// ── Analytics view ──

function AnalyticsView({ campaignId, headers, onClose }) {
  const [data, setData] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setRefreshing(true);
      const r = await axios.get(
        `${API}/admin/external-campaigns/${campaignId}/analytics`,
        { headers },
      );
      setData(r.data);
    } catch (e) {
      toast.error('Failed to load analytics');
    } finally {
      setRefreshing(false);
    }
  }, [campaignId, headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (!data) {
    return (
      <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="sm:max-w-[640px]">
          <Loader2 className="h-6 w-6 animate-spin mx-auto" />
        </DialogContent>
      </Dialog>
    );
  }

  const cards = [
    { label: 'Delivered',    val: data.delivered, pct: data.delivery_rate_pct, color: 'emerald' },
    { label: 'Opened',       val: data.opened,    pct: data.open_rate_pct,     color: 'blue' },
    { label: 'Clicked',      val: data.clicked,   pct: data.click_rate_pct,    color: 'indigo' },
    { label: 'Bounced',      val: data.bounced,   pct: data.bounce_rate_pct,   color: 'rose' },
    { label: 'Unsub\'d',     val: data.unsubscribed, pct: null,                color: 'amber' },
    { label: 'Spam Reports', val: data.spam_reports, pct: null,                color: 'rose' },
  ];

  return (
    <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-[720px] max-h-[90vh] overflow-y-auto" data-testid="analytics-view">
        <DialogHeader>
          <DialogTitle>Campaign Analytics</DialogTitle>
          <div className="text-xs text-slate-500">
            Sent: {data.sent_at ? new Date(data.sent_at).toLocaleString() : '—'}{' '}
            · Last updated: {data.last_updated_at ? new Date(data.last_updated_at).toLocaleString() : 'never'}
          </div>
        </DialogHeader>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="analytics-cards">
          {cards.map(c => (
            <Card key={c.label}>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-slate-500">{c.label}</p>
                <p className={`text-2xl font-bold text-${c.color}-600`}>{c.val}</p>
                {c.pct != null && (
                  <p className="text-xs text-slate-500">{c.pct}%</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={fetchData} disabled={refreshing}>
            <RefreshCw className={`h-3 w-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Button onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// ── Suppression list ──

function SuppressionList({ headers }) {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchList = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      const r = await axios.get(
        `${API}/admin/external-suppressions?${params.toString()}`, { headers },
      );
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error('Failed to load suppression list');
    } finally {
      setLoading(false);
    }
  }, [search, headers]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const addSuppression = async () => {
    try {
      await axios.post(
        `${API}/admin/external-suppressions/add`,
        { email: newEmail, reason: 'manual' },
        { headers },
      );
      toast.success(`Suppressed ${newEmail}`);
      setNewEmail('');
      fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Add failed');
    }
  };

  const removeSuppression = async (email) => {
    if (!window.confirm(`Allow ${email} to receive marketing emails again?`)) return;
    try {
      await axios.delete(`${API}/admin/external-suppressions/${email}`, { headers });
      toast.success('Removed');
      fetchList();
    } catch (e) {
      toast.error('Remove failed');
    }
  };

  return (
    <Card data-testid="suppression-list">
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Search emails…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
            data-testid="suppression-search"
          />
          <Input
            placeholder="email@example.com"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            className="max-w-xs"
            data-testid="suppression-add-input"
          />
          <Button onClick={addSuppression} size="sm" data-testid="suppression-add-btn">
            <Ban className="h-3 w-3 mr-1" /> Add Suppression
          </Button>
        </div>
        {loading ? (
          <Loader2 className="h-6 w-6 animate-spin mx-auto" />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left">Email</th>
                <th className="px-3 py-2 text-left">Reason</th>
                <th className="px-3 py-2 text-left">Campaign</th>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-slate-400">
                  No suppressed emails.
                </td></tr>
              )}
              {items.map(s => (
                <tr key={s.email} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-mono text-xs">{s.email}</td>
                  <td className="px-3 py-2">
                    <Badge className="border bg-slate-100 text-slate-700 border-slate-300">
                      {s.reason || 'manual'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">{s.campaign_id || '—'}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">
                    {s.suppressed_at ? new Date(s.suppressed_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button size="sm" variant="outline" onClick={() => removeSuppression(s.email)}>
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
