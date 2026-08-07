/**
 * BulkImportLotsCSV — iter306 → iter447
 *
 * Multi-step modal wizard for CSV bulk import into a Multi-Lot Vehicle
 * Auction event:
 *
 *   1. Upload — drag-drop CSV, download template
 *   2. Review — server-driven per-cell bilingual errors; inline edit;
 *                capacity indicator (X of 500 used, Y remaining);
 *                atomic all-or-nothing confirm
 *   3. Photos — Vehicle Photo Studio (VIN-only unambiguous matching);
 *                per-lot photo pill; publish gate previews "N lots
 *                still need a photo"
 *   4. Done   — hand off to parent so the dealer can activate the event
 *
 * Rules:
 *  • Max 500 rows per import (frontend + server).
 *  • Event holds up to 500 total lots. Repeat uploads into the same
 *    event honour the remaining capacity.
 *  • Bulk-imported lots always stay `status="draft_no_photos"` until
 *    at least one photo is attached (enforced by the activate route).
 *  • Photo matching is VIN-only (full 17-char, then unambiguous
 *    last-8 / last-6 suffix). See VehicleBulkPhotoStudio.jsx.
 */
import API_BASE from '../../config';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import Papa from 'papaparse';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import {
  Upload, Download, FileSpreadsheet, CheckCircle, AlertTriangle,
  Loader2, X, ChevronRight, ExternalLink, Camera, Send,
} from 'lucide-react';

import VehicleBulkPhotoStudio from './VehicleBulkPhotoStudio';

const API = API_BASE;

const MAX_LOTS_PER_IMPORT = 500;
const MAX_LOTS_PER_EVENT = 500;

// CSV columns — kept in sync with backend CSV_COLUMNS_TEMPLATE.
const COLUMNS = [
  'vin', 'year', 'make', 'model', 'trim', 'body_type', 'mileage',
  'engine_size', 'transmission', 'drivetrain', 'fuel_type',
  'exterior_color', 'condition_rating', 'title_status',
  'starting_price', 'reserve_price', 'bid_increment',
  'location_city', 'location_province',
  'title', 'title_fr', 'description',
];
// Friendly aliases — accept common header variations.
const COL_ALIASES = {
  'starting_price_cad': 'starting_price',
  'reserve_price_cad': 'reserve_price',
  'price': 'starting_price',
  'condition': 'condition_rating',
  'engine': 'engine_size',
  'city': 'location_city',
  'province': 'location_province',
  'title_en': 'title',
};

const STEPS = [
  { key: 1, en: 'Upload', fr: 'Téléverser', icon: Upload },
  { key: 2, en: 'Review', fr: 'Vérifier', icon: FileSpreadsheet },
  { key: 3, en: 'Photos', fr: 'Photos', icon: Camera },
  { key: 4, en: 'Done', fr: 'Terminé', icon: Send },
];

