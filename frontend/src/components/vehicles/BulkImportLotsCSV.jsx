/**
 * BulkImportLotsCSV — iter306
 *
 * Drag-and-drop CSV upload + preview-and-validate table for the multi-lot
 * vehicle auction wizard. Uses PapaParse (already in the bundle).
 *
 * Flow:
 *   1. Dealer downloads template OR uploads their own CSV.
 *   2. Component parses CSV client-side, validates each row, and shows a
 *      preview table with green/yellow/red status indicators.
 *   3. Dealer may edit any cell inline to fix errors before importing.
 *   4. VIN auto-enrichment runs in parallel for all valid rows — fields
 *      not provided by the CSV are filled from the VIN lookup endpoint.
 *   5. "Import N Lots" button → POST /api/vehicle-multi-lot-auctions/{id}/bulk-import.
 *
 * The component requires `eventId` (created on submit; the parent must save
 * the event before opening this dialog so we have an ID to attach lots to).
 *
 * Maximum 50 rows per import (enforced client + server).
 */
import API_BASE from '../../config';
import React, { useMemo, useRef, useState } from 'react';
import axios from 'axios';
import Papa from 'papaparse';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent } from '../../components/ui/card';
import {
  Upload, Download, FileSpreadsheet, CheckCircle, AlertTriangle, XCircle,
  Loader2, X, Search, ChevronRight,
} from 'lucide-react';

const API = API_BASE;

const MAX_LOTS = 50;

// CSV columns — keep in sync with backend `BulkImportLot` schema.
const COLUMNS = [
  'vin', 'year', 'make', 'model', 'trim', 'body_type', 'mileage',
  'engine_size', 'transmission', 'drivetrain', 'fuel_type',
  'exterior_color', 'condition_rating', 'title_status',
  'starting_price_cad', 'reserve_price_cad', 'bid_increment',
  'city', 'province',
  'title_en', 'title_fr', 'description',
];
// Friendly aliases — accept common header variations from the dealer's CSV.
const COL_ALIASES = {
  'starting_price': 'starting_price_cad',
  'reserve_price': 'reserve_price_cad',
  'price': 'starting_price_cad',
  'condition': 'condition_rating',
  'engine': 'engine_size',
  'location_city': 'city',
  'location_province': 'province',
  'title': 'title_en',
};

// Per-row client validation — server re-validates.
const validateRow = (row) => {
  const en = [];
  const fr = [];
  const warnings = [];
  const vin = String(row.vin || '').trim().toUpperCase();
  if (vin.length !== 17) { en.push('VIN must be 17 chars'); fr.push('NIV à 17 caractères'); }
  const year = parseInt(row.year || 0, 10);
  if (!year || year < 1900 || year > 2100) { en.push('Year required (1900-2100)'); fr.push('Année 1900-2100'); }
  if (!String(row.make || '').trim()) { en.push('Make required'); fr.push('Marque requise'); }
  if (!String(row.model || '').trim()) { en.push('Model required'); fr.push('Modèle requis'); }
  const price = parseFloat(row.starting_price_cad || 0);
  if (!price || price <= 0) { en.push('Starting price > 0'); fr.push('Prix de départ > 0'); }
  if (!String(row.city || '').trim()) { en.push('City required'); fr.push('Ville requise'); }
  const province = String(row.province || '').trim().toUpperCase();
  if (!province) { en.push('Province required'); fr.push('Province requise'); }
  if (!String(row.title_en || '').trim()) { en.push('Title (EN) required'); fr.push('Titre (EN) requis'); }
  if (province === 'QC' && !String(row.title_fr || '').trim()) {
    en.push('Bill 96: title_fr required for QC');
    fr.push('Loi 96: titre français requis (QC)');
  }
  if (!row.mileage) { warnings.push({ en: 'Mileage missing (optional)', fr: 'Kilométrage manquant' }); }
  return { en, fr, warnings };
};

