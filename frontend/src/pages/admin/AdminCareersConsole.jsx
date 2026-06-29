/**
 * iter318 — Admin Careers console (/admin/careers).
 *
 * Two sub-tabs:
 *   • Job Postings — create / edit / activate / archive / delete jobs
 *   • Applicants ATS — filter, view detail, change status, download docs
 *
 * Admin-only — protected by AdminGuard at the route layer.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Briefcase, Users, Plus, Search, Loader2, Edit, Archive, Trash2,
  CheckCircle2, ArchiveRestore, Download, Save, X, Filter,
} from 'lucide-react';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import { COUNTRIES } from '../../lib/countries';

const DEPARTMENTS = ['Operations', 'Sales', 'Valuations', 'Field'];
const STATUS_COLORS = {
  draft:    'bg-amber-100 text-amber-800',
  active:   'bg-emerald-100 text-emerald-800',
  archived: 'bg-slate-200 text-slate-700',
};
const APPLICANT_STATUS_COLORS = {
  applied:     'bg-slate-200 text-slate-800',
  reviewing:   'bg-sky-100 text-sky-800',
  shortlisted: 'bg-emerald-100 text-emerald-800',
  rejected:    'bg-rose-100 text-rose-800',
};

function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}

export default function AdminCareersConsole() {
  const { token } = useAuth();
  const [tab, setTab] = useState('jobs');

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4" data-testid="admin-careers-console">
      <header className="mb-4">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Briefcase className="h-6 w-6 text-sky-600" /> Careers Console
        </h1>
        <p className="text-sm text-slate-500">Manage job postings and applicants.</p>
      </header>

      <div className="flex gap-2 mb-4">
        <Button
          variant={tab === 'jobs' ? 'default' : 'outline'}
          onClick={() => setTab('jobs')}
          data-testid="tab-jobs"
        >
          <Briefcase className="h-4 w-4 mr-2" /> Job Postings
        </Button>
        <Button
          variant={tab === 'applicants' ? 'default' : 'outline'}
          onClick={() => setTab('applicants')}
          data-testid="tab-applicants"
        >
          <Users className="h-4 w-4 mr-2" /> Applicants
        </Button>
      </div>

      {tab === 'jobs' ? <JobsTab token={token} /> : <ApplicantsTab token={token} />}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// JOBS TAB
// ═══════════════════════════════════════════════════════════════════════

function JobsTab({ token }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [creating, setCreating] = useState(false);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const r = await axios.get(`${API_BASE}/admin/careers/jobs`, {
        headers: authHeaders(token), params,
      });
      setJobs(r.data?.items || []);
    } catch (e) {
      toast.error('Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, search]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const handleActivate = async (id) => {
    try {
      await axios.post(`${API_BASE}/admin/careers/jobs/${id}/activate`, {}, {
        headers: authHeaders(token),
      });
      toast.success('Job activated');
      fetchJobs();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || 'Activation failed');
    }
  };

  const handleArchive = async (id) => {
    try {
      await axios.post(`${API_BASE}/admin/careers/jobs/${id}/archive`, {}, {
        headers: authHeaders(token),
      });
      toast.success('Job archived');
      fetchJobs();
    } catch {
      toast.error('Archive failed');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this draft job? This cannot be undone.')) return;
    try {
      await axios.delete(`${API_BASE}/admin/careers/jobs/${id}`, {
        headers: authHeaders(token),
      });
      toast.success('Job deleted');
      fetchJobs();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || 'Delete failed');
    }
  };

  return (
    <div className="space-y-4" data-testid="jobs-tab">
      <Card>
        <CardContent className="p-4 flex flex-wrap items-center gap-3">
          <Button
            onClick={() => setCreating(true)}
            className="bg-sky-600 hover:bg-sky-700"
            data-testid="create-job-btn"
          >
            <Plus className="h-4 w-4 mr-2" /> Create Job Posting
          </Button>
          <div className="flex items-center gap-2 ml-auto">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm bg-white"
              data-testid="job-status-filter"
            >
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
            <div className="relative">
              <Search className="absolute left-2 top-2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-8 w-56"
                data-testid="job-search-input"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-sky-600" />
        </div>
      )}

      {!loading && jobs.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center text-slate-500" data-testid="jobs-empty">
            No jobs match the current filters.
          </CardContent>
        </Card>
      )}

      {!loading && jobs.length > 0 && (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm" data-testid="jobs-table">
              <thead className="bg-slate-50 border-b text-left">
                <tr>
                  <th className="px-4 py-2">Title</th>
                  <th className="px-4 py-2">Dept</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Applicants</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id} className="border-b hover:bg-slate-50" data-testid={`job-row-${j.id}`}>
                    <td className="px-4 py-2 font-medium">{j.title}</td>
                    <td className="px-4 py-2 text-slate-600">{j.department}</td>
                    <td className="px-4 py-2">
                      <Badge className={STATUS_COLORS[j.status] || ''}>
                        {j.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">{j.applicants_count ?? 0}</td>
                    <td className="px-4 py-2 text-right space-x-1">
                      <Button
                        size="sm" variant="outline"
                        onClick={() => setEditingId(j.id)}
                        data-testid={`edit-job-${j.id}`}
                      >
                        <Edit className="h-3 w-3" />
                      </Button>
                      {j.status === 'draft' && (
                        <>
                          <Button
                            size="sm" variant="outline"
                            onClick={() => handleActivate(j.id)}
                            data-testid={`activate-job-${j.id}`}
                          >
                            <CheckCircle2 className="h-3 w-3" />
                          </Button>
                          <Button
                            size="sm" variant="outline"
                            onClick={() => handleDelete(j.id)}
                            className="text-rose-600"
                            data-testid={`delete-job-${j.id}`}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </>
                      )}
                      {j.status === 'active' && (
                        <Button
                          size="sm" variant="outline"
                          onClick={() => handleArchive(j.id)}
                          data-testid={`archive-job-${j.id}`}
                        >
                          <Archive className="h-3 w-3" />
                        </Button>
                      )}
                      {j.status === 'archived' && (
                        <Button
                          size="sm" variant="outline"
                          onClick={() => handleActivate(j.id)}
                          data-testid={`reactivate-job-${j.id}`}
                        >
                          <ArchiveRestore className="h-3 w-3" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {(creating || editingId) && (
        <JobEditDialog
          token={token}
          jobId={editingId}
          open
          onClose={() => { setCreating(false); setEditingId(null); }}
          onSaved={() => { setCreating(false); setEditingId(null); fetchJobs(); }}
        />
      )}
    </div>
  );
}


function JobEditDialog({ token, jobId, open, onClose, onSaved }) {
  const isNew = !jobId;
  const [form, setForm] = useState({
    title: '', title_fr: '', department: 'Operations', location: 'National',
    status: 'draft', description_en: '', description_fr: '',
    commission_range: '',
    required_inputs: {
      requires_cv: true, requires_cover_letter: false,
      requires_photos: false, requires_certifications: false,
      custom_text_fields: [], custom_date_fields: [],
    },
  });
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isNew) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/admin/careers/jobs`, {
          headers: authHeaders(token), params: { limit: 100 },
        });
        const found = (r.data?.items || []).find((j) => j.id === jobId);
        if (found && !cancelled) {
          setForm({
            title:           found.title || '',
            title_fr:        found.title_fr || '',
            department:      found.department || 'Operations',
            location:        found.location || 'National',
            status:          found.status || 'draft',
            description_en:  found.description_en || '',
            description_fr:  found.description_fr || '',
            commission_range: found.commission_range || '',
            required_inputs: {
              requires_cv:             !!found.required_inputs?.requires_cv,
              requires_cover_letter:   !!found.required_inputs?.requires_cover_letter,
              requires_photos:         !!found.required_inputs?.requires_photos,
              requires_certifications: !!found.required_inputs?.requires_certifications,
              custom_text_fields:      found.required_inputs?.custom_text_fields || [],
              custom_date_fields:      found.required_inputs?.custom_date_fields || [],
            },
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [jobId, isNew, token]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (isNew) {
        await axios.post(`${API_BASE}/admin/careers/jobs`, form, {
          headers: authHeaders(token),
        });
        toast.success('Draft saved');
      } else {
        await axios.patch(`${API_BASE}/admin/careers/jobs/${jobId}`, form, {
          headers: authHeaders(token),
        });
        toast.success('Saved');
      }
      onSaved();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const addCustomText = () => {
    const label = window.prompt('Question label:');
    if (label && label.trim()) {
      setForm({
        ...form,
        required_inputs: {
          ...form.required_inputs,
          custom_text_fields: [...form.required_inputs.custom_text_fields, label.trim()],
        },
      });
    }
  };

  const addCustomDate = () => {
    const label = window.prompt('Date field label:');
    if (label && label.trim()) {
      setForm({
        ...form,
        required_inputs: {
          ...form.required_inputs,
          custom_date_fields: [...form.required_inputs.custom_date_fields, label.trim()],
        },
      });
    }
  };

  const removeCustomText = (idx) => {
    const next = [...form.required_inputs.custom_text_fields];
    next.splice(idx, 1);
    setForm({ ...form, required_inputs: { ...form.required_inputs, custom_text_fields: next } });
  };
  const removeCustomDate = (idx) => {
    const next = [...form.required_inputs.custom_date_fields];
    next.splice(idx, 1);
    setForm({ ...form, required_inputs: { ...form.required_inputs, custom_date_fields: next } });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="job-edit-dialog">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Create Job Posting' : 'Edit Job Posting'}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-sky-600" /></div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Label>Job Title (EN)</Label>
                <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="edit-title-en" />
              </div>
              <div>
                <Label>Job Title (FR)</Label>
                <Input value={form.title_fr} onChange={(e) => setForm({ ...form, title_fr: e.target.value })} data-testid="edit-title-fr" />
              </div>
              <div>
                <Label>Department</Label>
                <select
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm bg-white"
                  data-testid="edit-department"
                >
                  {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div>
                <Label>Location</Label>
                <Input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} data-testid="edit-location" />
              </div>
              <div className="md:col-span-2">
                <Label>Commission Range</Label>
                <Input
                  value={form.commission_range}
                  onChange={(e) => setForm({ ...form, commission_range: e.target.value })}
                  placeholder="5% – 20% per transaction"
                  data-testid="edit-commission"
                />
              </div>
            </div>

            <div>
              <Label>Description (EN, markdown OK)</Label>
              <Textarea
                rows={6}
                value={form.description_en}
                onChange={(e) => setForm({ ...form, description_en: e.target.value })}
                data-testid="edit-description-en"
              />
            </div>
            <div>
              <Label>Description (FR, markdown OK)</Label>
              <Textarea
                rows={6}
                value={form.description_fr}
                onChange={(e) => setForm({ ...form, description_fr: e.target.value })}
                data-testid="edit-description-fr"
              />
            </div>

            <div>
              <h3 className="text-sm font-bold mb-2">Application Requirements</h3>
              {[
                ['requires_cv', 'Require CV Upload'],
                ['requires_cover_letter', 'Require Cover Letter'],
                ['requires_photos', 'Require Portfolio Photos'],
                ['requires_certifications', 'Require Certifications'],
              ].map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 text-sm py-1">
                  <input
                    type="checkbox"
                    checked={!!form.required_inputs[key]}
                    onChange={(e) => setForm({
                      ...form,
                      required_inputs: { ...form.required_inputs, [key]: e.target.checked },
                    })}
                    data-testid={`toggle-${key}`}
                  />
                  {label}
                </label>
              ))}
            </div>

            <div>
              <h3 className="text-sm font-bold mb-2">Custom Questions</h3>
              <div className="space-y-1">
                {form.required_inputs.custom_text_fields.map((q, i) => (
                  <div key={`t${i}`} className="flex items-center gap-2 text-sm">
                    <span className="flex-1 truncate">📝 {q}</span>
                    <Button size="sm" variant="ghost" onClick={() => removeCustomText(i)}>
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
                {form.required_inputs.custom_date_fields.map((q, i) => (
                  <div key={`d${i}`} className="flex items-center gap-2 text-sm">
                    <span className="flex-1 truncate">📅 {q}</span>
                    <Button size="sm" variant="ghost" onClick={() => removeCustomDate(i)}>
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-2">
                <Button size="sm" variant="outline" onClick={addCustomText} data-testid="add-custom-text">
                  <Plus className="h-3 w-3 mr-1" /> Add Question
                </Button>
                <Button size="sm" variant="outline" onClick={addCustomDate} data-testid="add-custom-date">
                  <Plus className="h-3 w-3 mr-1" /> Add Date Field
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} className="bg-sky-600 hover:bg-sky-700" data-testid="save-job-btn">
                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                Save Draft
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// APPLICANTS TAB
// ═══════════════════════════════════════════════════════════════════════

function ApplicantsTab({ token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    job_offer_id: '', status: '', country: '', province: '', search: '',
  });
  const [selectedId, setSelectedId] = useState(null);
  const [jobs, setJobs] = useState([]);

  const fetchApplicants = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const r = await axios.get(`${API_BASE}/admin/careers/applicants`, {
        headers: authHeaders(token), params,
      });
      setItems(r.data?.items || []);
    } catch {
      toast.error('Failed to load applicants');
    } finally {
      setLoading(false);
    }
  }, [token, filters]);

  useEffect(() => { fetchApplicants(); }, [fetchApplicants]);

  useEffect(() => {
    axios.get(`${API_BASE}/admin/careers/jobs`, {
      headers: authHeaders(token), params: { limit: 100 },
    }).then((r) => setJobs(r.data?.items || [])).catch(() => undefined);
  }, [token]);

  return (
    <div className="space-y-4" data-testid="applicants-tab">
      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-5 gap-2">
          <select
            value={filters.job_offer_id}
            onChange={(e) => setFilters({ ...filters, job_offer_id: e.target.value })}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm bg-white"
            data-testid="filter-job"
          >
            <option value="">All Jobs</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm bg-white"
            data-testid="filter-status"
          >
            <option value="">All Statuses</option>
            <option value="applied">Applied</option>
            <option value="reviewing">Reviewing</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="rejected">Rejected</option>
          </select>
          <select
            value={filters.country}
            onChange={(e) => setFilters({ ...filters, country: e.target.value, province: '' })}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm bg-white"
            data-testid="filter-country"
          >
            <option value="">All Countries</option>
            {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <Input
            placeholder="Province/State (e.g. QC, TX)"
            value={filters.province}
            onChange={(e) => setFilters({ ...filters, province: e.target.value })}
            data-testid="filter-province"
          />
          <Input
            placeholder="Name or email…"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            data-testid="filter-search"
          />
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-sky-600" />
        </div>
      )}

      {!loading && items.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center text-slate-500" data-testid="applicants-empty">
            No applicants match the filters.
          </CardContent>
        </Card>
      )}

      {!loading && items.length > 0 && (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm" data-testid="applicants-table">
              <thead className="bg-slate-50 border-b text-left">
                <tr>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Job</th>
                  <th className="px-4 py-2">Country / Region</th>
                  <th className="px-4 py-2">AI</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Applied</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} className="border-b hover:bg-slate-50" data-testid={`applicant-row-${a.id}`}>
                    <td className="px-4 py-2 font-medium">{a.first_name} {a.last_name}</td>
                    <td className="px-4 py-2 text-slate-600">{a.job_title}</td>
                    <td className="px-4 py-2 text-xs">
                      <span data-testid="row-country">{a.country || '—'}</span>
                      {(a.province || a.state) && (
                        <span className="text-slate-400"> · {a.province || a.state}</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <RecommendationBadge rec={a.screening?.recommendation} />
                    </td>
                    <td className="px-4 py-2">
                      <Badge className={APPLICANT_STATUS_COLORS[a.status] || ''}>{a.status}</Badge>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500">
                      {a.applied_at ? new Date(a.applied_at).toLocaleDateString('en-CA') : ''}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Button
                        size="sm" variant="outline"
                        onClick={() => setSelectedId(a.id)}
                        data-testid={`view-applicant-${a.id}`}
                      >
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {selectedId && (
        <ApplicantDetailDialog
          token={token}
          applicantId={selectedId}
          open
          onClose={() => setSelectedId(null)}
          onUpdated={fetchApplicants}
        />
      )}
    </div>
  );
}


function RecommendationBadge({ rec }) {
  if (!rec) return <span className="text-slate-300 text-xs">—</span>;
  const colors = {
    Yes:   'bg-emerald-100 text-emerald-800',
    Maybe: 'bg-amber-100 text-amber-800',
    No:    'bg-rose-100 text-rose-800',
  };
  return (
    <Badge className={colors[rec] || 'bg-slate-100 text-slate-800'} data-testid={`ai-rec-${rec.toLowerCase()}`}>
      AI: {rec}
    </Badge>
  );
}


function ApplicantDetailDialog({ token, applicantId, open, onClose, onUpdated }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [editingSummary, setEditingSummary] = useState(false);
  const [summaryDraft, setSummaryDraft] = useState('');
  const [savingSummary, setSavingSummary] = useState(false);
  const [rescreening, setRescreening] = useState(false);

  const loadApplicant = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/careers/applicants/${applicantId}`, {
        headers: authHeaders(token),
      });
      setData(r.data);
      setStatus(r.data?.status || 'applied');
      setNotes(r.data?.admin_notes || '');
      setSummaryDraft(r.data?.screening?.summary || '');
    } finally {
      setLoading(false);
    }
  }, [applicantId, token]);

  useEffect(() => {
    let cancelled = false;
    loadApplicant();
    return () => { cancelled = true; };
  }, [loadApplicant]);

  // Build a CV preview blob URL (PDF only) — runs once when the dialog
  // mounts; revoked on unmount to avoid leaks.
  useEffect(() => {
    if (!data?.attachments?.cv_url) return undefined;
    const fname = data.attachments.cv_url;
    if (!fname.toLowerCase().endsWith('.pdf')) return undefined;
    let blobUrl;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API_BASE}/admin/careers/applicants/${applicantId}/attachments/${encodeURIComponent(fname)}?inline=1`,
          { headers: authHeaders(token), responseType: 'blob' },
        );
        if (cancelled) return;
        blobUrl = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
        setPreviewUrl(blobUrl);
      } catch {
        // silent — admin can still download
      }
    })();
    return () => {
      cancelled = true;
      if (blobUrl) window.URL.revokeObjectURL(blobUrl);
    };
  }, [applicantId, data?.attachments?.cv_url, token]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.patch(`${API_BASE}/admin/careers/applicants/${applicantId}/status`, {
        status, admin_notes: notes,
      }, { headers: authHeaders(token) });
      toast.success('Saved');
      onUpdated?.();
      onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSummary = async () => {
    setSavingSummary(true);
    try {
      await axios.patch(`${API_BASE}/admin/careers/applicants/${applicantId}/screening/summary`, {
        summary: summaryDraft, pin: true,
      }, { headers: authHeaders(token) });
      toast.success('Summary updated');
      await loadApplicant();
      setEditingSummary(false);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || 'Save failed');
    } finally {
      setSavingSummary(false);
    }
  };

  const handleRescreen = async () => {
    setRescreening(true);
    try {
      await axios.post(`${API_BASE}/admin/careers/applicants/${applicantId}/screen`, {}, {
        headers: authHeaders(token),
      });
      toast.success('Re-screening started');
      // Wait briefly then reload so the UI shows the fresh values.
      setTimeout(() => loadApplicant(), 3000);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || 'Re-screen failed');
    } finally {
      setRescreening(false);
    }
  };

  const downloadHref = (filename) => async () => {
    try {
      const r = await axios.get(
        `${API_BASE}/admin/careers/applicants/${applicantId}/attachments/${encodeURIComponent(filename)}`,
        { headers: authHeaders(token), responseType: 'blob' },
      );
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('Download failed');
    }
  };

  const screening = data?.screening || {};
  const hasPdf = data?.attachments?.cv_url && data.attachments.cv_url.toLowerCase().endsWith('.pdf');

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-6xl max-h-[92vh] overflow-y-auto" data-testid="applicant-detail-dialog">
        <DialogHeader>
          <DialogTitle>{data ? `${data.first_name} ${data.last_name}` : 'Applicant'}</DialogTitle>
        </DialogHeader>
        {loading && <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-sky-600" /></div>}
        {data && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-sm">
            {/* ── LEFT: AI summary + applicant data + status ── */}
            <div className="lg:col-span-5 space-y-4">
              {/* AI Screening panel */}
              <Card className="border-2 border-sky-100 bg-sky-50/40" data-testid="ai-screening-panel">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold flex items-center gap-2">
                      🤖 Claude Auto-Screening
                      <RecommendationBadge rec={screening.recommendation} />
                    </h3>
                    <Button
                      size="sm" variant="outline" onClick={handleRescreen}
                      disabled={rescreening || !data.attachments?.cv_url}
                      data-testid="rescreen-btn"
                    >
                      {rescreening ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : '↻'}
                      Re-screen
                    </Button>
                  </div>
                  {screening.status === 'pending' && (
                    <p className="text-xs text-amber-700 italic" data-testid="ai-pending">
                      ⏳ Screening in progress…
                    </p>
                  )}
                  {screening.status === 'skipped' && (
                    <p className="text-xs text-slate-500 italic" data-testid="ai-skipped">
                      No CV uploaded — screening skipped.
                    </p>
                  )}
                  {screening.status === 'failed' && (
                    <p className="text-xs text-rose-700" data-testid="ai-failed">
                      Screening failed: {screening.error || 'unknown error'}
                    </p>
                  )}
                  {screening.status === 'ok' && (
                    <div className="space-y-2">
                      <div>
                        <div className="flex items-center justify-between">
                          <Label className="text-xs">1-line summary</Label>
                          {!editingSummary && (
                            <Button
                              size="sm" variant="ghost"
                              onClick={() => { setSummaryDraft(screening.summary || ''); setEditingSummary(true); }}
                              data-testid="edit-summary-btn"
                            >
                              <Edit className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                        {editingSummary ? (
                          <div className="space-y-2 mt-1">
                            <Textarea
                              value={summaryDraft}
                              onChange={(e) => setSummaryDraft(e.target.value.slice(0, 220))}
                              rows={3}
                              className="text-xs"
                              data-testid="edit-summary-textarea"
                            />
                            <div className="flex justify-end gap-2">
                              <Button size="sm" variant="outline" onClick={() => setEditingSummary(false)}>Cancel</Button>
                              <Button
                                size="sm" onClick={handleSaveSummary}
                                disabled={savingSummary || !summaryDraft.trim()}
                                className="bg-sky-600 hover:bg-sky-700"
                                data-testid="save-summary-btn"
                              >
                                {savingSummary ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Save className="h-3 w-3 mr-1" />}
                                Pin Edit
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm leading-relaxed mt-1" data-testid="ai-summary">
                            {screening.summary || '(empty)'}
                          </p>
                        )}
                        {screening.summary_edited && (
                          <p className="text-[10px] text-amber-700 italic mt-1" data-testid="ai-summary-edited-tag">
                            ✏️ Admin-edited · LLM original below
                          </p>
                        )}
                      </div>
                      {screening.summary_edited && screening.llm_summary && (
                        <div className="text-[11px] text-slate-500 bg-white rounded p-2 border border-slate-200">
                          <span className="font-bold">LLM original:</span> {screening.llm_summary}
                        </div>
                      )}
                      {(screening.key_signals || []).length > 0 && (
                        <div data-testid="ai-key-signals">
                          <Label className="text-xs">Key signals</Label>
                          <ul className="list-disc list-inside text-xs space-y-0.5 mt-1">
                            {screening.key_signals.map((sig, i) => <li key={i}>{sig}</li>)}
                          </ul>
                        </div>
                      )}
                      <p className="text-[10px] text-slate-400 italic">
                        Model: {screening.model} · {screening.completed_at}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Applicant data */}
              <Card>
                <CardContent className="p-4 space-y-2 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <div><span className="text-slate-500">Job:</span> <strong>{data.job?.title}</strong></div>
                    <div><span className="text-slate-500">Email:</span> {data.email}</div>
                    <div><span className="text-slate-500">Phone:</span> {data.phone}</div>
                    <div data-testid="detail-country"><span className="text-slate-500">Country:</span> {data.country || '—'}</div>
                    {data.province && <div data-testid="detail-province"><span className="text-slate-500">Province:</span> {data.province}</div>}
                    {data.state && <div data-testid="detail-state"><span className="text-slate-500">State:</span> {data.state}</div>}
                    <div><span className="text-slate-500">Language:</span> {data.preferred_language}</div>
                    <div><span className="text-slate-500">Applied:</span> {data.applied_at}</div>
                  </div>

                  {Object.keys(data.custom_responses || {}).length > 0 && (
                    <div className="pt-2 border-t border-slate-100">
                      <h3 className="text-xs font-bold mb-1">Custom Responses</h3>
                      {Object.entries(data.custom_responses).map(([k, v]) => (
                        <div key={k}>
                          <span className="text-slate-500">{k}:</span> {String(v)}
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="pt-2 border-t border-slate-100">
                    <h3 className="text-xs font-bold mb-1">Attachments</h3>
                    <ul className="space-y-1">
                      {data.attachments?.cv_url && (
                        <li className="flex items-center gap-2">
                          <span>📄 CV: {data.attachments.cv_url}</span>
                          <Button size="sm" variant="outline" onClick={downloadHref(data.attachments.cv_url)} data-testid="download-cv">
                            <Download className="h-3 w-3 mr-1" /> Download
                          </Button>
                        </li>
                      )}
                      {data.attachments?.cover_letter_url && (
                        <li className="flex items-center gap-2">
                          <span>📄 Cover: {data.attachments.cover_letter_url}</span>
                          <Button size="sm" variant="outline" onClick={downloadHref(data.attachments.cover_letter_url)} data-testid="download-cover">
                            <Download className="h-3 w-3 mr-1" /> Download
                          </Button>
                        </li>
                      )}
                      {(data.attachments?.photos || []).map((p) => (
                        <li key={p} className="flex items-center gap-2">
                          <span>📸 {p}</span>
                          <Button size="sm" variant="outline" onClick={downloadHref(p)}>
                            <Download className="h-3 w-3 mr-1" /> Download
                          </Button>
                        </li>
                      ))}
                      {(data.attachments?.certifications || []).map((c) => (
                        <li key={c} className="flex items-center gap-2">
                          <span>🏆 {c}</span>
                          <Button size="sm" variant="outline" onClick={downloadHref(c)}>
                            <Download className="h-3 w-3 mr-1" /> Download
                          </Button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-4 space-y-2">
                  <div>
                    <Label>Status</Label>
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm bg-white"
                      data-testid="applicant-status-select"
                    >
                      <option value="applied">Applied</option>
                      <option value="reviewing">Reviewing</option>
                      <option value="shortlisted">Shortlisted</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>
                  <div>
                    <Label>Admin Notes</Label>
                    <Textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      data-testid="applicant-notes-textarea"
                    />
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleSave} disabled={saving} className="bg-sky-600 hover:bg-sky-700" data-testid="save-applicant-btn">
                      {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                      Save
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* ── RIGHT: inline PDF preview ── */}
            <div className="lg:col-span-7" data-testid="cv-preview-pane">
              <Card className="h-full">
                <CardContent className="p-3 h-full">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold">📄 CV Preview</h3>
                    {hasPdf && previewUrl && (
                      <a
                        href={previewUrl} target="_blank" rel="noopener noreferrer"
                        className="text-xs text-sky-600 hover:underline"
                        data-testid="open-pdf-new-tab"
                      >
                        Open in new tab ↗
                      </a>
                    )}
                  </div>
                  {!data.attachments?.cv_url && (
                    <div className="h-[60vh] flex items-center justify-center text-slate-400 border border-dashed rounded" data-testid="no-cv-placeholder">
                      No CV uploaded
                    </div>
                  )}
                  {data.attachments?.cv_url && !hasPdf && (
                    <div className="h-[60vh] flex flex-col items-center justify-center text-slate-500 border border-dashed rounded p-6 text-center" data-testid="non-pdf-placeholder">
                      <p className="text-sm">CV is a DOCX file — inline preview is PDF-only.</p>
                      <Button
                        size="sm" variant="outline" className="mt-3"
                        onClick={downloadHref(data.attachments.cv_url)}
                      >
                        <Download className="h-3 w-3 mr-1" /> Download to read
                      </Button>
                    </div>
                  )}
                  {hasPdf && !previewUrl && (
                    <div className="h-[60vh] flex items-center justify-center" data-testid="pdf-loading">
                      <Loader2 className="h-6 w-6 animate-spin text-sky-600" />
                    </div>
                  )}
                  {hasPdf && previewUrl && (
                    <iframe
                      src={previewUrl}
                      title="CV preview"
                      className="w-full h-[70vh] border rounded"
                      data-testid="cv-iframe"
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
