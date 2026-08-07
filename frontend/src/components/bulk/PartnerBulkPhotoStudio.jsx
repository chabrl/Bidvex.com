/**
 * PartnerBulkPhotoStudio — iter444
 *
 * Drag-and-drop photo assignment for bulk-imported drafts.
 * Auto-matches uploaded files to drafts by filename slug of the draft
 * title. Unmatched files land in a tray with click-to-assign. Drafts
 * without at least one photo carry a red "missing photo" pill.
 *
 * Uploads to S3 through the shared `uploadListingImage` utility, then
 * calls POST /api/partner-pro/bulk-import/{listing_id}/photos to attach.
 */
import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import { toast } from 'sonner';
import { Upload, Image as ImageIcon, X, CheckCircle2, AlertTriangle } from 'lucide-react';

import { uploadListingImage } from '../../utils/uploadListingImage';
import API_BASE from '../../config';

const API = API_BASE;

const slugify = (s) =>
  (s || '')
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '')
    .trim();

export const PartnerBulkPhotoStudio = ({ drafts, onDraftUpdate, isFr, token }) => {
  const { t } = useTranslation();
  const [unmatched, setUnmatched] = useState([]);  // [{ id, name, url }]

  const attachToDraft = useCallback(async (listingId, imageUrl) => {
    try {
      const res = await axios.post(
        `${API}/partner-pro/bulk-import/${listingId}/photos`,
        { image_urls: [imageUrl] },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      onDraftUpdate(listingId, {
        image_count: res.data.image_count,
        needs_photos: res.data.needs_photos,
      });
      return true;
    } catch (e) {
      toast.error(t('bulkImport.photoUploadFailed', 'Photo upload failed'));
      return false;
    }
  }, [token, onDraftUpdate, t]);

  const onDrop = useCallback(async (files) => {
    const draftSlugs = drafts.map((d) => ({ id: d.id, slug: slugify(d.title) }));
    const stillUnmatched = [];
    for (const f of files) {
      // Upload first — we need a URL either way.
      let url;
      try {
        url = await uploadListingImage(f);
      } catch (e) {
        toast.error(t('bulkImport.photoUploadFailed', 'Photo upload failed'));
        continue;
      }
      if (!url) continue;

      // Try to auto-match: strip extension → slug → prefix/contains match.
      const fileSlug = slugify(f.name.replace(/\.[^.]+$/, ''));
      const match = draftSlugs.find((d) =>
        d.slug && (fileSlug === d.slug || fileSlug.startsWith(d.slug) || d.slug.startsWith(fileSlug))
      );

      if (match) {
        const ok = await attachToDraft(match.id, url);
        if (!ok) stillUnmatched.push({ id: `${Date.now()}-${f.name}`, name: f.name, url });
      } else {
        stillUnmatched.push({ id: `${Date.now()}-${f.name}`, name: f.name, url });
      }
    }
    if (stillUnmatched.length > 0) {
      setUnmatched((prev) => [...prev, ...stillUnmatched]);
      toast.info(t('bulkImport.noUnmatched', `${stillUnmatched.length} photo(s) awaiting manual assignment.`));
    }
  }, [drafts, attachToDraft, t]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'], 'image/webp': ['.webp'] },
    multiple: true,
  });

  const assignUnmatched = async (unmatchedId, draftId) => {
    const item = unmatched.find((u) => u.id === unmatchedId);
    if (!item) return;
    const ok = await attachToDraft(draftId, item.url);
    if (ok) setUnmatched((prev) => prev.filter((u) => u.id !== unmatchedId));
  };

  const removeUnmatched = (id) => setUnmatched((prev) => prev.filter((u) => u.id !== id));

  const missingCount = drafts.filter((d) => d.needs_photos).length;

  return (
    <div className="space-y-4" data-testid="bulk-photo-studio">
      {/* Drop-zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-cyan-400 bg-cyan-50/60' : 'border-slate-300 hover:border-cyan-400'
        }`}
        data-testid="bulk-photo-dropzone"
      >
        <input {...getInputProps()} data-testid="bulk-photo-file-input" />
        <Upload className="h-8 w-8 mx-auto text-slate-400 mb-2" />
        <p className="font-medium text-slate-700">
          {t('bulkImport.dropPhotos', 'Drop photos here (JPG, PNG, WebP) or click to browse')}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          {t('bulkImport.dropPhotosHint', "Photos with filenames like 'sony_camera_1.jpg' will auto-match by title.")}
        </p>
      </div>

      {/* Missing-photo summary */}
      {missingCount > 0 && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex items-center gap-2"
          data-testid="missing-photo-summary"
        >
          <AlertTriangle className="h-4 w-4" />
          {t('bulkImport.pendingPhotosCount', { count: missingCount })}
        </div>
      )}

      {/* Drafts panel */}
      <section>
        <h3 className="font-semibold text-sm mb-2">{t('bulkImport.listingsPanel', 'Your drafts')}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {drafts.map((d) => (
            <div
              key={d.id}
              className={`rounded-lg border p-3 text-sm ${d.needs_photos ? 'border-red-300 bg-red-50/40' : 'border-emerald-300 bg-emerald-50/40'}`}
              data-testid={`draft-card-${d.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">{d.title}</p>
                  {d.title_fr ? <p className="text-xs text-slate-500 truncate">{d.title_fr}</p> : null}
                </div>
                {d.needs_photos ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-600 text-white text-[10px] font-bold px-2 py-0.5" data-testid={`needs-photo-${d.id}`}>
                    <AlertTriangle className="h-3 w-3" /> {t('bulkImport.needsPhoto', 'Needs 1 photo')}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5" data-testid={`photo-ready-${d.id}`}>
                    <CheckCircle2 className="h-3 w-3" /> {t('bulkImport.photoCount', { count: d.image_count })}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Unmatched panel */}
      <section>
        <h3 className="font-semibold text-sm mb-2">{t('bulkImport.unmatchedPanel', 'Unmatched photos')}</h3>
        {unmatched.length === 0 ? (
          <p className="text-xs text-slate-500 italic">{t('bulkImport.noUnmatched', 'No unmatched photos.')}</p>
        ) : (
          <ul className="divide-y border rounded-lg" data-testid="unmatched-list">
            {unmatched.map((u) => (
              <li key={u.id} className="flex items-center gap-3 p-2 text-sm" data-testid={`unmatched-${u.id}`}>
                <ImageIcon className="h-5 w-5 text-slate-400" />
                <span className="flex-1 truncate">{u.name}</span>
                <select
                  className="text-xs px-2 py-1 border rounded"
                  defaultValue=""
                  onChange={(e) => e.target.value && assignUnmatched(u.id, e.target.value)}
                  data-testid={`assign-${u.id}`}
                >
                  <option value="">{t('bulkImport.assignTo', 'Assign to...')}</option>
                  {drafts.map((d) => (
                    <option key={d.id} value={d.id}>{d.title}</option>
                  ))}
                </select>
                <button
                  onClick={() => removeUnmatched(u.id)}
                  className="text-slate-400 hover:text-red-500"
                  aria-label="Remove"
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

export default PartnerBulkPhotoStudio;
