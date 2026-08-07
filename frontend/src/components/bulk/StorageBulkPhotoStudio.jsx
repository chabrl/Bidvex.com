/**
 * StorageBulkPhotoStudio — iter446
 *
 * Unit Photo Studio for bulk-imported storage-auction drafts.
 *
 * • Facility drops a group of photos.
 * • Each file is uploaded via POST /api/storage-facilities/upload-photo
 *   to get a public URL (namespaced per facility).
 * • The client auto-matches the filename to a draft's `unit_number`
 *   using a permissive fuzzy match (case-insensitive substring +
 *   alphanumeric-only comparison + digit-suffix). Longest unit_number
 *   wins so "A-101" beats "A-1" in "photo-A-101.jpg".
 * • Matched photos are attached via
 *   POST /api/storage-facilities/bulk-import/{auction_id}/photos.
 * • Unmatched photos sit in a tray with a "Assign to..." dropdown.
 * • Every draft carries a red "Needs 1 photo" pill or a green
 *   "N photo(s)" pill so the facility can see publish-eligibility.
 *
 * NO draft is published from this component. Publish happens in Step 5.
 */
import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Upload, Image as ImageIcon, X, CheckCircle2, AlertTriangle, Loader2,
} from 'lucide-react';

import API_BASE from '../../config';

const API = API_BASE;

const stripExt = (name) => (name || '').replace(/\.[^.]+$/, '');
const alnum = (s) => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const digitsOnly = (s) => (s || '').replace(/[^0-9]/g, '');

/**
 * Fuzzy-match a filename stem to a draft `unit_number`.
 * Tries progressively looser tokens; longest unit_number first so
 * multi-digit numbers win over single-digit prefixes.
 */
const matchUnit = (filename, drafts) => {
  const stem = stripExt(filename || '').toLowerCase();
  const stemAlnum = alnum(stem);
  if (!stem || !drafts.length) return null;

  const sorted = [...drafts].sort(
    (a, b) => (b.unit_number || '').length - (a.unit_number || '').length
  );
  for (const d of sorted) {
    const u = (d.unit_number || '').toLowerCase().trim();
    if (!u) continue;
    if (stem.includes(u)) return d;
    const ua = alnum(u);
    if (ua && stemAlnum.includes(ua)) return d;
    const ud = digitsOnly(u);
    if (ud && ud.length >= 2 && stemAlnum.includes(ud)) return d;
  }
  return null;
};

