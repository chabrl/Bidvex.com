/**
 * iter209 Step 2 — Reusable resubmission flow component.
 *
 * Renders the rejected-state banner + actionable "what to do next" panel +
 * a resubmit dialog (form) that:
 *   - Pre-fills text fields the applicant gave on the previous attempt
 *   - Always clears file inputs (security)
 *   - Shows previous rejection reason at the top of the form
 *   - Hides the resubmit CTA once `resubmissionCount >= 3` and shows the
 *     "Maximum resubmission attempts reached" support message instead
 *
 * Supports BOTH flavors:
 *   - flavor="partner"  → POST /api/partner/resubmit (multipart: company_name, neq_number, neq_document, certification_documents[])
 *   - flavor="dealer"   → POST /api/vehicles/dealer/resubmit (JSON: seller_type, business_name, license_number, license_province, ...)
 *
 * On success calls onResubmitted() so the parent page can re-fetch status
 * and switch its banner to "pending review" without a full reload.
 */
import React, { useState, useMemo } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { FileText, RotateCcw, AlertTriangle, Loader2, ShieldAlert } from 'lucide-react';
import API_BASE from '../config';

const MAX_RESUBMISSIONS = 3;

export const ResubmitApplicationPanel = ({
  flavor,                  // "partner" | "dealer"
  rejectionReason,
  resubmissionCount = 0,
  rejectionHistory = [],
  prefillData = {},        // { companyName, neqNumber, businessName, licenseNumber, licenseProvince, sellerType }
  onResubmitted,           // callback invoked after a successful POST
  token,
}) => {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const canResubmit = resubmissionCount < MAX_RESUBMISSIONS;

  // Local form state (text pre-fill, files always clear)
  const [companyName, setCompanyName] = useState(prefillData.companyName || '');
  const [neqNumber, setNeqNumber] = useState(prefillData.neqNumber || '');
  const [businessName, setBusinessName] = useState(prefillData.businessName || '');
  const [licenseNumber, setLicenseNumber] = useState(prefillData.licenseNumber || '');
  const [licenseProvince, setLicenseProvince] = useState(prefillData.licenseProvince || '');
  const [sellerType] = useState(prefillData.sellerType || 'dealer');
  const [neqFile, setNeqFile] = useState(null);
  const [certFiles, setCertFiles] = useState([]);

  const headlineEn = useMemo(
    () => (flavor === 'partner' ? 'Resubmitting Your Partner Application' : 'Resubmitting Your Dealer Application'),
    [flavor]
  );
  const headlineFr = useMemo(
    () => (flavor === 'partner' ? 'Nouvelle soumission de votre demande de partenaire' : 'Nouvelle soumission de votre demande de marchand'),
    [flavor]
  );

  const submit = async () => {
    setSubmitting(true);
    try {
      if (flavor === 'partner') {
        if (!neqFile) {
          toast.error(isFr ? "Document d'enregistrement d'entreprise requis" : 'Business registration document required');
          setSubmitting(false);
          return;
        }
        if (certFiles.length === 0) {
          toast.error(isFr ? 'Au moins une certification requise' : 'At least one certification required');
          setSubmitting(false);
          return;
        }
        const fd = new FormData();
        fd.append('company_name', companyName);
        fd.append('neq_number', neqNumber);
        fd.append('neq_document', neqFile);
        certFiles.forEach(f => fd.append('certification_documents', f));
        const r = await axios.post(`${API_BASE}/partner/resubmit`, fd, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
        });
        toast.success(isFr ? r.data.message_fr : r.data.message_en);
      } else {
        // dealer
        const body = {
          seller_type: sellerType,
          business_name: businessName,
          license_number: licenseNumber,
          license_province: licenseProvince,
        };
        const r = await axios.post(`${API_BASE}/vehicles/dealer/resubmit`, body, {
          headers: { Authorization: `Bearer ${token}` },
        });
        toast.success(isFr ? r.data.message_fr : r.data.message_en);
      }
      setOpen(false);
      if (typeof onResubmitted === 'function') onResubmitted();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.error === 'max_resubmissions_reached') {
        toast.error(isFr ? detail.message_fr : detail.message_en);
      } else if (detail && typeof detail === 'object' && detail.error === 'not_in_rejected_state') {
        toast.error(isFr ? detail.message_fr : detail.message_en);
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error(isFr ? 'Échec de la nouvelle soumission' : 'Resubmission failed');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-3" data-testid={`resubmit-panel-${flavor}`}>
      {/* What to do next */}
      <div
        className="rounded-xl border border-blue-200 bg-blue-50 dark:border-blue-700/40 dark:bg-blue-950/40 p-4"
        data-testid={`resubmit-next-steps-${flavor}`}
      >
        <p className="text-sm font-semibold text-blue-900 dark:text-blue-200 flex items-center gap-2">
          <FileText className="w-4 h-4" />
          {isFr ? 'À faire ensuite :' : 'What to do next:'}
        </p>
        <p className="text-sm text-blue-800 dark:text-blue-300 mt-1.5 leading-relaxed">
          {isFr
            ? "Consultez la raison ci-dessus, mettez à jour vos documents ou informations, et soumettez à nouveau votre demande. Notre équipe l'examinera dans les 24 à 48 heures."
            : 'Review the reason above, update your documents or information, and resubmit your application. Our team will review it within 24–48 hours.'}
        </p>

        {canResubmit ? (
          <Button
            onClick={() => setOpen(true)}
            data-testid={`resubmit-cta-${flavor}`}
            className="mt-3 w-full bg-blue-600 hover:bg-blue-700 text-white rounded-[10px] h-11 text-sm font-semibold"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            {isFr ? 'Soumettre à nouveau' : 'Resubmit Application'}
          </Button>
        ) : (
          <div
            className="mt-3 rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700/40 dark:bg-amber-950/40 p-3 text-sm text-amber-900 dark:text-amber-200"
            data-testid={`resubmit-max-reached-${flavor}`}
          >
            <p className="flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>
                {isFr
                  ? 'Nombre maximum de tentatives atteint. Contactez '
                  : 'Maximum resubmission attempts reached. Please contact '}
                <a href="mailto:partners@bidvex.ca" className="underline font-semibold">partners@bidvex.ca</a>
                {isFr ? " pour obtenir de l'aide." : ' for assistance.'}
              </span>
            </p>
          </div>
        )}

        {resubmissionCount > 0 && canResubmit && (
          <p className="text-[11px] text-blue-700 dark:text-blue-400 mt-2">
            {isFr
              ? `Tentative ${resubmissionCount + 1} sur ${MAX_RESUBMISSIONS}`
              : `Attempt ${resubmissionCount + 1} of ${MAX_RESUBMISSIONS}`}
          </p>
        )}

        <p className="text-[11px] text-slate-500 dark:text-slate-500 mt-2">
          {isFr ? 'Questions ? Contactez-nous à ' : 'Questions? Contact us at '}
          <a href="mailto:partners@bidvex.ca" className="underline">partners@bidvex.ca</a>
        </p>
      </div>

      {/* Resubmission Dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          data-testid={`resubmit-dialog-${flavor}`}
          className="sm:max-w-lg max-h-[85vh] overflow-y-auto"
        >
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-slate-900 dark:text-white">
              {isFr ? headlineFr : headlineEn}
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500 dark:text-slate-400">
              {isFr
                ? `Raison du refus précédent : ${rejectionReason || '—'}`
                : `Previous rejection reason: ${rejectionReason || '—'}`}
            </DialogDescription>
          </DialogHeader>

          {rejectionHistory.length > 0 && (
            <div className="rounded-md bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700/40 px-3 py-2 text-[11px] text-slate-600 dark:text-slate-400">
              <p className="font-semibold mb-1 text-slate-700 dark:text-slate-300">
                {isFr ? 'Historique des refus' : 'Rejection history'}
              </p>
              <ul className="space-y-1 list-disc list-inside">
                {rejectionHistory.map((h, i) => (
                  <li key={i}>{h.reason || '—'}</li>
                ))}
              </ul>
            </div>
          )}

          {flavor === 'partner' ? (
            <div className="space-y-3 mt-2">
              <div>
                <Label className="text-xs">{isFr ? 'Nom de la société' : 'Company name'}</Label>
                <Input
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                  data-testid="resubmit-partner-company"
                  className="h-9"
                />
              </div>
              <div>
                <Label className="text-xs">{isFr ? "Numéro d'enregistrement d'entreprise" : 'Business Registration #'}</Label>
                <Input
                  value={neqNumber}
                  onChange={e => setNeqNumber(e.target.value)}
                  data-testid="resubmit-partner-neq"
                  className="h-9"
                />
              </div>
              <div>
                <Label className="text-xs">{isFr ? "Document d'enregistrement (PDF)" : 'Business Registration Document (PDF)'}</Label>
                <Input
                  type="file"
                  accept="application/pdf,image/*"
                  onChange={e => setNeqFile(e.target.files?.[0] || null)}
                  data-testid="resubmit-partner-neq-file"
                  className="h-9"
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  {isFr ? 'Veuillez téléverser à nouveau le document pour des raisons de sécurité.' : 'Please re-upload the document for security reasons.'}
                </p>
              </div>
              <div>
                <Label className="text-xs">{isFr ? 'Certifications (1+)' : 'Certifications (1+)'}</Label>
                <Input
                  type="file"
                  accept="application/pdf,image/*"
                  multiple
                  onChange={e => setCertFiles(Array.from(e.target.files || []))}
                  data-testid="resubmit-partner-cert-files"
                  className="h-9"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-3 mt-2">
              <div>
                <Label className="text-xs">{isFr ? "Nom de l'entreprise" : 'Business name'}</Label>
                <Input
                  value={businessName}
                  onChange={e => setBusinessName(e.target.value)}
                  data-testid="resubmit-dealer-business-name"
                  className="h-9"
                />
              </div>
              <div>
                <Label className="text-xs">{isFr ? 'Numéro de licence' : 'License number'}</Label>
                <Input
                  value={licenseNumber}
                  onChange={e => setLicenseNumber(e.target.value)}
                  data-testid="resubmit-dealer-license"
                  className="h-9"
                />
              </div>
              <div>
                <Label className="text-xs">{isFr ? 'Province' : 'Province'}</Label>
                <Input
                  value={licenseProvince}
                  onChange={e => setLicenseProvince(e.target.value)}
                  data-testid="resubmit-dealer-province"
                  className="h-9"
                  placeholder="ON, QC, BC, AB..."
                />
              </div>
              <p className="text-[10px] text-slate-500">
                {isFr
                  ? 'Téléversez à nouveau vos documents (licence, etc.) depuis l’onglet Documents après la nouvelle soumission.'
                  : 'Re-upload your documents (license, etc.) from the Documents tab after resubmitting.'}
              </p>
            </div>
          )}

          <DialogFooter className="mt-3 flex-col sm:flex-row sm:justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={submitting}
              data-testid={`resubmit-cancel-${flavor}`}
            >
              {isFr ? 'Annuler' : 'Cancel'}
            </Button>
            <Button
              onClick={submit}
              disabled={submitting}
              data-testid={`resubmit-submit-${flavor}`}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {submitting ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isFr ? 'Envoi…' : 'Submitting…'}</>
              ) : (
                <>{isFr ? 'Soumettre la nouvelle demande' : 'Submit Resubmission'}</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ResubmitApplicationPanel;
