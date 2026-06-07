/**
 * iter288 — Listing Change-Request Modal (shared across directories).
 *
 * Spawns from the "Edit Listing" or "Request Deletion" CTAs on any
 * /my-{section}/listings page. Forces the user to provide a reason
 * (required by the backend validator) and dispatches the request to
 * `POST /api/listings/{id}/request-change`.
 *
 * Active auctions cannot be edited or deleted directly — the request
 * lands in the admin moderation inbox where it's approved or rejected.
 *
 * Usage:
 *   <ListingChangeRequestModal
 *     listingId={listing.id}
 *     listingLabel="2020 Toyota Camry"
 *     requestType="delete"        // 'edit' | 'delete'
 *     open={showModal}
 *     onClose={() => setShowModal(false)}
 *     onSubmitted={(req) => toast.success(...)}
 *   />
 */
import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { AlertTriangle, Edit, Loader2 } from 'lucide-react';
import API_BASE from '../../config';

const COPY = {
  en: {
    titleEdit:    'Request Listing Edit',
    titleDelete:  'Request Listing Deletion',
    explainEdit:  'Edits to active listings require admin approval. Describe what you want to change so the moderation team can act quickly.',
    explainDel:   'Deletions on active auctions require admin approval. State the reason — typo, accidental listing, sold offline, etc.',
    reasonLabel:  'Reason (required)',
    reasonPh:     'e.g., Typo in VIN data — should be 1FTSW21RXEEAxxxxx',
    cancel:       'Cancel',
    submit:       'Submit Request',
    submitting:   'Submitting…',
    submitted:    'Request submitted — pending admin review',
    duplicate:    'You already have a pending request on this listing.',
    error:        'Could not submit request. Please try again.',
  },
  fr: {
    titleEdit:    "Demande de modification d'annonce",
    titleDelete:  "Demande de suppression d'annonce",
    explainEdit:  "Les modifications sur les annonces actives requièrent une approbation administrative. Décrivez ce que vous voulez changer.",
    explainDel:   "La suppression d'enchères actives requiert une approbation administrative. Indiquez la raison — faute de frappe, annonce accidentelle, vendu hors plateforme, etc.",
    reasonLabel:  'Raison (requise)',
    reasonPh:     'ex. Faute de frappe dans le NIV — devrait être 1FTSW21RXEEAxxxxx',
    cancel:       'Annuler',
    submit:       'Soumettre la demande',
    submitting:   'Soumission…',
    submitted:    'Demande soumise — en attente de révision',
    duplicate:    'Vous avez déjà une demande en attente sur cette annonce.',
    error:        "Impossible de soumettre la demande. Réessayez.",
  },
};

export default function ListingChangeRequestModal({
  listingId,
  listingLabel,
  requestType = 'delete',
  isFr = false,
  open,
  onClose,
  onSubmitted,
  defaultDelta = null,
}) {
  const t = COPY[isFr ? 'fr' : 'en'];
  const [reason, setReason]   = useState('');
  const [busy, setBusy]       = useState(false);

  const handleSubmit = async () => {
    if (reason.trim().length < 3) {
      toast.error(isFr ? 'La raison doit faire au moins 3 caractères.' : 'Reason must be at least 3 characters.');
      return;
    }
    setBusy(true);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      const { data } = await axios.post(
        `${API_BASE}/listings/${listingId}/request-change`,
        {
          request_type:          requestType,
          reason:                reason.trim(),
          current_payload_delta: defaultDelta || {},
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(t.submitted);
      setReason('');
      onSubmitted?.(data?.request);
      onClose?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail?.code === 'duplicate_pending_request') {
        toast.error(t.duplicate);
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error(t.error);
      }
    } finally {
      setBusy(false);
    }
  };

  const isDelete = requestType === 'delete';

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent data-testid="listing-change-request-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isDelete ? <AlertTriangle className="h-5 w-5 text-rose-600" /> : <Edit className="h-5 w-5" />}
            {isDelete ? t.titleDelete : t.titleEdit}
          </DialogTitle>
        </DialogHeader>
        {listingLabel && (
          <p className="text-sm font-semibold text-slate-700" data-testid="listing-change-request-label">
            {listingLabel}
          </p>
        )}
        <p className="text-xs text-slate-500">{isDelete ? t.explainDel : t.explainEdit}</p>
        <div className="space-y-2 mt-3">
          <Label htmlFor="listing-request-reason">{t.reasonLabel}</Label>
          <Textarea
            id="listing-request-reason"
            data-testid="listing-change-request-reason"
            placeholder={t.reasonPh}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            disabled={busy}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={busy}
            data-testid="listing-change-request-cancel"
          >
            {t.cancel}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={busy || reason.trim().length < 3}
            data-testid="listing-change-request-submit"
            className={isDelete ? 'bg-rose-600 hover:bg-rose-700 text-white' : ''}
          >
            {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
            {busy ? t.submitting : t.submit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