const BulkImportLotsCSV = ({ open, onClose, eventId, fr, L, onImported }) => {
  const isFr = !!fr;
  const fileInputRef = useRef(null);

  const [step, setStep] = useState(1);
  const [csvBaseRows, setCsvBaseRows] = useState([]);   // client-parsed CSV
  const [preview, setPreview] = useState(null);         // server preview
  const [previewing, setPreviewing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [capacity, setCapacity] = useState(null);       // { used, max, remaining }
  const [parseError, setParseError] = useState('');
  const [createdLots, setCreatedLots] = useState([]);   // lots for Photo Studio
  const [activating, setActivating] = useState(false);

  const token = useMemo(() => localStorage.getItem('token'), []);

  // ── Load current event capacity on open ──────────────────────────
  useEffect(() => {
    if (!open || !eventId || !token) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API}/vehicle-multi-lot-auctions/${eventId}/bulk-import/capacity`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!cancelled) setCapacity(r.data);
      } catch (e) {
        // If the event isn't editable (live/ended), reflect that.
        if (!cancelled) setCapacity(null);
      }
    })();
    return () => { cancelled = true; };
  }, [open, eventId, token]);

  // ── Reset ────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    setStep(1);
    setCsvBaseRows([]);
    setPreview(null);
    setParseError('');
    setCreatedLots([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleClose = () => {
    reset();
    onClose?.();
  };

  // ── Template ─────────────────────────────────────────────────────
  const downloadTemplate = async () => {
    if (!eventId || !token) {
      toast.error(L('Save the event first, then download the template',
        "Enregistrez l'événement d'abord, puis téléchargez le modèle"));
      return;
    }
    try {
      const r = await axios.get(
        `${API}/vehicle-multi-lot-auctions/${eventId}/bulk-import/template`,
        { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bidvex_multi_lot_bulk_template.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(L('Template download failed', 'Échec du téléchargement du modèle'));
    }
  };

  // ── Step 1 — Parse CSV client-side ───────────────────────────────
  const parseFile = (file) => {
    setParseError('');
    Papa.parse(file, {
      header: true,
      skipEmptyLines: 'greedy',
      transformHeader: (h) => {
        const norm = String(h || '').trim().toLowerCase().replace(/\s+/g, '_');
        return COL_ALIASES[norm] || norm;
      },
      complete: (results) => {
        if (results.errors?.length) {
          setParseError(results.errors[0]?.message || 'CSV parse failed');
          return;
        }
        const data = (results.data || [])
          .filter((r) => Object.values(r).some((v) => String(v || '').trim()))
          .filter((r) => !String(r.vin || '').trim().startsWith('#'));
        if (data.length === 0) {
          setParseError(L('No data rows found in CSV', 'Aucune ligne de données trouvée'));
          return;
        }
        if (data.length > MAX_LOTS_PER_IMPORT) {
          setParseError(L(
            `Max ${MAX_LOTS_PER_IMPORT} lots per import. Found ${data.length}.`,
            `Maximum ${MAX_LOTS_PER_IMPORT} lots. ${data.length} trouvés.`
          ));
          return;
        }
        setCsvBaseRows(data);
        setStep(2);
        // Run the initial server preview
        runPreview(data);
      },
      error: (err) => setParseError(err?.message || 'Parse failed'),
    });
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (f) parseFile(f);
  };
  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f) parseFile(f);
  };

  // ── Step 2 — Server preview ──────────────────────────────────────
  const buildPayload = (rows) => ({
    lots: rows.map((r) => ({
      vin: String(r.vin || '').trim().toUpperCase(),
      year: parseInt(r.year || 0, 10) || 0,
      make: String(r.make || '').trim(),
      model: String(r.model || '').trim(),
      trim: String(r.trim || '').trim(),
      body_type: String(r.body_type || 'sedan').trim().toLowerCase(),
      mileage: parseInt(r.mileage || 0, 10) || 0,
      engine_size: String(r.engine_size || ''),
      transmission: String(r.transmission || 'automatic').trim().toLowerCase(),
      drivetrain: String(r.drivetrain || 'fwd').trim().toLowerCase(),
      fuel_type: String(r.fuel_type || 'gasoline').trim().toLowerCase(),
      exterior_color: String(r.exterior_color || ''),
      condition_rating: String(r.condition_rating || 'good').trim().toLowerCase(),
      title_status: String(r.title_status || 'clean').trim().toLowerCase(),
      starting_price: parseFloat(r.starting_price || 0) || 0,
      reserve_price: r.reserve_price ? parseFloat(r.reserve_price) : null,
      bid_increment: parseFloat(r.bid_increment || 100) || 100,
      location_city: String(r.location_city || '').trim(),
      location_province: String(r.location_province || '').trim().toUpperCase(),
      title: String(r.title || '').trim(),
      title_fr: String(r.title_fr || '').trim(),
      description: String(r.description || '').trim(),
    })),
  });

  const runPreview = async (rows) => {
    if (!rows.length || !eventId || !token) return;
    setPreviewing(true);
    try {
      const r = await axios.post(
        `${API}/vehicle-multi-lot-auctions/${eventId}/bulk-import/preview`,
        buildPayload(rows),
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPreview(r.data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : detail) || L('Preview failed', 'Échec de la prévisualisation');
      toast.error(msg);
    } finally {
      setPreviewing(false);
    }
  };

  // Inline edit — mutates csvBaseRows locally and re-runs the preview
  // in a debounced fashion.
  const editCell = (rowIdx, field, value) => {
    setCsvBaseRows((prev) => {
      const next = [...prev];
      next[rowIdx] = { ...next[rowIdx], [field]: value };
      return next;
    });
  };

  // Debounced preview refresh on edit.
  const refreshPreview = useCallback(() => {
    if (csvBaseRows.length > 0) runPreview(csvBaseRows);
  }, [csvBaseRows]);

  // ── Step 2 — Server confirm (atomic) ─────────────────────────────
  const handleConfirm = async () => {
    if (!eventId) return;
    if (!preview?.can_import) {
      toast.error(L(
        'Fix all errors and stay within the remaining capacity before importing.',
        "Corrigez toutes les erreurs et respectez la capacité restante avant l'importation."
      ));
      return;
    }
    setConfirming(true);
    try {
      const r = await axios.post(
        `${API}/vehicle-multi-lot-auctions/${eventId}/bulk-import/confirm`,
        buildPayload(csvBaseRows),
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!r.data?.ok) {
        toast.error(isFr ? r.data.message_fr : r.data.message_en);
        return;
      }
      toast.success(isFr ? r.data.message_fr : r.data.message_en);
      // Fetch the full event to hand the fresh lots to Photo Studio.
      const ev = await axios.get(
        `${API}/vehicle-multi-lot-auctions/${eventId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const evLots = ev.data?.lots || [];
      // Focus the Photo Studio only on the freshly imported lot_ids.
      const idsCreated = new Set(r.data.lot_ids || []);
      setCreatedLots(evLots.filter((l) => idsCreated.has(l.id)));
      setStep(3);
      // Refresh capacity for the caller.
      setCapacity((c) => c ? ({
        ...c,
        used: r.data.used_capacity,
        remaining: r.data.remaining_capacity,
      }) : c);
      onImported?.(r.data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : detail) || L('Import failed', "Échec de l'importation");
      toast.error(msg);
    } finally {
      setConfirming(false);
    }
  };

  // ── Step 3 — Photo Studio callback ───────────────────────────────
  const onLotUpdated = useCallback((lotId, updatedLot) => {
    setCreatedLots((prev) =>
      prev.map((l) => (l.id === lotId ? { ...l, ...updatedLot } : l))
    );
  }, []);

  const stillMissingPhotos = createdLots.filter(
    (l) => (l.media || []).length < 1
  ).length;

  // ── Step 4 — Activate (Go Live) ──────────────────────────────────
  const goLive = async () => {
    if (!eventId) return;
    if (stillMissingPhotos > 0) {
      toast.error(L(
        `${stillMissingPhotos} lot(s) still need at least one photo before going live.`,
        `${stillMissingPhotos} lot(s) nécessitent encore au moins une photo avant la mise en direct.`
      ));
      return;
    }
    setActivating(true);
    try {
      await axios.post(
        `${API}/vehicle-multi-lot-auctions/${eventId}/activate?intent=live`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(L('Event is now live', "L'événement est maintenant en direct"));
      setStep(4);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object'
        ? (isFr ? detail.message_fr : detail.message_en)
        : detail) || L('Failed to go live', 'Échec de la mise en direct');
      toast.error(msg);
    } finally {
      setActivating(false);
    }
  };

  if (!open) return null;

  const totalRowsWithErrors = (preview?.preview || [])
    .filter((r) => (r.errors || []).length > 0).length;

  return (
    <div
      className="fixed inset-0 z-[9999] bg-black/70 flex items-center justify-center p-2 sm:p-4"
      data-testid="bulk-import-modal"
    >
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-2xl w-full max-w-6xl max-h-[92vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <FileSpreadsheet className="h-5 w-5 text-blue-600" />
            <h2 className="text-lg sm:text-xl font-semibold">
              {L('Bulk Import Lots (CSV)', 'Importation groupée de lots (CSV)')}
            </h2>
            {capacity && (
              <span
                className="ml-2 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full"
                data-testid="bulk-import-capacity-header"
              >
                {L(
                  `${capacity.used} / ${MAX_LOTS_PER_EVENT} used — ${capacity.remaining} remaining`,
                  `${capacity.used} / ${MAX_LOTS_PER_EVENT} utilisés — ${capacity.remaining} restants`
                )}
              </span>
            )}
          </div>
          <button
            onClick={handleClose}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
            data-testid="bulk-import-close-btn"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Stepper */}
        <ol
          className="grid grid-cols-4 gap-1 px-4 pt-3"
          data-testid="bulk-import-stepper"
        >
          {STEPS.map(({ key, en, fr: frLabel, icon: Icon }) => {
            const active = step === key;
            const done = step > key;
            return (
              <li
                key={key}
                className={`flex flex-col items-center rounded-md py-2 px-1 text-[11px] sm:text-xs ${
                  active ? 'bg-blue-100 text-blue-800 font-semibold' :
                  done ? 'text-emerald-600' : 'text-slate-400'
                }`}
                data-testid={`bulk-import-step-${key}`}
              >
                <Icon className="h-4 w-4 mb-1" />
                <span>{isFr ? frLabel : en}</span>
              </li>
            );
          })}
        </ol>

        {/* Body */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Step 1 — Upload */}
          {step === 1 && (
            <>
              <Card className="border-2 border-dashed border-slate-300 dark:border-slate-700">
                <CardContent
                  className="p-6 sm:p-8 text-center cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  data-testid="bulk-import-dropzone"
                >
                  <Upload className="h-10 w-10 mx-auto text-slate-400 mb-2" />
                  <p className="font-medium text-sm sm:text-base">
                    {L('Drag and drop a CSV file here — or click to choose',
                      'Glissez-déposez un fichier CSV ici — ou cliquez pour choisir')}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    {L(
                      `Maximum ${MAX_LOTS_PER_IMPORT} lots per import — event cap ${MAX_LOTS_PER_EVENT}.`,
                      `Maximum ${MAX_LOTS_PER_IMPORT} lots par importation — plafond de ${MAX_LOTS_PER_EVENT} par événement.`
                    )}
                  </p>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    data-testid="bulk-import-file-input"
                  />
                </CardContent>
              </Card>
              {parseError && (
                <div
                  className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700"
                  data-testid="bulk-import-parse-error"
                >
                  <AlertTriangle className="h-4 w-4 inline mr-1" />
                  {parseError}
                </div>
              )}
              <div className="flex justify-center">
                <Button
                  variant="outline"
                  onClick={downloadTemplate}
                  data-testid="bulk-import-download-template-btn"
                >
                  <Download className="h-4 w-4 mr-1" />
                  {L('Download CSV Template', 'Télécharger le modèle CSV')}
                </Button>
              </div>
            </>
          )}

          {/* Step 2 — Review */}
          {step === 2 && preview && (
            <>
              {/* Capacity + error tally */}
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span
                  className="bg-blue-100 text-blue-800 px-2 py-1 rounded"
                  data-testid="bulk-import-rows-tally"
                >
                  {L('Rows', 'Lignes')}: {preview.total_rows}
                </span>
                <span
                  className={`px-2 py-1 rounded ${
                    preview.capacity_exceeded
                      ? 'bg-red-100 text-red-800'
                      : 'bg-emerald-100 text-emerald-800'
                  }`}
                  data-testid="bulk-import-capacity-tally"
                >
                  {L(
                    `Capacity: ${preview.used_capacity} / ${preview.max_capacity} — ${preview.remaining_capacity} remaining`,
                    `Capacité : ${preview.used_capacity} / ${preview.max_capacity} — ${preview.remaining_capacity} restants`
                  )}
                </span>
                {totalRowsWithErrors > 0 ? (
                  <span
                    className="bg-red-100 text-red-800 px-2 py-1 rounded"
                    data-testid="bulk-import-error-tally"
                  >
                    <AlertTriangle className="h-3 w-3 inline mr-1" />
                    {L(
                      `${totalRowsWithErrors} row(s) with errors`,
                      `${totalRowsWithErrors} ligne(s) avec erreurs`
                    )}
                  </span>
                ) : (
                  <span
                    className="bg-emerald-100 text-emerald-800 px-2 py-1 rounded"
                    data-testid="bulk-import-clean-tally"
                  >
                    <CheckCircle className="h-3 w-3 inline mr-1" />
                    {L('All rows are valid', 'Toutes les lignes sont valides')}
                  </span>
                )}
              </div>

              <div
                className="overflow-x-auto border border-slate-200 rounded-lg"
                data-testid="bulk-import-preview-table"
              >
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-100 sticky top-0 z-10">
                    <tr>
                      <th className="p-2 text-left">#</th>
                      <th className="p-2 text-left">VIN</th>
                      <th className="p-2 text-left">{L('Year', 'Année')}</th>
                      <th className="p-2 text-left">{L('Make', 'Marque')}</th>
                      <th className="p-2 text-left">{L('Model', 'Modèle')}</th>
                      <th className="p-2 text-left">{L('Price', 'Prix')}</th>
                      <th className="p-2 text-left">{L('City', 'Ville')}</th>
                      <th className="p-2 text-left">{L('Province', 'Province')}</th>
                      <th className="p-2 text-left">{L('Title (EN)', 'Titre (EN)')}</th>
                      <th className="p-2 text-left">{L('Title (FR)', 'Titre (FR)')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((pr, idx) => {
                      const errs = pr.errors || [];
                      const hasErrs = errs.length > 0;
                      const errsForField = (f) => errs.filter((e) => e.field === f);
                      const raw = pr.raw || {};
                      const row = csvBaseRows[idx] || raw;
                      const cellCls = (f) =>
                        `w-full px-1 py-0.5 text-xs border rounded ${
                          errsForField(f).length ? 'border-red-400 bg-red-50/40' : 'border-slate-200'
                        }`;
                      return (
                        <tr
                          key={pr.row}
                          className={hasErrs ? 'bg-red-50/30' : 'bg-emerald-50/10'}
                          data-testid={`bulk-import-row-${pr.row}`}
                        >
                          <td className="p-2 align-top font-mono font-semibold text-slate-500">
                            {pr.row}
                            {hasErrs ? (
                              <AlertTriangle className="h-3 w-3 text-red-500 inline ml-1" />
                            ) : (
                              <CheckCircle className="h-3 w-3 text-emerald-500 inline ml-1" />
                            )}
                          </td>
                          {[
                            ['vin', 17],
                            ['year', 4],
                            ['make', 12],
                            ['model', 14],
                            ['starting_price', 8],
                            ['location_city', 10],
                            ['location_province', 3],
                            ['title', 20],
                            ['title_fr', 20],
                          ].map(([f, maxLen]) => (
                            <td className="p-2 align-top" key={f}>
                              <input
                                className={cellCls(f)}
                                maxLength={maxLen}
                                value={row[f] ?? ''}
                                onChange={(e) => editCell(idx, f, e.target.value)}
                                onBlur={refreshPreview}
                                data-testid={`bulk-import-input-${pr.row}-${f}`}
                              />
                              {errsForField(f).map((err, i) => (
                                <div
                                  key={i}
                                  className="mt-1 text-[10px] leading-tight rounded bg-red-50 text-red-700 border border-red-200 px-1 py-0.5"
                                  data-testid={`bulk-import-err-${pr.row}-${f}-${err.code}`}
                                >
                                  {isFr ? err.message_fr : err.message_en}
                                  {err.conflict?.event_id && (
                                    <a
                                      href={`/vehicle-multi-lot/${err.conflict.event_id}`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-0.5 ml-1 underline hover:text-red-900"
                                    >
                                      <ExternalLink className="h-2.5 w-2.5" />
                                    </a>
                                  )}
                                </div>
                              ))}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {previewing && (
                <p className="text-xs text-slate-500 italic">
                  <Loader2 className="h-3 w-3 inline animate-spin mr-1" />
                  {L('Re-validating…', 'Nouvelle validation…')}
                </p>
              )}
            </>
          )}

          {/* Step 3 — Photo Studio */}
          {step === 3 && (
            <VehicleBulkPhotoStudio
              eventId={eventId}
              lots={createdLots}
              onLotUpdated={onLotUpdated}
              isFr={isFr}
              token={token}
              L={L}
            />
          )}

          {/* Step 4 — Done */}
          {step === 4 && (
            <div className="text-center py-8" data-testid="bulk-import-done">
              <CheckCircle className="h-12 w-12 mx-auto text-emerald-500 mb-2" />
              <p className="text-lg font-semibold">
                {L('Event is live', "L'événement est en direct")}
              </p>
              <p className="text-sm text-slate-500 mt-1">
                {L(
                  'All lots are now available to bidders.',
                  'Tous les lots sont maintenant disponibles pour les enchérisseurs.'
                )}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-col-reverse sm:flex-row items-center justify-between gap-2 p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <Button
            variant="ghost"
            onClick={handleClose}
            data-testid="bulk-import-cancel-btn"
          >
            {step === 4 ? L('Close', 'Fermer') : L('Cancel', 'Annuler')}
          </Button>

          <div className="flex flex-col-reverse sm:flex-row gap-2 w-full sm:w-auto">
            {step === 2 && (
              <>
                <Button
                  variant="outline"
                  onClick={reset}
                  data-testid="bulk-import-reset-btn"
                >
                  <X className="h-4 w-4 mr-1" />
                  {L('Choose different file', 'Choisir un autre fichier')}
                </Button>
                <Button
                  onClick={handleConfirm}
                  disabled={confirming || previewing || !preview?.can_import}
                  className="bg-blue-600 hover:bg-blue-700"
                  data-testid="bulk-import-submit-btn"
                >
                  {confirming ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <ChevronRight className="h-4 w-4 mr-1" />
                  )}
                  {L(
                    `Import ${preview?.total_rows || 0} lot(s)`,
                    `Importer ${preview?.total_rows || 0} lot(s)`
                  )}
                </Button>
              </>
            )}

            {step === 3 && (
              <>
                <Button
                  variant="outline"
                  onClick={handleClose}
                  data-testid="bulk-import-finish-later-btn"
                >
                  {L('Finish later', 'Terminer plus tard')}
                </Button>
                <Button
                  onClick={goLive}
                  disabled={activating || stillMissingPhotos > 0 || createdLots.length === 0}
                  className="bg-emerald-600 hover:bg-emerald-700"
                  data-testid="bulk-import-go-live-btn"
                >
                  {activating ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4 mr-1" />
                  )}
                  {stillMissingPhotos > 0
                    ? L(
                      `Go Live (${stillMissingPhotos} lot(s) need a photo)`,
                      `Passer en direct (${stillMissingPhotos} lot(s) sans photo)`
                    )
                    : L('Go Live', 'Passer en direct')}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BulkImportLotsCSV;
