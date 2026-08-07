/**
 * BulkImportPage — iter444
 *
 * 5-step Partner CSV bulk-import wizard:
 *   1. Download template
 *   2. Upload CSV → preview
 *   3. Review + inline-edit + bilingual errors
 *   4. Photo Studio (auto-match + manual assign)
 *   5. Publish (batch or per-draft; publish-gated on ≥1 photo)
 *
 * Every imported row is written as `status="draft"` — never active.
 * Nothing outside this page's flow is touched.
 */
import API_BASE from '../config';
import React, { useCallback, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Upload, FileSpreadsheet, Download, CheckCircle2, AlertTriangle,
  ArrowLeft, Loader2, X, FileUp, PenSquare, Camera, Send,
} from 'lucide-react';
import SEO from '../components/SEO';

import PartnerBulkReviewTable from '../components/bulk/PartnerBulkReviewTable';
import PartnerBulkPhotoStudio from '../components/bulk/PartnerBulkPhotoStudio';

const API = API_BASE;

const STEPS = [
  { key: 1, labelKey: 'bulkImport.step1', icon: Download },
  { key: 2, labelKey: 'bulkImport.step2', icon: FileUp },
  { key: 3, labelKey: 'bulkImport.step3', icon: PenSquare },
  { key: 4, labelKey: 'bulkImport.step4', icon: Camera },
  { key: 5, labelKey: 'bulkImport.step5', icon: Send },
];

const BulkImportPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || '').startsWith('fr');
  const fileRef = useRef(null);

  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState(null);
  // Preview `rows` are stateful — inline-edit mutates `normalized`.
  const [rows, setRows] = useState([]);
  const [confirming, setConfirming] = useState(false);
  const [drafts, setDrafts] = useState([]);   // [{ id, title, title_fr, image_count, needs_photos }]
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);

  const headers = { Authorization: `Bearer ${token}` };
  const errorCount = useMemo(
    () => rows.reduce((n, r) => n + (r.errors?.length || 0), 0),
    [rows]
  );

  // ─── Step 1: template ──────────────────────────────────────────
  const downloadTemplate = async () => {
    try {
      const resp = await axios.get(`${API}/partner-pro/bulk-import/template`, {
        headers, responseType: 'blob',
      });
      const url = window.URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bidvex_partner_bulk_import_template.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error(t('bulkImport.failedDownload'));
    }
  };

  // ─── Step 2: preview ───────────────────────────────────────────
  const handleUpload = async () => {
    if (!file) return;
    setPreviewing(true);
    setPreview(null);
    setRows([]);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await axios.post(`${API}/partner-pro/bulk-import`, form, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
      });
      setPreview(data);
      setRows(data.preview || []);
      setStep(3);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = detail && typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : (detail || t('bulkImport.importFailed'));
      toast.error(msg);
    } finally {
      setPreviewing(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f && f.name.endsWith('.csv')) setFile(f);
    else toast.error(t('bulkImport.csvOnly'));
  };

  // ─── Step 3: inline edit ───────────────────────────────────────
  // Any cell edit invalidates the per-cell errors for that field, and
  // clears the whole row's `duplicate_row` error (the Partner has changed
  // one of the three keys forming the duplicate). Server-side revalidation
  // runs when the Partner clicks "Confirm & Create Drafts" — that's the
  // authoritative check.
  const onCellChange = useCallback((rowIdx, field, value) => {
    setRows((prev) => {
      const next = [...prev];
      const row = { ...next[rowIdx] };
      const norm = { ...(row.normalized || {}) };
      // Coerce types back to what the backend expects on confirm.
      if (['starting_price', 'buy_now_price', 'buyers_premium_percent'].includes(field)) {
        norm[field] = value === '' ? null : Number(value);
      } else if (field === 'quantity') {
        norm[field] = value === '' ? null : parseInt(value, 10);
      } else {
        norm[field] = value;
      }
      row.normalized = norm;
      // Optimistically drop the errors on the field the user just edited
      // + any batch-wide duplicate error attached to this row (they may
      // have just fixed the duplicate). Server re-validates on confirm.
      row.errors = (row.errors || []).filter(
        (e) => e.field !== field && e.code !== 'duplicate_row'
      );
      next[rowIdx] = row;
      return next;
    });
  }, []);

  const confirmDrafts = async () => {
    if (errorCount > 0) {
      toast.error(t('bulkImport.cannotImport', 'Fix all errors before creating drafts.'));
      return;
    }
    setConfirming(true);
    try {
      const body = { rows: rows.map((r) => r.normalized) };
      const { data } = await axios.post(`${API}/partner-pro/bulk-import/confirm`, body, {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
      if (!data.ok) {
        // Server re-validation caught something the client didn't.
        toast.error(isFr ? data.message_fr : data.message_en);
        // Re-attach server-detected errors to their rows for display.
        if (Array.isArray(data.errors)) {
          setRows((prev) => {
            const next = prev.map((r) => ({ ...r, errors: [] }));
            for (const e of data.errors) {
              const idx = next.findIndex((r) => r.row === e.row);
              if (idx >= 0) next[idx].errors = [...(next[idx].errors || []), e];
            }
            return next;
          });
        }
        return;
      }
      toast.success(isFr ? data.message_fr : data.message_en);
      // Prime the drafts list for the Photo Studio.
      setDrafts(
        (data.drafts || []).map((d) => ({
          ...d,
          image_count: 0,
          needs_photos: true,
        }))
      );
      setStep(4);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = detail && typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : (detail || t('bulkImport.importFailed'));
      toast.error(msg);
    } finally {
      setConfirming(false);
    }
  };

  // ─── Step 4: photo studio callbacks ────────────────────────────
  const onDraftPhotoUpdate = useCallback((listingId, patch) => {
    setDrafts((prev) => prev.map((d) => (d.id === listingId ? { ...d, ...patch } : d)));
  }, []);

  // ─── Step 5: publish ───────────────────────────────────────────
  const publishAll = async () => {
    setPublishing(true);
    setPublishResult(null);
    try {
      const { data } = await axios.post(`${API}/partner-pro/bulk-import/publish-batch`, {}, { headers });
      setPublishResult(data);
      toast.success(isFr ? data.message_fr : data.message_en);
      // Reflect status on the drafts list — published drafts leave the
      // Photo Studio queue.
      setDrafts((prev) => prev.filter((d) => !(data.published_ids || []).includes(d.id)));
    } catch (err) {
      toast.error(t('bulkImport.importFailed'));
    } finally {
      setPublishing(false);
    }
  };

  // ─── Render ────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="bulk-import-page">
      <SEO title="Bulk Import — BidVex" />

      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900 via-slate-900 to-cyan-900">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="text-white hover:bg-white/10" data-testid="bulk-back-btn">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="p-2.5 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
              <FileSpreadsheet className="h-7 w-7 text-cyan-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">{t('bulkImport.title')}</h1>
              <p className="text-blue-200/80 text-sm">{t('bulkImport.subtitle')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Stepper */}
      <div className="max-w-6xl mx-auto px-4 pt-6">
        <ol className="grid grid-cols-5 gap-1" data-testid="bulk-stepper">
          {STEPS.map(({ key, labelKey, icon: Icon }) => {
            const active = step === key;
            const done = step > key;
            return (
              <li
                key={key}
                className={`flex flex-col items-center rounded-md py-2 px-1 text-[11px] sm:text-xs ${
                  active ? 'bg-cyan-100 text-cyan-800 font-semibold' :
                  done ? 'text-emerald-600' : 'text-slate-400'
                }`}
                data-testid={`bulk-step-indicator-${key}`}
              >
                <Icon className="h-4 w-4 mb-1" />
                <span className="text-center leading-tight">{t(labelKey)}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* ── STEP 1 ── */}
        {step === 1 && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge className="bg-cyan-100 text-cyan-700">1</Badge>
                {t('bulkImport.downloadTemplate')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {t('bulkImport.templateDesc')} <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">title</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">category</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">starting_price</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">quantity</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">condition</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">auction_end_date</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">city</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">region</code>.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" onClick={downloadTemplate} className="border-cyan-500 text-cyan-600 hover:bg-cyan-50 dark:hover:bg-cyan-900/20" data-testid="download-template-btn">
                  <Download className="h-4 w-4 mr-2" /> {t('bulkImport.downloadBtn')}
                </Button>
                <Button onClick={() => setStep(2)} className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="step-1-next-btn">
                  {t('bulkImport.next')}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 2 ── */}
        {step === 2 && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge className="bg-cyan-100 text-cyan-700">2</Badge>
                {t('bulkImport.uploadCsv')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
                  file ? 'border-cyan-400 bg-cyan-50/50 dark:bg-cyan-900/10' : 'border-slate-300 dark:border-slate-600 hover:border-cyan-400'
                }`}
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={onDrop}
                data-testid="csv-dropzone"
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  data-testid="csv-file-input"
                />
                {file ? (
                  <div className="flex items-center justify-center gap-3">
                    <FileSpreadsheet className="h-8 w-8 text-cyan-500" />
                    <div className="text-left">
                      <p className="font-medium">{file.name}</p>
                      <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="text-slate-400 hover:text-red-500">
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <Upload className="h-10 w-10 mx-auto text-slate-400 mb-3" />
                    <p className="font-medium">{t('bulkImport.dropHere')}</p>
                    <p className="text-xs text-slate-500 mt-1">{t('bulkImport.maxSize')}</p>
                  </>
                )}
              </div>

              <div className="mt-4 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(1)}>{t('bulkImport.back')}</Button>
                <Button
                  onClick={handleUpload}
                  disabled={!file || previewing}
                  className="bg-cyan-600 hover:bg-cyan-700 text-white"
                  data-testid="upload-csv-btn"
                >
                  {previewing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
                  {previewing ? t('bulkImport.importing') : t('bulkImport.importListings')}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 3 ── */}
        {step === 3 && preview && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge className="bg-cyan-100 text-cyan-700">3</Badge>
                {t('bulkImport.reviewTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {t('bulkImport.reviewSubtitle')}
              </p>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <Badge className={errorCount === 0 ? 'bg-emerald-500' : 'bg-red-500'} data-testid="bulk-error-summary">
                  {errorCount === 0
                    ? t('bulkImport.rowsReady', { count: rows.length })
                    : t('bulkImport.rowsWithErrors', { count: errorCount })}
                </Badge>
                <span className="text-slate-500">{rows.length} / {preview.max_rows}</span>
              </div>

              <PartnerBulkReviewTable rows={rows} onChange={onCellChange} isFr={isFr} />

              <div className="flex justify-between">
                <Button variant="ghost" onClick={() => setStep(2)}>{t('bulkImport.back')}</Button>
                <Button
                  onClick={confirmDrafts}
                  disabled={errorCount > 0 || confirming || rows.length === 0}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  data-testid="confirm-drafts-btn"
                >
                  {confirming ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
                  {confirming ? t('bulkImport.confirmingDrafts') : t('bulkImport.confirmDrafts')}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 4 ── */}
        {step === 4 && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge className="bg-cyan-100 text-cyan-700">4</Badge>
                {t('bulkImport.photoStudioTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {t('bulkImport.photoStudioSubtitle')}
              </p>
              <PartnerBulkPhotoStudio
                drafts={drafts}
                onDraftUpdate={onDraftPhotoUpdate}
                isFr={isFr}
                token={token}
              />
              <div className="flex justify-between">
                <Button variant="ghost" onClick={() => setStep(3)}>{t('bulkImport.back')}</Button>
                <Button
                  onClick={() => setStep(5)}
                  className="bg-cyan-600 hover:bg-cyan-700 text-white"
                  data-testid="step-4-next-btn"
                >
                  {t('bulkImport.next')}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 5 ── */}
        {step === 5 && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge className="bg-cyan-100 text-cyan-700">5</Badge>
                {t('bulkImport.publishTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {t('bulkImport.publishSubtitle')}
              </p>

              {publishResult ? (
                <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 space-y-2" data-testid="publish-result">
                  <p className="text-sm text-emerald-800 font-semibold">
                    {t('bulkImport.publishedCount', { count: publishResult.published_count })}
                  </p>
                  {publishResult.pending_photos_count > 0 && (
                    <p className="text-sm text-amber-700 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      {t('bulkImport.pendingPhotosCount', { count: publishResult.pending_photos_count })}
                    </p>
                  )}
                  <div className="flex gap-2 pt-2">
                    <Button variant="outline" onClick={() => setStep(4)}>{t('bulkImport.back')}</Button>
                    <Button onClick={() => navigate('/my-listings?tab=drafts')} data-testid="go-to-drafts-btn">
                      {t('bulkImport.goToDrafts')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-between">
                  <Button variant="ghost" onClick={() => setStep(4)}>{t('bulkImport.back')}</Button>
                  <Button
                    onClick={publishAll}
                    disabled={publishing || drafts.filter((d) => !d.needs_photos).length === 0}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    data-testid="publish-all-btn"
                  >
                    {publishing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                    {publishing ? t('bulkImport.publishing') : t('bulkImport.publishAllReady')}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default BulkImportPage;