export const StorageBulkPhotoStudio = ({ drafts, onDraftUpdate, isFr, token }) => {
  const { t } = useTranslation();
  const [unmatched, setUnmatched] = useState([]); // [{ id, name, url }]
  const [uploading, setUploading] = useState(false);

  const uploadOne = useCallback(async (file) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await axios.post(
      `${API}/storage-facilities/upload-photo`,
      fd,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return res?.data?.url || null;
  }, [token]);

  const attachToDraft = useCallback(async (auctionId, imageUrl) => {
    try {
      const res = await axios.post(
        `${API}/storage-facilities/bulk-import/${auctionId}/photos`,
        { image_urls: [imageUrl] },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      onDraftUpdate(auctionId, {
        image_count: res.data.image_count,
        needs_photos: res.data.needs_photos,
      });
      return true;
    } catch (e) {
      toast.error(
        isFr
          ? 'Échec de l\'ajout de la photo au brouillon'
          : 'Failed to attach photo to draft'
      );
      return false;
    }
  }, [token, onDraftUpdate, isFr]);

  const onDrop = useCallback(async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const stillUnmatched = [];
    try {
      for (const f of files) {
        let url;
        try {
          url = await uploadOne(f);
        } catch (e) {
          toast.error(
            isFr ? 'Échec du téléversement de la photo' : 'Photo upload failed'
          );
          continue;
        }
        if (!url) continue;

        const match = matchUnit(f.name, drafts);
        if (match) {
          const ok = await attachToDraft(match.id, url);
          if (!ok) {
            stillUnmatched.push({
              id: `${Date.now()}-${f.name}`, name: f.name, url,
            });
          } else {
            toast.success(
              isFr
                ? `Photo attribuée à l'unité ${match.unit_number}`
                : `Photo assigned to unit ${match.unit_number}`
            );
          }
        } else {
          stillUnmatched.push({
            id: `${Date.now()}-${f.name}`, name: f.name, url,
          });
        }
      }
      if (stillUnmatched.length > 0) {
        setUnmatched((prev) => [...prev, ...stillUnmatched]);
        toast.info(
          isFr
            ? `${stillUnmatched.length} photo(s) en attente d'attribution manuelle.`
            : `${stillUnmatched.length} photo(s) awaiting manual assignment.`
        );
      }
    } finally {
      setUploading(false);
    }
  }, [drafts, attachToDraft, uploadOne, isFr]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
    },
    multiple: true,
    disabled: uploading,
  });

  const assignUnmatched = async (unmatchedId, auctionId) => {
    const item = unmatched.find((u) => u.id === unmatchedId);
    if (!item || !auctionId) return;
    const ok = await attachToDraft(auctionId, item.url);
    if (ok) setUnmatched((prev) => prev.filter((u) => u.id !== unmatchedId));
  };

  const removeUnmatched = (id) =>
    setUnmatched((prev) => prev.filter((u) => u.id !== id));

  const missingCount = drafts.filter((d) => d.needs_photos).length;

  return (
    <div className="space-y-4" data-testid="storage-bulk-photo-studio">
      {/* Drop-zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-cyan-400 bg-cyan-50/60'
            : uploading
              ? 'border-slate-300 bg-slate-100/70 cursor-wait'
              : 'border-slate-300 hover:border-cyan-400'
        }`}
        data-testid="storage-bulk-photo-dropzone"
      >
        <input {...getInputProps()} data-testid="storage-bulk-photo-file-input" />
        {uploading ? (
          <Loader2 className="h-8 w-8 mx-auto text-cyan-500 mb-2 animate-spin" />
        ) : (
          <Upload className="h-8 w-8 mx-auto text-slate-400 mb-2" />
        )}
        <p className="font-medium text-slate-700">
          {isFr
            ? 'Déposez les photos ici (JPG, PNG, WebP) ou cliquez pour parcourir'
            : 'Drop photos here (JPG, PNG, WebP) or click to browse'}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          {isFr
            ? "Les fichiers nommés comme « A-101_front.jpg » ou « unit_B42.png » sont attribués automatiquement au numéro d'unité correspondant."
            : "Files named like 'A-101_front.jpg' or 'unit_B42.png' auto-match to their unit number."}
        </p>
      </div>

      {/* Missing-photo summary */}
      {missingCount > 0 && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex items-center gap-2"
          data-testid="storage-missing-photo-summary"
        >
          <AlertTriangle className="h-4 w-4" />
          {isFr
            ? `${missingCount} unité(s) sans photo — au moins une photo requise avant la publication.`
            : `${missingCount} unit(s) missing a photo — at least one photo is required to publish.`}
        </div>
      )}

      {/* Drafts panel */}
      <section>
        <h3 className="font-semibold text-sm mb-2">
          {isFr ? 'Vos unités brouillon' : 'Your draft units'}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {drafts.map((d) => (
            <div
              key={d.id}
              className={`rounded-lg border p-3 text-sm ${
                d.needs_photos
                  ? 'border-red-300 bg-red-50/40'
                  : 'border-emerald-300 bg-emerald-50/40'
              }`}
              data-testid={`storage-draft-card-${d.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">
                    {isFr ? 'Unité' : 'Unit'} {d.unit_number}
                  </p>
                  <p className="text-xs text-slate-500 truncate">
                    {d.unit_size} · {d.unit_type}
                  </p>
                </div>
                {d.needs_photos ? (
                  <span
                    className="inline-flex items-center gap-1 rounded-full bg-red-600 text-white text-[10px] font-bold px-2 py-0.5"
                    data-testid={`storage-needs-photo-${d.id}`}
                  >
                    <AlertTriangle className="h-3 w-3" />
                    {isFr ? 'Photo requise' : 'Needs 1 photo'}
                  </span>
                ) : (
                  <span
                    className="inline-flex items-center gap-1 rounded-full bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5"
                    data-testid={`storage-photo-ready-${d.id}`}
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    {d.image_count} {isFr ? 'photo(s)' : 'photo(s)'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Unmatched panel */}
      <section>
        <h3 className="font-semibold text-sm mb-2">
          {isFr ? 'Photos non attribuées' : 'Unmatched photos'}
        </h3>
        {unmatched.length === 0 ? (
          <p className="text-xs text-slate-500 italic" data-testid="storage-no-unmatched">
            {isFr
              ? 'Aucune photo non attribuée.'
              : 'No unmatched photos.'}
          </p>
        ) : (
          <ul
            className="divide-y border rounded-lg"
            data-testid="storage-unmatched-list"
          >
            {unmatched.map((u) => (
              <li
                key={u.id}
                className="flex items-center gap-3 p-2 text-sm"
                data-testid={`storage-unmatched-${u.id}`}
              >
                <ImageIcon className="h-5 w-5 text-slate-400" />
                <span className="flex-1 truncate">{u.name}</span>
                <select
                  className="text-xs px-2 py-1 border rounded"
                  defaultValue=""
                  onChange={(e) =>
                    e.target.value && assignUnmatched(u.id, e.target.value)
                  }
                  data-testid={`storage-assign-${u.id}`}
                >
                  <option value="">
                    {isFr ? 'Attribuer à…' : 'Assign to…'}
                  </option>
                  {drafts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {isFr ? 'Unité' : 'Unit'} {d.unit_number}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => removeUnmatched(u.id)}
                  className="text-slate-400 hover:text-red-500"
                  aria-label={isFr ? 'Retirer' : 'Remove'}
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

export default StorageBulkPhotoStudio;
