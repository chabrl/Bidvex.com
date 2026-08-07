/**
 * VehicleBulkPhotoStudio — iter447
 *
 * Photo Studio for bulk-imported multi-lot vehicles.
 *
 * Auto-matching rule (per user directive):
 *   1. Try FULL 17-character VIN in the filename first.
 *   2. If not found, try the LAST 8 characters of each VIN, but ONLY if
 *      exactly one lot in the current batch has that suffix.
 *   3. If still not found, try the LAST 6 characters, again ONLY when
 *      exactly one lot in the batch has that suffix.
 *   4. Anything ambiguous or unmatched drops into the Unmatched tray
 *      for MANUAL assignment. A wrong automatic match is worse than
 *      asking the dealer to click.
 *
 * NO stock-number fallback. Matching is VIN-only.
 *
 * Publish gate: parent should disable "Go Live" until every lot has
 * media.length >= 1. Server also blocks activate on this condition.
 * The existing `_MAX_PHOTOS_PER_LOT = 20` per-lot cap is honoured.
 */
import React, { useCallback, useMemo, useState } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import { toast } from 'sonner';
import {
  Upload, ImageIcon, X, CheckCircle2, AlertTriangle, Loader2, Camera,
} from 'lucide-react';

import API_BASE from '../../config';
import { matchByVin } from './vinPhotoMatcher';

const API = API_BASE;
const MAX_PHOTOS_PER_LOT = 20;

