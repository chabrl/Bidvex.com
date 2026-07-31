/**
 * BidVex — Phase 6.2 Task 4 / Phase 6.3 Task 3
 * Buyer-facing "My Cleanouts" page.
 *
 * Shows every won storage-locker invoice that has an active cleanout hold,
 * with a live countdown ticker. The "🧼 Mark Unit as Completely Cleared" CTA
 * now opens an inline file-uploader drawer that REQUIRES at least one
 * broom-swept photo before the request-clearance API call is dispatched.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Loader2, Upload, X } from 'lucide-react';

import CleanoutCountdownTicker from '../../components/CleanoutCountdownTicker';
import { authHeaders } from '../../utils/authToken';
import { uploadListingImage } from '../../utils/uploadListingImage';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function MyCleanoutsPage() {
  const { t } = useTranslation();
  const [holds, setHolds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submittingId, setSubmittingId] = useState(null);
  // Phase 6.3 Task 3 — Drawer state: which invoice is in upload mode + the
  // attached photos for that invoice (as base64 data URLs).
  const [uploadDrawerFor, setUploadDrawerFor] = useState(null);
  const [photosByInvoice, setPhotosByInvoice] = useState({});
  const fileInputRef = useRef(null);

  const fetchHolds = useCallback(async () => {
    setLoading(true);
    try {
      const headers = authHeaders();
      // Reuse the existing buyer-storage-deposits endpoint as the source of
      // won invoices. We hydrate cleanout status per-row via the new endpoint.
      const res = await axios.get(`${API}/api/storage-auctions/my-bids`, { headers });
      const won = (res.data?.bids || []).filter(
        (b) => b.status === 'won' && b.invoice_id,
      );
      const enriched = await Promise.all(
        won.map(async (b) => {
          try {
            const sr = await axios.get(
              `${API}/api/storage-cleanout/${b.invoice_id}/status`,
              { headers },
            );
            return { ...b, cleanout: sr.data };
          } catch (e) {
            console.debug('[cleanouts] status fetch failed:', e);
            return { ...b, cleanout: { has_hold: false } };
          }
        }),
      );
      setHolds(enriched.filter((b) => b.cleanout?.has_hold));
    } catch (e) {
      console.error('Failed to load cleanouts', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHolds();
  }, [fetchHolds]);

  // iter440 — Upload each broom-swept photo to S3 via
  // /api/uploads/listing-image and store the returned URL. The old
  // behaviour (readAsDataURL → base64 URLs stored inline in the
  // clearance-request payload) triggered the API-level base64
  // guardrail and inflated Mongo documents beyond the 16 MB limit.

  const handlePhotoSelect = async (invoiceId, files) => {
    const valid = Array.from(files || []).filter((f) => f.type.startsWith('image/'));
    if (valid.length === 0) {
      toast.error(t('cleanouts.photoMustBeImage', 'Please select an image file.'));
      return;
    }
    try {
      const urls = await Promise.all(valid.map((f) => uploadListingImage(f)));
      setPhotosByInvoice((prev) => ({
        ...prev,
        [invoiceId]: [...(prev[invoiceId] || []), ...urls],
      }));
    } catch (err) {
      console.error('[Cleanouts] photo upload failed:', err);
      toast.error(t('cleanouts.photoUploadFailed', 'Photo upload failed. Please try again.'));
    }
  };

  const removePhoto = (invoiceId, idx) => {
    setPhotosByInvoice((prev) => ({
      ...prev,
      [invoiceId]: (prev[invoiceId] || []).filter((_, i) => i !== idx),
    }));
  };

  const handleMarkCleared = async (invoiceId) => {
    const photos = photosByInvoice[invoiceId] || [];
    // Phase 6.3 Task 3 — Client-side validation: at least 1 photo required.
    if (photos.length === 0) {
      toast.error(t('cleanouts.photoRequired', 'Please attach at least one photo of the empty, broom-swept unit before submitting.'));
      return;
    }
    if (!window.confirm(
      t('cleanouts.confirmMarkCleared', {
        defaultValue:
          'Confirm: have you fully cleared this unit and removed all items? An admin will physically verify before your deposit is released. Misrepresentation may result in forfeit.',
      }),
    )) {
      return;
    }
    setSubmittingId(invoiceId);
    try {
      await axios.post(
        `${API}/api/storage-cleanout/${invoiceId}/request-clearance`,
        { notes: '', photos },
        { headers: authHeaders() },
      );
      toast.success(t('cleanouts.requestedSuccess', 'Clearance requested. Awaiting admin verification.'));
      // Clear state for this invoice
      setPhotosByInvoice((prev) => {
        const next = { ...prev };
        delete next[invoiceId];
        return next;
      });
      setUploadDrawerFor(null);
      await fetchHolds();
    } catch (e) {
      console.error(e);
      toast.error(
        e?.response?.data?.detail?.message_en
        || t('cleanouts.requestedError', 'Failed to request clearance. Please contact support.'),
      );
    } finally {
      setSubmittingId(null);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-12 text-center" data-testid="cleanouts-loading">
        <Loader2 className="h-8 w-8 animate-spin mx-auto" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl" data-testid="my-cleanouts-page">
      <h1 className="text-2xl sm:text-3xl font-bold mb-2">
        {t('cleanouts.heading', 'My Storage Cleanouts')}
      </h1>
      <p className="text-sm text-muted-foreground mb-6">
        {t('cleanouts.subheading', 'Track the cleanout deadline for every storage locker you have won. Your security deposit is released after admin verification.')}
      </p>

      {holds.length === 0 && (
        <div className="text-center py-16 border rounded-lg" data-testid="cleanouts-empty">
          <p className="text-muted-foreground">
            {t('cleanouts.empty', 'No active cleanout holds. Won storage auctions will appear here.')}
          </p>
        </div>
      )}

      <div className="space-y-4">
        {holds.map((h) => {
          const c = h.cleanout || {};
          const isRequested = c.status === 'pending_verification';
          const isResolved = ['released', 'forfeited', 'captured'].includes(c.status);
          return (
            <Card key={h.invoice_id} className="overflow-hidden" data-testid={`cleanout-card-${h.invoice_id}`}>
              <CardHeader>
                <CardTitle className="text-base sm:text-lg break-words">
                  {h.listing_title || h.facility_name || 'Storage Unit'}
                </CardTitle>
                {h.facility_name && (
                  <p className="text-xs text-muted-foreground">{h.facility_name}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                <CleanoutCountdownTicker deadlineAt={c.deadline_at} status={c.status} />

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-muted-foreground text-xs">{t('cleanouts.depositHeld', 'Deposit Held')}</div>
                    <div className="font-semibold">${Number(c.amount_cad || 0).toFixed(2)} CAD</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">{t('cleanouts.windowHours', 'Cleanout Window')}</div>
                    <div className="font-semibold">{c.cleanout_deadline_hours || 72}h</div>
                  </div>
                </div>

                {!isResolved && !isRequested && (
                  <>
                    {uploadDrawerFor !== h.invoice_id ? (
                      <Button
                        onClick={() => setUploadDrawerFor(h.invoice_id)}
                        className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                        data-testid={`mark-cleared-btn-${h.invoice_id}`}
                      >
                        🧼 {t('cleanouts.markCleared', 'Mark Unit as Completely Cleared')}
                      </Button>
                    ) : (
                      <div className="rounded-md border border-emerald-300 bg-emerald-50/40 dark:bg-emerald-900/10 p-3 space-y-3" data-testid={`upload-drawer-${h.invoice_id}`}>
                        <div className="text-xs font-semibold text-emerald-900 dark:text-emerald-200">
                          {t('cleanouts.uploadPrompt', 'Attach at least 1 photo of the empty, broom-swept unit.')}
                        </div>
                        {/* File input */}
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          ref={fileInputRef}
                          onChange={(e) => handlePhotoSelect(h.invoice_id, e.target.files)}
                          className="hidden"
                          data-testid={`upload-input-${h.invoice_id}`}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => fileInputRef.current?.click()}
                          className="w-full"
                          data-testid={`upload-trigger-${h.invoice_id}`}
                        >
                          <Upload className="h-4 w-4 mr-1.5" />
                          {t('cleanouts.choosePhotos', 'Choose Photos')}
                        </Button>

                        {/* Thumbnails */}
                        {(photosByInvoice[h.invoice_id] || []).length > 0 && (
                          <div className="grid grid-cols-3 gap-1.5" data-testid={`upload-thumbs-${h.invoice_id}`}>
                            {(photosByInvoice[h.invoice_id] || []).map((src, idx) => (
                              <div key={idx} className="relative aspect-square rounded overflow-hidden bg-slate-200">
                                <img src={src} alt={`Cleanout proof ${idx + 1}`} className="w-full h-full object-cover" />
                                <button
                                  type="button"
                                  onClick={() => removePhoto(h.invoice_id, idx)}
                                  className="absolute top-0.5 right-0.5 bg-red-600 text-white rounded-full p-0.5 hover:bg-red-700"
                                  aria-label="Remove photo"
                                  data-testid={`upload-remove-${h.invoice_id}-${idx}`}
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="text-[10px] text-muted-foreground">
                          {((photosByInvoice[h.invoice_id] || []).length)} {(photosByInvoice[h.invoice_id] || []).length === 1 ? 'photo' : 'photos'} attached
                        </div>

                        <div className="flex gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => { setUploadDrawerFor(null); }}
                            className="flex-1"
                            data-testid={`upload-cancel-${h.invoice_id}`}
                          >
                            {t('common.cancel', 'Cancel')}
                          </Button>
                          <Button
                            onClick={() => handleMarkCleared(h.invoice_id)}
                            disabled={submittingId === h.invoice_id || (photosByInvoice[h.invoice_id] || []).length === 0}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                            data-testid={`upload-submit-${h.invoice_id}`}
                          >
                            {submittingId === h.invoice_id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <>{t('cleanouts.submitClearance', 'Submit Clearance')}</>
                            )}
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                )}
                {isRequested && (
                  <div className="rounded-md bg-amber-50 border border-amber-300 px-3 py-2 text-xs text-amber-900" data-testid={`cleanout-pending-${h.invoice_id}`}>
                    ⏳ {t('cleanouts.pendingAdminVerification', 'Clearance requested. Awaiting admin verification before deposit is released.')}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
