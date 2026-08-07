/**
 * StorageBulkImportPage — iter446
 *
 * 5-step CSV bulk-import wizard for VERIFIED storage facilities.
 *
 *   1. Download template            (fixed columns; no buyer_premium)
 *   2. Upload CSV → preview
 *   3. Review + inline-edit + bilingual per-cell errors + duplicate
 *      conflicts (batch AND facility's open auctions)
 *   4. Active legal-notice acceptance → confirm drafts
 *   5. Unit Photo Studio (auto-match by unit_number in filename)
 *   6. Publish (photo-gated, ≥1 photo per unit)
 *
 * Every imported row is written as `status="draft"` — never active.
 * Buyer's premium is fixed 5 %; the template has no BP column and no
 * facility can bypass this policy.
 */
import API_BASE from '../config';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import {
  FileSpreadsheet, Download, CheckCircle2, AlertTriangle,
  ArrowLeft, Loader2, FileUp, PenSquare, Camera, Send,
  ShieldCheck,
} from 'lucide-react';
import SEO from '../components/SEO';

import StorageBulkReviewTable from '../components/bulk/StorageBulkReviewTable';
import StorageBulkPhotoStudio from '../components/bulk/StorageBulkPhotoStudio';

const API = API_BASE;

const STEPS = [
  { key: 1, en: 'Template', fr: 'Modèle', icon: Download },
  { key: 2, en: 'Upload', fr: 'Téléverser', icon: FileUp },
  { key: 3, en: 'Review', fr: 'Vérifier', icon: PenSquare },
  { key: 4, en: 'Photos', fr: 'Photos', icon: Camera },
  { key: 5, en: 'Publish', fr: 'Publier', icon: Send },
];

const StorageBulkImportPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || '').startsWith('fr');
  const fileRef = useRef(null);

  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [rows, setRows] = useState([]);
  const [legalAccepted, setLegalAccepted] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);

  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}` }),
    [token]
  );

  const totalErrorObjects = useMemo(
    () => rows.reduce((n, r) => n + (r.errors?.length || 0), 0),
    [rows]
  );
  const errorRowsCount = useMemo(
    () => rows.reduce((n, r) => n + ((r.errors?.length || 0) > 0 ? 1 : 0), 0),
    [rows]
  );

  // ─── Step 1: template ──────────────────────────────────────────
  const downloadTemplate = async () => {
    try {
      const resp = await axios.get(
        `${API}/storage-facilities/bulk-import/template`,
        { headers, responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bidvex_storage_bulk_import_template.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = detail && typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : (isFr ? 'Échec du téléchargement du modèle' : 'Failed to download template');
      toast.error(msg);
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
      const { data } = await axios.post(
        `${API}/storage-facilities/bulk-import`, form,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } }
      );
      setPreview(data);
      setRows(data.preview || []);
      setStep(3);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = detail && typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : (detail || (isFr ? 'Échec de l\'importation' : 'Import failed'));
      toast.error(msg);
    } finally {
      setPreviewing(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f && f.name.toLowerCase().endsWith('.csv')) setFile(f);
    else toast.error(isFr ? 'Fichiers CSV uniquement' : 'CSV files only');
  };

  // ─── Step 3: inline edit ───────────────────────────────────────
  const onCellChange = useCallback((rowIdx, field, value) => {
    setRows((prev) => {
      const next = [...prev];
      const row = { ...next[rowIdx] };
      const norm = { ...(row.normalized || {}) };
      if (
        ['starting_price', 'reserve_price', 'bid_increment',
         'past_due_balance', 'deposit_amount'].includes(field)
      ) {
        norm[field] = value === '' ? null : Number(value);
      } else if (field === 'cleanup_deadline_hours') {
        norm[field] = value === '' ? null : parseInt(value, 10);
      } else if (['is_lien_unit', 'deposit_required'].includes(field)) {
        norm[field] = value === true || value === 'Y' || value === 'true';
      } else {
        norm[field] = value;
      }
      row.normalized = norm;
      // Clear this field's errors + the row's duplicate errors (batch
      // and facility). Server re-validates on confirm.
      row.errors = (row.errors || []).filter(
        (e) => e.field !== field
          && e.code !== 'duplicate_unit_in_batch'
          && e.code !== 'duplicate_unit_in_facility'
      );
      next[rowIdx] = row;
      return next;
    });
  }, []);

  // ─── Step 4: legal-notice + confirm ────────────────────────────
  const confirmDrafts = async () => {
    if (totalErrorObjects > 0) {
      toast.error(
        isFr
          ? 'Corrigez toutes les erreurs avant de créer les brouillons.'
          : 'Fix all errors before creating drafts.'
      );
      return;
    }
    if (!legalAccepted) {
      toast.error(
        isFr
          ? 'Veuillez accepter la notification légale bilingue.'
          : 'Please accept the bilingual legal notice.'
      );
      return;
    }
    setConfirming(true);
    try {
      const body = {
        rows: rows.map((r) => r.normalized),
        accepted_legal_notice: true,
      };
      const { data } = await axios.post(
        `${API}/storage-facilities/bulk-import/confirm`, body,
        { headers: { ...headers, 'Content-Type': 'application/json' } }
      );
      if (!data.ok) {
        toast.error(isFr ? data.message_fr : data.message_en);
        if (Array.isArray(data.errors)) {
          setRows((prev) => {
            // Merge server-returned errors onto the existing row state
            // instead of wiping everything — preserves any client-side
            // fields the user is still editing.
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
      setDrafts(
        (data.drafts || []).map((d) => ({
          ...d,
          image_count: 0,
          needs_photos: true,
        }))
      );
      setStep(5);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = detail && typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : (detail || (isFr ? 'Échec de la création' : 'Failed to create drafts'));
      toast.error(msg);
    } finally {
      setConfirming(false);
    }
  };

  // ─── Step 5: photo studio callbacks ────────────────────────────
  const onDraftPhotoUpdate = useCallback((auctionId, patch) => {
    setDrafts((prev) => prev.map((d) => (d.id === auctionId ? { ...d, ...patch } : d)));
  }, []);

  // ─── Publish ───────────────────────────────────────────────────
  const publishAll = async () => {
    setPublishing(true);
    setPublishResult(null);
    try {
      const { data } = await axios.post(
        `${API}/storage-facilities/bulk-import/publish-batch`, {},
        { headers }
      );
      setPublishResult(data);
      toast.success(isFr ? data.message_fr : data.message_en);
      setDrafts((prev) => prev.filter(
        (d) => !(data.published_ids || []).includes(d.id)
      ));
    } catch (err) {
      toast.error(isFr ? 'Échec de la publication' : 'Publish failed');
    } finally {
      setPublishing(false);
    }
  };

  // On mount (and when token hydrates), refresh any pending drafts so a
  // returning facility sees their in-progress bulk queue.
  useEffect(() => {
    if (!token) return;
    const loadPending = async () => {
      try {
        const { data } = await axios.get(
          `${API}/storage-facilities/bulk-import/pending`,
          { headers }
        );
        if (Array.isArray(data.drafts) && data.drafts.length > 0) {
          setDrafts(data.drafts);
        }
      } catch { /* silent */ }
    };
    loadPending();
  }, [token, headers]);

  const canGoToPhotos = drafts.length > 0;

  return (
    <div
      className="min-h-screen bg-slate-50 dark:bg-slate-900"
      data-testid="storage-bulk-import-page"
    >
      <SEO title="Storage Bulk Import — BidVex" />

      {/* Header */}
      <div className="bg-gradient-to-r from-cyan-800 via-slate-900 to-blue-900">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate(-1)}
              className="text-white hover:bg-white/10"
              data-testid="storage-bulk-back-btn"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="p-2.5 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
              <FileSpreadsheet className="h-7 w-7 text-cyan-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">
                {isFr
                  ? 'Importation groupée d\'unités de stockage'
                  : 'Storage Bulk Import'}
              </h1>
              <p className="text-blue-200/80 text-sm">
                {isFr
                  ? 'Téléversez jusqu\'à 50 unités par lot. Chaque unité démarre en brouillon jusqu\'à ce qu\'elle ait au moins une photo.'
                  : 'Upload up to 50 units per batch. Every unit starts as a draft until it has at least one photo.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Stepper */}
      <div className="max-w-6xl mx-auto px-4 pt-6">
        <ol
          className="grid grid-cols-5 gap-1"
          data-testid="storage-bulk-stepper"
        >
          {STEPS.map(({ key, en, fr, icon: Icon }) => {
            const active = step === key;
            const done = step > key;
            return (
              <li
                key={key}
                className={`flex flex-col items-center rounded-md py-2 px-1 text-[11px] sm:text-xs ${
                  active ? 'bg-cyan-100 text-cyan-800 font-semibold' :
                  done ? 'text-emerald-600' : 'text-slate-400'
                }`}
                data-testid={`storage-bulk-step-indicator-${key}`}
              >
                <Icon className="h-4 w-4 mb-1" />
                <span className="text-center leading-tight">{isFr ? fr : en}</span>
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
                {isFr ? 'Télécharger le modèle' : 'Download the template'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {isFr
                  ? 'Le modèle utilise les mêmes champs que le formulaire d\'unité unique. La prime acheteur (5 %) est une règle de plateforme fixe : elle n\'est pas incluse dans le modèle et ne peut pas être modifiée.'
                  : 'The template uses the same fields as the single-unit form. The buyer\'s premium (5%) is a fixed platform rule — it is not in the template and cannot be changed.'}
              </p>
              <div className="text-xs text-slate-500 bg-slate-100 dark:bg-slate-700 rounded p-2 font-mono">
                unit_number, unit_size, unit_type, is_lien_unit,
                past_due_balance, description_en, description_fr, video_url,
                starting_price, reserve_price, bid_increment, start_time,
                end_time, cleanup_deadline_hours, payment_method, currency,
                deposit_required, deposit_amount, deposit_type
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="outline"
                  onClick={downloadTemplate}
                  className="border-cyan-500 text-cyan-600 hover:bg-cyan-50 dark:hover:bg-cyan-900/20"
                  data-testid="storage-download-template-btn"
                >
                  <Download className="h-4 w-4 mr-2" />
                  {isFr ? 'Télécharger le modèle' : 'Download template'}
                </Button>
                <Button
                  onClick={() => setStep(2)}
                  className="bg-cyan-600 hover:bg-cyan-700 text-white"
                  data-testid="storage-step-1-next-btn"
                >
                  {isFr ? 'Suivant' : 'Next'}
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
                {isFr
                  ? 'Téléverser le fichier CSV'
                  : 'Upload the CSV file'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div
                onDrop={onDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center cursor-pointer hover:border-cyan-400 transition-colors"
                data-testid="storage-bulk-csv-dropzone"
              >
                <FileUp className="h-10 w-10 mx-auto text-slate-400 mb-2" />
                <p className="font-medium text-slate-700 dark:text-slate-200">
                  {isFr
                    ? 'Déposez votre fichier CSV ici ou cliquez pour choisir'
                    : 'Drop your CSV file here or click to browse'}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {isFr ? 'Max. 50 lignes · 5 Mo' : 'Max. 50 rows · 5 MB'}
                </p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  data-testid="storage-bulk-csv-file-input"
                />
              </div>
              {file && (
                <div
                  className="text-sm text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2 flex items-center gap-2"
                  data-testid="storage-bulk-selected-file"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {file.name}
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => setStep(1)}
                  data-testid="storage-step-2-back-btn"
                >
                  {isFr ? 'Retour' : 'Back'}
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={!file || previewing}
                  className="bg-cyan-600 hover:bg-cyan-700 text-white"
                  data-testid="storage-step-2-upload-btn"
                >
                  {previewing ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <FileUp className="h-4 w-4 mr-2" />
                  )}
                  {isFr ? 'Analyser le fichier' : 'Analyze file'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 3 — Review ── */}
        {step === 3 && preview && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge className="bg-cyan-100 text-cyan-700">3</Badge>
                {isFr
                  ? 'Vérifier et corriger les erreurs'
                  : 'Review and fix errors'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <Badge className="bg-blue-100 text-blue-800" data-testid="storage-total-rows">
                  {isFr ? 'Lignes' : 'Rows'}: {rows.length}
                </Badge>
                {errorRowsCount > 0 ? (
                  <Badge
                    className="bg-red-100 text-red-800"
                    data-testid="storage-error-rows"
                  >
                    <AlertTriangle className="h-3 w-3 mr-1 inline" />
                    {isFr
                      ? `${errorRowsCount} ligne(s) avec erreurs`
                      : `${errorRowsCount} row(s) with errors`}
                  </Badge>
                ) : (
                  <Badge
                    className="bg-emerald-100 text-emerald-800"
                    data-testid="storage-all-clean"
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1 inline" />
                    {isFr ? 'Toutes les lignes sont valides' : 'All rows are valid'}
                  </Badge>
                )}
              </div>

              <StorageBulkReviewTable
                rows={rows}
                onChange={onCellChange}
                isFr={isFr}
              />

              {/* Bilingual legal-notice — actively accepted here.
                  Spreadsheet values do NOT satisfy this requirement.
                  This applies to EVERY unit in the batch. */}
              <div
                className="rounded-lg border-2 border-amber-300 bg-amber-50/60 p-4"
                data-testid="storage-legal-notice-block"
              >
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-5 w-5 text-amber-700 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-amber-900 mb-1">
                      {isFr
                        ? 'Confirmation légale (bilingue) — s\'applique à chaque unité du lot'
                        : 'Legal-notice confirmation (bilingual) — applies to every unit in this batch'}
                    </p>
                    <p className="text-xs text-amber-900 leading-relaxed">
                      {isFr
                        ? 'Je confirme que CHAQUE unité de cette importation a fait l\'objet du processus de notification légale requis et que son contenu peut être mis aux enchères conformément à la loi provinciale applicable. Cette acceptation est enregistrée sur chaque brouillon créé.'
                        : 'I confirm that EVERY unit in this import has gone through the required legal-notification process and its contents may be auctioned under the applicable provincial law. This acceptance will be recorded on every draft created.'}
                    </p>
                    <label className="mt-3 flex items-start gap-2 cursor-pointer">
                      <Checkbox
                        checked={legalAccepted}
                        onCheckedChange={(v) => setLegalAccepted(v === true)}
                        data-testid="storage-legal-notice-checkbox"
                      />
                      <span className="text-xs text-amber-900">
                        {isFr
                          ? 'J\'accepte cette confirmation pour toutes les unités du lot.'
                          : 'I accept this confirmation for all units in the batch.'}
                      </span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => setStep(2)}
                  data-testid="storage-step-3-back-btn"
                >
                  {isFr ? 'Retour' : 'Back'}
                </Button>
                <Button
                  onClick={confirmDrafts}
                  disabled={
                    confirming
                    || totalErrorObjects > 0
                    || !legalAccepted
                    || rows.length === 0
                  }
                  className="bg-cyan-600 hover:bg-cyan-700 text-white"
                  data-testid="storage-step-3-confirm-btn"
                >
                  {confirming ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <PenSquare className="h-4 w-4 mr-2" />
                  )}
                  {isFr ? 'Créer les brouillons' : 'Create drafts'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 4 (skipped in stepper, mapped to Photos step 5) ── */}
        {/* ── STEP 5 — Photo studio ── */}
        {step === 5 && canGoToPhotos && (
          <>
            <Card className="border-0 shadow-md dark:bg-slate-800/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Badge className="bg-cyan-100 text-cyan-700">4</Badge>
                  {isFr
                    ? 'Studio photo — attribuez au moins une photo par unité'
                    : 'Photo Studio — attach at least one photo per unit'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <StorageBulkPhotoStudio
                  drafts={drafts}
                  onDraftUpdate={onDraftPhotoUpdate}
                  isFr={isFr}
                  token={token}
                />
              </CardContent>
            </Card>

            <Card className="border-0 shadow-md dark:bg-slate-800/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Badge className="bg-cyan-100 text-cyan-700">5</Badge>
                  {isFr
                    ? 'Publier les unités prêtes'
                    : 'Publish photo-ready units'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  {isFr
                    ? 'Seules les unités disposant d\'au moins une photo peuvent être publiées. Les autres restent en brouillon.'
                    : 'Only units with at least one photo will be published. Others remain as drafts.'}
                </p>
                <Button
                  onClick={publishAll}
                  disabled={publishing || drafts.every((d) => d.needs_photos)}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  data-testid="storage-publish-batch-btn"
                >
                  {publishing ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4 mr-2" />
                  )}
                  {isFr
                    ? 'Publier toutes les unités prêtes'
                    : 'Publish all photo-ready units'}
                </Button>
                {publishResult && (
                  <div
                    className="rounded-lg bg-slate-100 dark:bg-slate-700 p-3 text-sm"
                    data-testid="storage-publish-result"
                  >
                    <p className="font-semibold">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 inline mr-1" />
                      {isFr
                        ? `${publishResult.published_count} enchère(s) publiée(s)`
                        : `${publishResult.published_count} auction(s) published`}
                    </p>
                    {publishResult.pending_photos_count > 0 && (
                      <p className="text-amber-700 mt-1">
                        <AlertTriangle className="h-4 w-4 inline mr-1" />
                        {isFr
                          ? `${publishResult.pending_photos_count} unité(s) attendent une photo.`
                          : `${publishResult.pending_photos_count} unit(s) still need a photo.`}
                      </p>
                    )}
                  </div>
                )}
                <Button
                  variant="outline"
                  onClick={() => navigate('/storage-auctions')}
                  data-testid="storage-view-listings-btn"
                >
                  {isFr
                    ? 'Voir les enchères'
                    : 'View my storage auctions'}
                </Button>
              </CardContent>
            </Card>
          </>
        )}

        {/* Empty state for Step 5 with no drafts */}
        {step === 5 && !canGoToPhotos && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50">
            <CardContent className="py-8 text-center">
              <p className="text-slate-500">
                {isFr
                  ? 'Aucun brouillon en attente. Retour à l\'étape 1 pour importer un nouveau lot.'
                  : 'No drafts pending. Head back to step 1 to import a new batch.'}
              </p>
              <Button
                className="mt-4"
                onClick={() => setStep(1)}
                data-testid="storage-step-5-restart-btn"
              >
                {isFr ? 'Recommencer' : 'Start over'}
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default StorageBulkImportPage;
