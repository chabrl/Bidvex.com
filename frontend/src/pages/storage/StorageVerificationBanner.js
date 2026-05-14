/**
 * StorageVerificationBanner — iter213
 * ────────────────────────────────────────────────────────────────
 * 3-step progress banner shown above the Storage Dashboard for
 * facilities that haven't been verified yet. Hidden once the
 * facility is fully verified.
 *
 * Steps:
 *   1. Document Uploaded         (status: pending_upload | uploaded)
 *   2. Admin Reviewing            (status: reviewing)
 *   3. Verified — Ready to List!  (status: verified)
 *
 * Bilingual EN+FR per Bill 96. Designed as a thin info banner that
 * doesn't crowd the dashboard once the facility has anything else
 * to show.
 */
import React from 'react';
import { CheckCircle2, Clock, FileUp, ShieldCheck, XCircle, Loader2 } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';

const Step = ({ index, label_en, label_fr, status, isFr }) => {
  // status: 'complete' | 'active' | 'pending' | 'rejected'
  const baseRing = 'h-9 w-9 rounded-full flex items-center justify-center flex-shrink-0 ring-2';
  const styles = {
    complete: {
      ring: 'bg-emerald-500 ring-emerald-200 dark:ring-emerald-900',
      icon: <CheckCircle2 className="h-5 w-5 text-white" />,
      label: 'text-emerald-700 dark:text-emerald-300',
    },
    active: {
      ring: 'bg-amber-500 ring-amber-200 dark:ring-amber-900 animate-pulse',
      icon: <Loader2 className="h-5 w-5 text-white animate-spin" />,
      label: 'text-amber-700 dark:text-amber-300 font-semibold',
    },
    pending: {
      ring: 'bg-slate-200 dark:bg-slate-700 ring-slate-100 dark:ring-slate-800',
      icon: <span className="text-xs font-bold text-slate-600 dark:text-slate-300">{index}</span>,
      label: 'text-slate-500 dark:text-slate-400',
    },
    rejected: {
      ring: 'bg-rose-500 ring-rose-200 dark:ring-rose-900',
      icon: <XCircle className="h-5 w-5 text-white" />,
      label: 'text-rose-700 dark:text-rose-300 font-semibold',
    },
  };
  const s = styles[status] || styles.pending;
  return (
    <div className="flex items-center gap-2 min-w-0 flex-1" data-testid={`verification-step-${index}`}>
      <div className={`${baseRing} ${s.ring}`}>{s.icon}</div>
      <div className="min-w-0">
        <div className={`text-sm ${s.label}`}>{isFr ? label_fr : label_en}</div>
      </div>
    </div>
  );
};

const Connector = ({ active }) => (
  <div
    className={`h-px flex-1 mx-1 sm:mx-2 ${active ? 'bg-emerald-400' : 'bg-slate-200 dark:bg-slate-700'}`}
    aria-hidden="true"
  />
);

/**
 * @param {object} props
 * @param {object} props.facility - the facility doc; expects keys
 *   `company_registration_document_url`, `company_registration_verified`,
 *   `company_registration_rejection_reason`.
 * @param {boolean} props.isFr
 */
const StorageVerificationBanner = ({ facility, isFr }) => {
  if (!facility) return null;
  const hasDoc = !!facility.company_registration_document_url;
  const isVerified = facility.company_registration_verified === true;
  const isRejected = !isVerified && !!facility.company_registration_rejection_reason;

  // Hide once verified — banner is only for the unverified path.
  if (isVerified && !isRejected) return null;

  // Compute each step's status
  const step1 = hasDoc ? 'complete' : 'active';
  let step2, step3;
  if (isRejected) {
    step2 = 'rejected';
    step3 = 'pending';
  } else if (!hasDoc) {
    step2 = 'pending';
    step3 = 'pending';
  } else {
    step2 = 'active'; // doc uploaded → admin reviewing
    step3 = 'pending';
  }

  return (
    <Card
      className="mb-6 p-4 sm:p-5 border-l-4 border-l-amber-500 bg-amber-50/50 dark:bg-amber-950/20"
      data-testid="verification-progress-banner"
    >
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-amber-600 flex-shrink-0" />
          <h2 className="font-bold text-sm sm:text-base">
            {isFr ? 'Progrès de la vérification' : 'Verification progress'}
          </h2>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-amber-700 dark:text-amber-300 font-semibold">
          {isRejected
            ? (isFr ? 'Document rejeté' : 'Document rejected')
            : isVerified
              ? (isFr ? 'Vérifié' : 'Verified')
              : (isFr ? 'En cours' : 'In progress')}
        </span>
      </div>

      <div className="flex items-center" data-testid="verification-steps-row">
        <Step
          index={1}
          status={step1}
          label_en={hasDoc ? 'Document uploaded' : 'Awaiting document'}
          label_fr={hasDoc ? 'Document téléversé' : 'En attente de document'}
          isFr={isFr}
        />
        <Connector active={step1 === 'complete'} />
        <Step
          index={2}
          status={step2}
          label_en={isRejected ? 'Document rejected — please resubmit' : 'Admin reviewing'}
          label_fr={isRejected ? 'Document rejeté — à soumettre à nouveau' : 'En cours d\'examen'}
          isFr={isFr}
        />
        <Connector active={false} />
        <Step
          index={3}
          status={step3}
          label_en="Verified — ready to list!"
          label_fr="Vérifié — prêt à lister!"
          isFr={isFr}
        />
      </div>

      {isRejected && (
        <div
          className="mt-4 rounded-md bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 p-3"
          data-testid="verification-rejection-reason"
        >
          <p className="text-xs uppercase tracking-wider text-rose-700 dark:text-rose-300 font-semibold mb-1">
            {isFr ? 'Motif du rejet' : 'Rejection reason'}
          </p>
          <p className="text-sm text-rose-800 dark:text-rose-200 whitespace-pre-line">
            {facility.company_registration_rejection_reason}
          </p>
          <Link to="/storage-auctions/register-facility?resubmit=1">
            <Button
              size="sm"
              className="mt-3 bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="resubmit-registration-btn"
            >
              <FileUp className="h-3 w-3 mr-1" />
              {isFr ? 'Soumettre un nouveau document' : 'Resubmit document'}
            </Button>
          </Link>
        </div>
      )}

      {!isRejected && !isVerified && (
        <p className="mt-3 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
          <Clock className="h-3 w-3" />
          {hasDoc
            ? (isFr
                ? 'Notre équipe examine votre document — vous serez avisé dans 1 à 2 jours ouvrables.'
                : 'Our team is reviewing your document — you\'ll be notified within 1–2 business days.')
            : (isFr
                ? 'Téléversez votre document d\'enregistrement d\'entreprise pour commencer la vérification.'
                : 'Upload your business-registration document to start verification.')}
        </p>
      )}
    </Card>
  );
};

export default StorageVerificationBanner;