const BulkImportLotsCSV = ({ open, onClose, eventId, fr, L, onImported }) => {
  const fileInputRef = useRef(null);
  const [rows, setRows] = useState([]);
  const [parseError, setParseError] = useState('');
  const [importing, setImporting] = useState(false);
  const [enriching, setEnriching] = useState({});

  const stats = useMemo(() => {
    const errs = rows.filter((r) => r._validation.en.length > 0).length;
    const warns = rows.filter((r) => r._validation.en.length === 0 && r._validation.warnings.length > 0).length;
    const ok = rows.length - errs - warns;
    return { ok, warns, errs, total: rows.length };
  }, [rows]);

  const reset = () => {
    setRows([]);
    setParseError('');
    setEnriching({});
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const downloadTemplate = () => {
    // Build a CSV string with header + one example row + one QC example row
    const header = COLUMNS.join(',');
    const lines = [
      header,
      // Bilingual header comment row
      '# vin (17 chars req),year (req),make (req),model (req),trim,body_type,mileage,engine_size,transmission,drivetrain,fuel_type,exterior_color,condition_rating,title_status,starting_price_cad (req),reserve_price_cad,bid_increment,city (req),province (req),title_en (req),title_fr (req for QC),description',
      '1HGBH41JXMN109186,2020,Toyota,Camry,XSE,sedan,52000,2.5L I4,automatic,fwd,gasoline,Pearl White,good,clean,8500,,100,Toronto,ON,2020 Toyota Camry XSE,2020 Toyota Camry XSE,Clean 1-owner trade-in',
      '1FTFW1ET9DFA12345,2019,Ford,F-150,XLT,truck,82000,5.0L V8,automatic,4wd,gasoline,Oxford White,good,clean,12000,15000,100,Montréal,QC,2019 Ford F-150 XLT,2019 Ford F-150 XLT — camion de travail,4x4 work truck',
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'bidvex-lots-template.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    parseFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file) parseFile(file);
  };

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
          const msg = results.errors[0]?.message || 'CSV parse failed';
          setParseError(msg);
          return;
        }
        const data = (results.data || [])
          .filter((r) => Object.values(r).some((v) => String(v || '').trim()))
          .filter((r) => !String(r.vin || '').trim().startsWith('#')); // skip comment rows
        if (data.length === 0) {
          setParseError(L('No data rows found in CSV', 'Aucune ligne de données trouvée'));
          return;
        }
        if (data.length > MAX_LOTS) {
          setParseError(L(`Max ${MAX_LOTS} lots per import. Found ${data.length}.`, `Maximum ${MAX_LOTS} lots. ${data.length} trouvés.`));
          return;
        }
        const enriched = data.map((r, i) => ({
          ...r,
          _row: i + 1,
          _validation: validateRow(r),
          _vinEnriched: false,
        }));
        setRows(enriched);
        // Auto-trigger VIN enrichment in parallel for valid rows
        const token = localStorage.getItem('token');
        const candidates = enriched.filter((r) => String(r.vin || '').trim().length === 17);
        if (candidates.length && token) {
          enrichVins(enriched, token);
        }
      },
      error: (err) => {
        setParseError(err?.message || 'Parse failed');
      },
    });
  };

  // Run VIN lookups in parallel; merge into row only where row left field blank.
  const enrichVins = (currentRows, token) => {
    const tasks = currentRows.map(async (row) => {
      const vin = String(row.vin || '').trim().toUpperCase();
      if (vin.length !== 17) return row;
      setEnriching((m) => ({ ...m, [row._row]: true }));
      try {
        const r = await axios.get(`${API}/vehicles/decode-vin/${vin}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const d = r.data || {};
        // Only fill blanks — never overwrite the CSV's explicit values.
        const merged = { ...row };
        for (const k of ['year', 'make', 'model', 'trim', 'body_type', 'transmission', 'fuel_type', 'drivetrain', 'engine_size']) {
          if (d[k] && !merged[k]) merged[k] = d[k];
        }
        merged._vinEnriched = true;
        merged._validation = validateRow(merged);
        return merged;
      } catch (_e) {
        return { ...row, _vinLookupFailed: true };
      } finally {
        setEnriching((m) => {
          const next = { ...m }; delete next[row._row]; return next;
        });
      }
    });
    Promise.all(tasks).then((updated) => setRows(updated));
  };

  const editCell = (rowIdx, col, value) => {
    setRows((prev) => prev.map((r, i) => {
      if (i !== rowIdx) return r;
      const next = { ...r, [col]: value };
      next._validation = validateRow(next);
      return next;
    }));
  };

  const handleImport = async () => {
    if (!eventId) {
      toast.error(L('Save the event first, then import lots', "Enregistrez d'abord l'événement, puis importez"));
      return;
    }
    if (stats.errs > 0) {
      toast.error(L('Fix all red errors before importing', "Corrigez les erreurs rouges avant l'import"));
      return;
    }
    setImporting(true);
    try {
      const token = localStorage.getItem('token');
      const payload = {
        lots: rows.map((r) => ({
          vin: String(r.vin || '').trim().toUpperCase(),
          year: parseInt(r.year || 0, 10),
          make: String(r.make || '').trim(),
          model: String(r.model || '').trim(),
          trim: String(r.trim || '').trim(),
          body_type: String(r.body_type || 'sedan').trim().toLowerCase(),
          mileage: parseInt(r.mileage || 0, 10),
          engine_size: String(r.engine_size || ''),
          transmission: String(r.transmission || 'automatic').trim().toLowerCase(),
          drivetrain: String(r.drivetrain || 'fwd').trim().toLowerCase(),
          fuel_type: String(r.fuel_type || 'gasoline').trim().toLowerCase(),
          exterior_color: String(r.exterior_color || ''),
          condition_rating: String(r.condition_rating || 'good').trim().toLowerCase(),
          title_status: String(r.title_status || 'clean').trim().toLowerCase(),
          starting_price: parseFloat(r.starting_price_cad || 0),
          reserve_price: r.reserve_price_cad ? parseFloat(r.reserve_price_cad) : null,
          bid_increment: parseFloat(r.bid_increment || 100),
          location_city: String(r.city || '').trim(),
          location_province: String(r.province || '').trim().toUpperCase(),
          title: String(r.title_en || '').trim(),
          title_fr: String(r.title_fr || '').trim(),
          description: String(r.description || '').trim(),
        })),
      };
      const r = await axios.post(`${API}/vehicle-multi-lot-auctions/${eventId}/bulk-import`, payload,
        { headers: { Authorization: `Bearer ${token}` } });
      const created = r.data?.created || 0;
      const serverErrs = r.data?.errors || [];
      if (created > 0) {
        toast.success(L(`Imported ${created} lots — add photos to each before going Live.`, `${created} lots importés — ajoutez des photos avant de mettre en ligne.`));
      }
      if (serverErrs.length) {
        toast.error(L(`${serverErrs.length} row(s) rejected by server. See details.`, `${serverErrs.length} ligne(s) rejetée(s) par le serveur. Voir détails.`));
      }
      onImported?.(r.data);
      reset();
      onClose?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object' ? (fr ? detail.message_fr : detail.message_en) : detail)
        || (fr ? "Échec de l'importation" : 'Import failed');
      toast.error(msg);
    } finally {
      setImporting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[9999] bg-black/70 flex items-center justify-center p-2 sm:p-4" data-testid="bulk-import-modal">
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-2xl w-full max-w-5xl max-h-[92vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-lg sm:text-xl font-semibold flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-blue-600" />
            {L('Import Lots from CSV', 'Importer des lots depuis un CSV')}
          </h2>
          <button onClick={() => { reset(); onClose?.(); }} className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800" data-testid="bulk-import-close-btn">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {rows.length === 0 ? (
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
                    {L('Drag and drop a CSV file here — or click to choose', 'Glissez-déposez un fichier CSV ici — ou cliquez pour choisir')}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    {L(`Maximum ${MAX_LOTS} lots per import.`, `Maximum ${MAX_LOTS} lots par importation.`)}
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
                <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-200" data-testid="bulk-import-parse-error">
                  <AlertTriangle className="h-4 w-4 inline mr-1" />
                  {parseError}
                </div>
              )}
              <div className="flex justify-center">
                <Button variant="outline" onClick={downloadTemplate} data-testid="bulk-import-download-template-btn">
                  <Download className="h-4 w-4 mr-1" />
                  {L('Download CSV Template', 'Télécharger le modèle CSV')}
                </Button>
              </div>
            </>
          ) : (
            <>
              {/* Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="bulk-import-stats">
                <Card><CardContent className="p-3"><p className="text-xl font-bold">{stats.total}</p><p className="text-xs text-slate-500">{L('Total rows', 'Lignes totales')}</p></CardContent></Card>
                <Card><CardContent className="p-3"><p className="text-xl font-bold text-emerald-600">{stats.ok}</p><p className="text-xs text-slate-500">{L('Valid', 'Valides')}</p></CardContent></Card>
                <Card><CardContent className="p-3"><p className="text-xl font-bold text-yellow-600">{stats.warns}</p><p className="text-xs text-slate-500">{L('Warnings', 'Avertissements')}</p></CardContent></Card>
                <Card><CardContent className="p-3"><p className="text-xl font-bold text-rose-600">{stats.errs}</p><p className="text-xs text-slate-500">{L('Errors', 'Erreurs')}</p></CardContent></Card>
              </div>

              {/* Preview table */}
              <div className="overflow-x-auto border border-slate-200 dark:border-slate-700 rounded-lg" data-testid="bulk-import-preview-table">
                <table className="w-full text-xs">
                  <thead className="bg-slate-100 dark:bg-slate-800 text-left">
                    <tr>
                      <th className="p-2">#</th>
                      <th className="p-2">{L('Status', 'Statut')}</th>
                      <th className="p-2">VIN</th>
                      <th className="p-2">{L('Year', 'Année')}</th>
                      <th className="p-2">{L('Make/Model', 'Marque/Modèle')}</th>
                      <th className="p-2">{L('Price', 'Prix')}</th>
                      <th className="p-2">{L('Province', 'Province')}</th>
                      <th className="p-2">{L('Title (EN)', 'Titre (EN)')}</th>
                      <th className="p-2">{L('Title (FR)', 'Titre (FR)')}</th>
                      <th className="p-2">{L('Issues', 'Problèmes')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, idx) => {
                      const err = r._validation.en.length > 0;
                      const warn = !err && r._validation.warnings.length > 0;
                      const ok = !err && !warn;
                      const StatusIcon = err ? XCircle : warn ? AlertTriangle : CheckCircle;
                      const statusColor = err ? 'text-rose-600' : warn ? 'text-yellow-600' : 'text-emerald-600';
                      return (
                        <tr key={idx} className={`border-t border-slate-200 dark:border-slate-700 ${err ? 'bg-rose-50/30 dark:bg-rose-950/10' : warn ? 'bg-yellow-50/30 dark:bg-yellow-950/10' : ''}`} data-testid={`bulk-import-row-${idx}`}>
                          <td className="p-2">{r._row}</td>
                          <td className="p-2"><StatusIcon className={`h-4 w-4 ${statusColor}`} aria-label={ok ? 'OK' : err ? 'Error' : 'Warning'} data-testid={`bulk-import-row-status-${idx}`} /></td>
                          <td className="p-2">
                            <input value={r.vin || ''} onChange={(e) => editCell(idx, 'vin', e.target.value.toUpperCase())} maxLength={17} className="w-32 px-1 py-0.5 font-mono text-xs border rounded" data-testid={`bulk-import-vin-${idx}`} />
                            {enriching[r._row] && <Loader2 className="h-3 w-3 inline ml-1 animate-spin text-blue-500" />}
                            {r._vinLookupFailed && <span className="block text-[10px] text-yellow-700 mt-0.5">{L('VIN not found', 'NIV introuvable')}</span>}
                          </td>
                          <td className="p-2"><input type="number" value={r.year || ''} onChange={(e) => editCell(idx, 'year', e.target.value)} className="w-16 px-1 py-0.5 text-xs border rounded" /></td>
                          <td className="p-2 whitespace-nowrap">
                            <input value={r.make || ''} onChange={(e) => editCell(idx, 'make', e.target.value)} className="w-20 px-1 py-0.5 text-xs border rounded mr-1" />
                            <input value={r.model || ''} onChange={(e) => editCell(idx, 'model', e.target.value)} className="w-24 px-1 py-0.5 text-xs border rounded" />
                          </td>
                          <td className="p-2"><input type="number" value={r.starting_price_cad || ''} onChange={(e) => editCell(idx, 'starting_price_cad', e.target.value)} className="w-20 px-1 py-0.5 text-xs border rounded" /></td>
                          <td className="p-2"><input value={r.province || ''} onChange={(e) => editCell(idx, 'province', e.target.value.toUpperCase())} maxLength={3} className="w-12 px-1 py-0.5 text-xs border rounded uppercase" /></td>
                          <td className="p-2"><input value={r.title_en || ''} onChange={(e) => editCell(idx, 'title_en', e.target.value)} className="w-40 px-1 py-0.5 text-xs border rounded" /></td>
                          <td className="p-2"><input value={r.title_fr || ''} onChange={(e) => editCell(idx, 'title_fr', e.target.value)} className="w-40 px-1 py-0.5 text-xs border rounded" /></td>
                          <td className="p-2 max-w-[200px]">
                            {err && <span className="text-[10px] text-rose-700 block">{fr ? r._validation.fr.join('; ') : r._validation.en.join('; ')}</span>}
                            {warn && <span className="text-[10px] text-yellow-700 block">{(fr ? r._validation.warnings.map((w) => w.fr) : r._validation.warnings.map((w) => w.en)).join('; ')}</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-col-reverse sm:flex-row items-center justify-between gap-2 p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          {rows.length > 0 ? (
            <Button variant="outline" onClick={reset} data-testid="bulk-import-reset-btn">
              <X className="h-4 w-4 mr-1" /> {L('Choose different file', 'Choisir un autre fichier')}
            </Button>
          ) : <div />}
          <div className="flex flex-col-reverse sm:flex-row gap-2 w-full sm:w-auto">
            <Button variant="ghost" onClick={() => { reset(); onClose?.(); }} data-testid="bulk-import-cancel-btn">
              {L('Cancel', 'Annuler')}
            </Button>
            <Button
              onClick={handleImport}
              disabled={importing || rows.length === 0 || stats.errs > 0 || !eventId}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="bulk-import-submit-btn"
            >
              {importing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <ChevronRight className="h-4 w-4 mr-1" />}
              {L(`Import ${stats.ok + stats.warns} Lots`, `Importer ${stats.ok + stats.warns} lots`)}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BulkImportLotsCSV;
