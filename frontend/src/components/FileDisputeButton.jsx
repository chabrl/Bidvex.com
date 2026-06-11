import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Button } from './ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from './ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { Textarea } from './ui/textarea';
import { AlertTriangle, Loader2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

const API = API_BASE;

/**
 * iter300 P1 — "File a Dispute" button + form.
 *
 * Self-hides unless the current user is the buyer or seller of a
 * payment_collected listing within the 7-day post-close window
 * (eligibility computed server-side: GET /api/disputes/eligibility/:id).
 */
export const FileDisputeButton = ({ listingId, section = 'marketplace', className = '' }) => {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const isFrench = (i18n.language || 'en').startsWith('fr');

  const [elig, setElig] = useState(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchEligibility = useCallback(async () => {
    if (!token || !listingId) return;
    try {
      const res = await axios.get(
        `${API}/disputes/eligibility/${listingId}?section=${section}`,
        { headers: { Authorization: `Bearer ${token}` } });
      setElig(res.data);
    } catch { setElig(null); }
  }, [token, listingId, section]);

  useEffect(() => { fetchEligibility(); }, [fetchEligibility]);

  if (!elig) return null;
  if (elig.already_disputed) {
    return (
      <div className={`flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 ${className}`}
        data-testid="dispute-already-filed">
        <ShieldAlert className="h-4 w-4 shrink-0" />
        {isFrench
          ? `Litige ${elig.dispute_status === 'resolved' ? 'résolu' : 'en cours d\u2019examen'} pour cette transaction.`
          : `A dispute is ${elig.dispute_status === 'resolved' ? 'resolved' : 'under review'} for this transaction.`}
      </div>
    );
  }
  if (!elig.eligible) return null;

  const REASONS = [
    { value: 'item_not_as_described', en: 'Item not as described', fr: 'Article non conforme à la description' },
    { value: 'no_contact_from_seller', en: 'No contact from seller', fr: 'Aucun contact du vendeur' },
    { value: 'payment_issue', en: 'Payment issue', fr: 'Problème de paiement' },
    { value: 'other', en: 'Other', fr: 'Autre' },
  ];

  const submit = async () => {
    if (!reason) {
      toast.error(isFrench ? 'Sélectionnez une raison' : 'Please select a reason');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/disputes/file`,
        { listing_id: listingId, section, reason_category: reason, details },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(isFrench
        ? 'Votre litige a été reçu et est en cours d\u2019examen'
        : 'Your dispute has been received and is under review');
      setOpen(false);
      fetchEligibility();
    } catch (err) {
      toast.error(err.response?.data?.detail || (isFrench ? 'Échec du dépôt du litige' : 'Failed to file dispute'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Button
        variant="outline"
        className={`border-red-300 text-red-700 hover:bg-red-50 ${className}`}
        onClick={() => setOpen(true)}
        data-testid="file-dispute-btn"
      >
        <AlertTriangle className="h-4 w-4 mr-2" />
        {isFrench ? 'Déposer un litige' : 'File a Dispute'}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="file-dispute-dialog">
          <DialogHeader>
            <DialogTitle>{isFrench ? 'Déposer un litige' : 'File a Dispute'}</DialogTitle>
            <DialogDescription>
              {isFrench
                ? 'Notre équipe examinera votre litige et contactera les deux parties. Disponible pendant 7 jours après la clôture de l\u2019enchère.'
                : 'Our team will review your dispute and contact both parties. Available for 7 days after auction close.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium mb-1.5 block">
                {isFrench ? 'Raison' : 'Reason'} <span className="text-red-500">*</span>
              </label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger data-testid="dispute-reason-select">
                  <SelectValue placeholder={isFrench ? 'Sélectionnez une raison…' : 'Select a reason…'} />
                </SelectTrigger>
                <SelectContent>
                  {REASONS.map(r => (
                    <SelectItem key={r.value} value={r.value} data-testid={`dispute-reason-${r.value}`}>
                      {isFrench ? r.fr : r.en}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">
                {isFrench ? 'Détails (optionnel)' : 'Details (optional)'}
              </label>
              <Textarea
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={4}
                maxLength={2000}
                placeholder={isFrench ? 'Décrivez le problème…' : 'Describe the issue…'}
                data-testid="dispute-details-textarea"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {isFrench ? 'Annuler' : 'Cancel'}
            </Button>
            <Button onClick={submit} disabled={submitting} className="bg-red-600 hover:bg-red-700"
              data-testid="dispute-submit-btn">
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {isFrench ? 'Soumettre le litige' : 'Submit Dispute'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default FileDisputeButton;