const VehicleBulkPhotoStudio = ({
  eventId,
  lots,
  onLotUpdated,
  isFr,
  token,
  L,
}) => {
  const [uploading, setUploading] = useState(false);
  const [unmatched, setUnmatched] = useState([]); // [{id, name, url}]

  const missingCount = useMemo(
    () => lots.filter((l) => !(l.media && l.media.length > 0)).length,
    [lots]
  );

  const uploadOne = useCallback(async (file, lotId) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await axios.post(
      `${API}/vehicle-multi-lot-auctions/${eventId}/lots/${lotId}/photos`,
      fd,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return res.data;
  }, [eventId, token]);

  // For truly unmatched files we still need a URL somewhere so the
  // dealer can preview + assign later. We push those to the dropzone
  // temporary object-URL for preview only; the actual upload happens
  // when they choose a target lot.
  const [pendingBlobs, setPendingBlobs] = useState({}); // { id: File }

  const onDrop = useCallback(async (files) => {
    if (!files || !files.length || !eventId) return;
    setUploading(true);
    const stillUnmatched = [];
    try {
      for (const f of files) {
        const match = matchByVin(f.name, lots);
        if (match) {
          if ((match.media || []).length >= MAX_PHOTOS_PER_LOT) {
            toast.error(L(
              `Lot ${match.vin?.slice(-6)} is already at the ${MAX_PHOTOS_PER_LOT}-photo cap`,
              `Le lot ${match.vin?.slice(-6)} a déjà atteint le plafond de ${MAX_PHOTOS_PER_LOT} photos`
            ));
            continue;
          }
          try {
            const updatedLot = await uploadOne(f, match.id);
            onLotUpdated(match.id, updatedLot);
            toast.success(L(
              `Photo attached to VIN …${match.vin?.slice(-6)}`,
              `Photo attribuée au NIV …${match.vin?.slice(-6)}`
            ));
          } catch (e) {
            toast.error(L('Photo upload failed', 'Échec du téléversement'));
          }
        } else {
          const id = `${Date.now()}-${f.name}-${Math.random().toString(36).slice(2, 6)}`;
          const objectUrl = URL.createObjectURL(f);
          stillUnmatched.push({ id, name: f.name, url: objectUrl });
          setPendingBlobs((m) => ({ ...m, [id]: f }));
        }
      }
      if (stillUnmatched.length > 0) {
        setUnmatched((prev) => [...prev, ...stillUnmatched]);
        toast.info(L(
          `${stillUnmatched.length} photo(s) awaiting manual assignment.`,
          `${stillUnmatched.length} photo(s) en attente d'attribution manuelle.`
        ));
      }
    } finally {
      setUploading(false);
    }
  }, [eventId, lots, uploadOne, onLotUpdated, L]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
    },
    multiple: true,
    disabled: uploading || !eventId,
  });

  const assignUnmatched = async (unmatchedId, lotId) => {
    const item = unmatched.find((u) => u.id === unmatchedId);
    const blob = pendingBlobs[unmatchedId];
    if (!item || !blob || !lotId) return;
    const lot = lots.find((l) => l.id === lotId);
    if (lot && (lot.media || []).length >= MAX_PHOTOS_PER_LOT) {
      toast.error(L(
        `Lot at the ${MAX_PHOTOS_PER_LOT}-photo cap`,
        `Lot au plafond de ${MAX_PHOTOS_PER_LOT} photos`
      ));
      return;
    }
    try {
      const updatedLot = await uploadOne(blob, lotId);
      onLotUpdated(lotId, updatedLot);
      URL.revokeObjectURL(item.url);
      setUnmatched((prev) => prev.filter((u) => u.id !== unmatchedId));
      setPendingBlobs((m) => {
        const n = { ...m }; delete n[unmatchedId]; return n;
      });
      toast.success(L('Photo attached', 'Photo attribuée'));
    } catch (e) {
      toast.error(L('Photo upload failed', 'Échec du téléversement'));
    }
  };

  const removeUnmatched = (id) => {
    const item = unmatched.find((u) => u.id === id);
    if (item?.url) URL.revokeObjectURL(item.url);
    setUnmatched((prev) => prev.filter((u) => u.id !== id));
    setPendingBlobs((m) => {
      const n = { ...m }; delete n[id]; return n;
    });
  };

  return (
    <div className="space-y-4" data-testid="vehicle-bulk-photo-studio">
      {/* Drop-zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-400 bg-blue-50/60'
            : uploading
              ? 'border-slate-300 bg-slate-100/70 cursor-wait'
              : 'border-slate-300 hover:border-blue-400'
        }`}
        data-testid="vehicle-bulk-photo-dropzone"
      >
        <input {...getInputProps()} data-testid="vehicle-bulk-photo-file-input" />
        {uploading ? (
          <Loader2 className="h-8 w-8 mx-auto text-blue-500 mb-2 animate-spin" />
        ) : (
          <Upload className="h-8 w-8 mx-auto text-slate-400 mb-2" />
        )}
        <p className="font-medium text-slate-700">
          {L(
            'Drop vehicle photos here (JPG, PNG, WebP)',
            'Déposez ici les photos des véhicules (JPG, PNG, WebP)'
          )}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          {L(
            'Files whose name contains a full VIN (or an unambiguous last-8 / last-6 VIN suffix) are attached automatically. Everything else lands in the Unmatched tray for manual assignment.',
            "Les fichiers dont le nom contient un NIV complet (ou un suffixe non ambigu de 8 ou 6 caractères) sont attribués automatiquement. Tout le reste apparaît dans le bac « Non attribuées » pour une attribution manuelle."
          )}
        </p>
      </div>

      {/* Missing-photo summary */}
      {missingCount > 0 && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex items-center gap-2"
          data-testid="vehicle-bulk-missing-summary"
        >
          <AlertTriangle className="h-4 w-4" />
          {L(
            `${missingCount} lot(s) missing a photo — at least one photo per lot is required to go live.`,
            `${missingCount} lot(s) sans photo — au moins une photo par lot est requise pour passer en direct.`
          )}
        </div>
      )}

      {/* Lots panel */}
      <section>
        <h3 className="font-semibold text-sm mb-2 flex items-center gap-2">
          <Camera className="h-4 w-4" />
          {L('Your lots', 'Vos lots')} ({lots.length})
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[380px] overflow-y-auto pr-1">
          {lots.map((l) => {
            const count = (l.media || []).length;
            const needs = count < 1;
            const short = (l.vin || '').slice(-6);
            return (
              <div
                key={l.id}
                className={`rounded-lg border p-3 text-sm ${
                  needs
                    ? 'border-red-300 bg-red-50/40'
                    : 'border-emerald-300 bg-emerald-50/40'
                }`}
                data-testid={`vehicle-bulk-lot-card-${l.id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900 truncate">
                      {l.year} {l.make} {l.model}
                    </p>
                    <p className="text-[11px] text-slate-500 font-mono truncate">
                      VIN …{short}
                    </p>
                  </div>
                  {needs ? (
                    <span
                      className="inline-flex items-center gap-1 rounded-full bg-red-600 text-white text-[10px] font-bold px-2 py-0.5"
                      data-testid={`vehicle-bulk-needs-photo-${l.id}`}
                    >
                      <AlertTriangle className="h-3 w-3" />
                      {L('Needs 1 photo', 'Photo requise')}
                    </span>
                  ) : (
                    <span
                      className="inline-flex items-center gap-1 rounded-full bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5"
                      data-testid={`vehicle-bulk-photo-ready-${l.id}`}
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      {count} / {MAX_PHOTOS_PER_LOT}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Unmatched tray */}
      <section>
        <h3 className="font-semibold text-sm mb-2">
          {L('Unmatched photos', 'Photos non attribuées')}
        </h3>
        {unmatched.length === 0 ? (
          <p
            className="text-xs text-slate-500 italic"
            data-testid="vehicle-bulk-no-unmatched"
          >
            {L('No unmatched photos.', 'Aucune photo non attribuée.')}
          </p>
        ) : (
          <ul
            className="divide-y border rounded-lg"
            data-testid="vehicle-bulk-unmatched-list"
          >
            {unmatched.map((u) => (
              <li
                key={u.id}
                className="flex items-center gap-3 p-2 text-sm"
                data-testid={`vehicle-bulk-unmatched-${u.id}`}
              >
                <img
                  src={u.url}
                  alt=""
                  className="h-10 w-10 object-cover rounded border"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
                <span className="flex-1 truncate">{u.name}</span>
                <select
                  className="text-xs px-2 py-1 border rounded"
                  defaultValue=""
                  onChange={(e) =>
                    e.target.value && assignUnmatched(u.id, e.target.value)
                  }
                  data-testid={`vehicle-bulk-assign-${u.id}`}
                >
                  <option value="">
                    {L('Assign to lot…', 'Attribuer au lot…')}
                  </option>
                  {lots.map((l) => (
                    <option
                      key={l.id}
                      value={l.id}
                      disabled={(l.media || []).length >= MAX_PHOTOS_PER_LOT}
                    >
                      VIN …{(l.vin || '').slice(-6)} — {l.year} {l.make} {l.model}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => removeUnmatched(u.id)}
                  className="text-slate-400 hover:text-red-500"
                  aria-label={L('Remove', 'Retirer')}
                  data-testid={`vehicle-bulk-unmatched-remove-${u.id}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};

export default VehicleBulkPhotoStudio;
