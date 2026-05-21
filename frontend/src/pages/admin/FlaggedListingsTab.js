import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import { Shield, AlertCircle, CheckCircle, XCircle, Search, RefreshCw, Eye } from 'lucide-react';

const API = API_BASE;

/**
 * FEATURE PATCH v9 / Feature 3 — Admin Flagged Listings Review Queue
 */
const FlaggedListingsTab = () => {
  const { token } = useAuth();
  const [status, setStatus] = useState('pending');
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [actionModal, setActionModal] = useState({ open: false, mode: null, row: null, note: '', overrideCategory: '' });
  // Phase 6.0 / Repair 3 — Admin preview modal state
  const [previewModal, setPreviewModal] = useState({ open: false, row: null, listing: null, loading: false, error: null });
  const queryParamListingId = (() => {
    try {
      return new URLSearchParams(window.location.search).get('listing_id');
    } catch { return null; }
  })();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/listing-reviews?status=${status}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRows(r.data?.rows || []);
      setTotal(r.data?.total || 0);
    } catch (e) {
      toast.error('Failed to load flagged listings');
    } finally {
      setLoading(false);
    }
  }, [status, token]);

  useEffect(() => { load(); }, [load]);

  // Phase 6.0 / Repair 2 — When the admin clicks a notification with
  // ?listing_id=XYZ, auto-scroll to and highlight the matching row.
  useEffect(() => {
    if (!queryParamListingId || rows.length === 0) return;
    const match = rows.find((r) => r.listing_id === queryParamListingId);
    if (match) {
      setTimeout(() => {
        try {
          document.querySelector(`[data-testid="review-row-${match.id}"]`)?.scrollIntoView({
            behavior: 'smooth', block: 'center',
          });
        } catch { /* noop */ }
      }, 200);
    }
  }, [queryParamListingId, rows]);

  const openPreview = async (row) => {
    setPreviewModal({ open: true, row, listing: null, loading: true, error: null });
    try {
      // Try to fetch the actual listing (single-item or multi-item)
      let listing = null;
      const isSynthetic = (row.listing_id || '').startsWith('vehicle-block::');
      if (!isSynthetic && row.listing_id) {
        try {
          const r = await axios.get(`${API}/listings/${row.listing_id}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          listing = r.data;
        } catch (e) {
          if (e?.response?.status !== 404) throw e;
          // Try multi-item
          try {
            const r2 = await axios.get(`${API}/multi-item-listings/${row.listing_id}`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            listing = r2.data;
          } catch { /* fall through */ }
        }
      }
      setPreviewModal({ open: true, row, listing, loading: false, error: null });
    } catch (e) {
      setPreviewModal({ open: true, row, listing: null, loading: false, error: e?.response?.data?.detail || e.message });
    }
  };

  const closePreview = () => setPreviewModal({ open: false, row: null, listing: null, loading: false, error: null });

  const filteredRows = rows.filter((r) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (r.listing_title || '').toLowerCase().includes(q) ||
      (r.seller_category || '').toLowerCase().includes(q) ||
      (r.suggested_category || '').toLowerCase().includes(q) ||
      (r.listing_id || '').toLowerCase().includes(q)
    );
  });

  const openAction = (mode, row) => {
    setActionModal({ open: true, mode, row, note: '', overrideCategory: row?.suggested_category || '' });
  };

  const submitAction = async () => {
    const { mode, row, note, overrideCategory } = actionModal;
    // Phase 6.0 / Task 1 — Call the alias route keyed by listing_id so admins
    // can approve/reject without needing the review_id surface.
    const url = `${API}/admin/ai-review/listings/${row.listing_id}/${mode}`;
    const body = { admin_note: note || '' };
    if (mode === 'approve' && overrideCategory) {
      body.override_category = overrideCategory.trim();
    }
    try {
      await axios.post(url, body, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(mode === 'approve' ? 'Listing approved' : 'Listing rejected');
      setActionModal({ open: false, mode: null, row: null, note: '', overrideCategory: '' });
      load();
    } catch (e) {
      // Phase 6.0 / Task 1 — graceful 404 / network error handling.
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      const message = typeof detail === 'string'
        ? detail
        : (detail?.message_en || detail?.message_fr || e?.message || 'Action failed');
      toast.error(`${status ? `(${status}) ` : ''}${message}`);
      console.error('[FlaggedListingsTab.submitAction] failed:', e);
    }
  };

  const renderStatusBadge = (s) => {
    if (s === 'pending') return <Badge className="bg-amber-100 text-amber-900 border border-amber-200">Pending</Badge>;
    if (s === 'approved') return <Badge className="bg-emerald-100 text-emerald-900 border border-emerald-200">Approved</Badge>;
    if (s === 'rejected') return <Badge className="bg-rose-100 text-rose-900 border border-rose-200">Rejected</Badge>;
    if (s === 'withdrawn') return <Badge variant="outline">Withdrawn</Badge>;
    if (s === 'resubmitted') return <Badge className="bg-cyan-100 text-cyan-900 border border-cyan-200">Resubmitted</Badge>;
    return <Badge variant="outline">{s}</Badge>;
  };

  return (
    <div className="space-y-6" data-testid="flagged-listings-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-amber-600" /> Flagged Listings (AI Review Queue)
          </h2>
          <p className="text-muted-foreground text-sm">
            Listings flagged by the AI watchdog for category mismatch. Review and approve / reject.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} data-testid="refresh-reviews-btn">
          <RefreshCw className="h-4 w-4 mr-1" /> Refresh
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          { id: 'pending',     label: 'Pending' },
          { id: 'approved',    label: 'Approved' },
          { id: 'rejected',    label: 'Rejected' },
          { id: 'withdrawn',   label: 'Withdrawn' },
          { id: 'resubmitted', label: 'Resubmitted' },
          { id: 'all',         label: 'All' },
        ].map((t) => (
          <Button
            key={t.id}
            variant={status === t.id ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatus(t.id)}
            className={status === t.id ? 'gradient-button text-white border-0' : ''}
            data-testid={`filter-${t.id}-btn`}
          >
            {t.label}
          </Button>
        ))}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search by title, category or listing ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
          data-testid="search-reviews-input"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{filteredRows.length} of {total} flagged listings</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-amber-500 border-t-transparent"></div>
            </div>
          ) : filteredRows.length === 0 ? (
            <p className="text-center text-muted-foreground py-8" data-testid="no-reviews-empty-state">
              No flagged listings in this state. <span className="text-emerald-600">All caught up!</span>
            </p>
          ) : (
            <div className="space-y-3">
              {filteredRows.map((r) => (
                <div key={r.id} className="p-4 border rounded-lg hover:bg-accent/30 transition-colors" data-testid={`review-row-${r.id}`}>
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex-1 min-w-[260px]">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        <h3 className="font-semibold">{r.listing_title || '(no title)'}</h3>
                        {renderStatusBadge(r.status)}
                        {r.listing_type === 'multi' && <Badge variant="secondary">Multi-item</Badge>}
                      </div>
                      <div className="text-sm space-y-1">
                        <div className="flex gap-2 flex-wrap items-center">
                          <span className="text-muted-foreground">Seller's category:</span>
                          <Badge variant="outline">{r.seller_category || '—'}</Badge>
                          <span className="text-muted-foreground mx-1">→</span>
                          <span className="text-muted-foreground">AI suggested:</span>
                          <Badge className="bg-amber-100 text-amber-900 border border-amber-200">
                            {r.suggested_category || '—'}
                          </Badge>
                          {typeof r.ai_confidence === 'number' && (
                            <span className="text-xs text-muted-foreground">({Math.round((r.ai_confidence || 0) * 100)}% confidence)</span>
                          )}
                        </div>
                        {(r.ai_reason_en || r.ai_reason_fr) && (
                          <div className="text-xs text-slate-600 italic">
                            {r.ai_reason_en || r.ai_reason_fr}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground">
                          Flagged {r.created_at ? new Date(r.created_at).toLocaleString() : '—'} · Listing ID: <code className="text-[10px]">{r.listing_id}</code>
                        </div>
                        {r.admin_note && (
                          <div className="text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded mt-1">
                            <strong>Admin note:</strong> {r.admin_note}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col lg:flex-row flex-wrap gap-2 w-full lg:w-auto">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openPreview(r)}
                        data-testid={`view-listing-${r.id}`}
                        className="w-full lg:w-auto"
                      >
                        <Eye className="h-4 w-4 mr-1" /> View
                      </Button>
                      {r.status === 'pending' && (
                        <>
                          <Button
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-700 text-white w-full lg:w-auto"
                            onClick={() => openAction('approve', r)}
                            data-testid={`approve-${r.id}`}
                          >
                            <CheckCircle className="h-4 w-4 mr-1" /> Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => openAction('reject', r)}
                            data-testid={`reject-${r.id}`}
                            className="w-full lg:w-auto"
                          >
                            <XCircle className="h-4 w-4 mr-1" /> Reject
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action confirmation modal */}
      <Dialog open={actionModal.open} onOpenChange={(v) => !v && setActionModal({ open: false, mode: null, row: null, note: '', overrideCategory: '' })}>
        <DialogContent className="max-w-lg" data-testid="review-action-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {actionModal.mode === 'approve' ? (
                <><CheckCircle className="h-5 w-5 text-emerald-600" /> Approve Listing</>
              ) : (
                <><AlertCircle className="h-5 w-5 text-rose-600" /> Reject Listing</>
              )}
            </DialogTitle>
            <DialogDescription>
              {actionModal.row?.listing_title}
              <span className="block text-[11px] mt-1">
                The seller will receive a bilingual email notification (EN/FR).
              </span>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {actionModal.mode === 'approve' && (
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Override category (optional)</label>
                <Input
                  value={actionModal.overrideCategory}
                  onChange={(e) => setActionModal((m) => ({ ...m, overrideCategory: e.target.value }))}
                  placeholder={actionModal.row?.suggested_category || 'Leave blank to keep current'}
                  data-testid="override-category-input"
                />
                <p className="text-[11px] text-muted-foreground">If set, the listing's category will be updated on approval.</p>
              </div>
            )}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Admin note (sent to seller)</label>
              <Textarea
                rows={3}
                value={actionModal.note}
                onChange={(e) => setActionModal((m) => ({ ...m, note: e.target.value }))}
                placeholder={actionModal.mode === 'approve' ? 'Thanks — approved.' : 'Please correct the category and resubmit.'}
                data-testid="admin-note-input"
                maxLength={1000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionModal({ open: false, mode: null, row: null, note: '', overrideCategory: '' })}>
              Cancel
            </Button>
            <Button
              className={actionModal.mode === 'approve' ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : 'bg-rose-600 hover:bg-rose-700 text-white'}
              onClick={submitAction}
              data-testid="confirm-action-btn"
            >
              {actionModal.mode === 'approve' ? 'Approve' : 'Reject'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Phase 6.0 / Repair 3 — Admin preview modal (fully authenticated, no public 404) */}
      <Dialog open={previewModal.open} onOpenChange={(v) => !v && closePreview()}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="admin-preview-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-cyan-600" /> Admin Preview
            </DialogTitle>
            <DialogDescription>
              Full snapshot of the original submission — never routes to the public marketplace.
            </DialogDescription>
          </DialogHeader>

          {previewModal.loading ? (
            <div className="flex justify-center py-10">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-cyan-500 border-t-transparent"></div>
            </div>
          ) : (
            <div className="flex flex-col lg:flex-row gap-4 w-full" data-testid="admin-preview-body">
              {/* Left column — original submission */}
              <div className="flex-1 min-w-0 space-y-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">Title</p>
                  <p className="font-semibold text-base" data-testid="preview-title">
                    {previewModal.listing?.title || previewModal.row?.listing_title || '(no title)'}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">Description</p>
                  <p className="text-sm whitespace-pre-wrap bg-slate-50 rounded-md p-3 border border-slate-200" data-testid="preview-description">
                    {previewModal.listing?.description || previewModal.row?.description || '(no description provided)'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 text-sm">
                  <div>
                    <p className="text-[11px] uppercase text-muted-foreground font-semibold">Starting Price</p>
                    <p className="font-semibold text-emerald-700" data-testid="preview-price">
                      {previewModal.listing?.starting_price != null
                        ? `${(previewModal.listing.currency || 'CAD')} $${Number(previewModal.listing.starting_price).toLocaleString()}`
                        : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] uppercase text-muted-foreground font-semibold">Listing ID</p>
                    <code className="text-[11px]" data-testid="preview-listing-id">{previewModal.row?.listing_id}</code>
                  </div>
                  <div>
                    <p className="text-[11px] uppercase text-muted-foreground font-semibold">Seller</p>
                    <p className="text-sm" data-testid="preview-seller">
                      {previewModal.row?.seller_name || previewModal.row?.seller_email || previewModal.listing?.seller_id || '—'}
                    </p>
                  </div>
                </div>

                {/* Images */}
                {Array.isArray(previewModal.listing?.images) && previewModal.listing.images.length > 0 && (
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">
                      Images ({previewModal.listing.images.length})
                    </p>
                    <div className="flex flex-wrap gap-2" data-testid="preview-images">
                      {previewModal.listing.images.slice(0, 6).map((src, idx) => (
                        // eslint-disable-next-line jsx-a11y/img-redundant-alt
                        <img
                          key={idx}
                          src={src}
                          alt={`Image ${idx + 1}`}
                          className="w-24 h-24 object-cover rounded-md border border-slate-200"
                        />
                      ))}
                    </div>
                  </div>
                )}

                {!previewModal.listing && (
                  <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900" data-testid="preview-no-listing">
                    <strong>Pre-creation request</strong> — the seller hit the vehicle-compliance block before the listing was created. Only the snapshot data on the right is available.
                  </div>
                )}
              </div>

              {/* Right column — AI flags */}
              <div className="w-full lg:w-72 flex-shrink-0 space-y-3">
                <div className="rounded-md bg-amber-50 border border-amber-300 p-3" data-testid="preview-categories">
                  <p className="text-[11px] uppercase tracking-wide font-semibold text-amber-900 mb-2">Category Mismatch</p>
                  <div className="space-y-2">
                    <div>
                      <p className="text-[10px] uppercase text-muted-foreground">Seller's category</p>
                      <Badge variant="outline" className="text-[11px]">
                        {previewModal.row?.seller_category || '—'}
                      </Badge>
                    </div>
                    <div className="text-center text-muted-foreground text-xs">↓</div>
                    <div>
                      <p className="text-[10px] uppercase text-muted-foreground">AI suggested</p>
                      <Badge className="bg-amber-200 text-amber-900 border border-amber-300 text-[11px]">
                        {previewModal.row?.suggested_category || '—'}
                      </Badge>
                    </div>
                  </div>
                  {typeof previewModal.row?.ai_confidence === 'number' && (
                    <p className="text-[10px] text-amber-700 mt-2">
                      Confidence: {Math.round((previewModal.row.ai_confidence || 0) * 100)}%
                    </p>
                  )}
                </div>

                {Array.isArray(previewModal.row?.detected_signals) && previewModal.row.detected_signals.length > 0 && (
                  <div className="rounded-md bg-rose-50 border border-rose-300 p-3" data-testid="preview-detected-signals">
                    <p className="text-[11px] uppercase tracking-wide font-semibold text-rose-900 mb-2">
                      🚨 Triggered Keywords
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {previewModal.row.detected_signals.map((sig, idx) => (
                        <Badge
                          key={idx}
                          className="bg-rose-200 text-rose-900 border border-rose-400 font-mono text-[10px]"
                        >
                          {sig}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {(previewModal.row?.ai_reason_en || previewModal.row?.ai_reason_fr) && (
                  <div className="rounded-md bg-slate-50 border border-slate-200 p-3 text-[11px] text-slate-700">
                    <p className="font-semibold uppercase text-muted-foreground mb-1">AI Reason</p>
                    <p>{previewModal.row.ai_reason_en || previewModal.row.ai_reason_fr}</p>
                  </div>
                )}

                {previewModal.error && (
                  <div className="rounded-md bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
                    {String(previewModal.error)}
                  </div>
                )}
              </div>
            </div>
          )}

          <DialogFooter className="mt-4 flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={closePreview} className="w-full sm:w-auto" data-testid="preview-close-btn">
              Close
            </Button>
            {previewModal.row?.status === 'pending' && (
              <>
                <Button
                  className="bg-emerald-600 hover:bg-emerald-700 text-white w-full sm:w-auto"
                  onClick={() => { const row = previewModal.row; closePreview(); openAction('approve', row); }}
                  data-testid="preview-approve-btn"
                >
                  <CheckCircle className="h-4 w-4 mr-1" /> Approve
                </Button>
                <Button
                  variant="destructive"
                  className="w-full sm:w-auto"
                  onClick={() => { const row = previewModal.row; closePreview(); openAction('reject', row); }}
                  data-testid="preview-reject-btn"
                >
                  <XCircle className="h-4 w-4 mr-1" /> Reject
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
};

export default FlaggedListingsTab;
