/**
 * iter427 — DealerVerificationGate
 *
 * Renders an inline gate panel that blocks vehicle-listing surfaces
 * (single create, multi-lot create, publish flows) for users whose
 * dealer profile is not `approved`. Shows a clear bilingual message
 * plus a primary "Verify Dealer" CTA — replacing the previous silent
 * `toast + navigate('/vehicle-auctions')` pattern.
 *
 * Props:
 *   sellerProfile    — the `/api/vehicle-sellers/me` response (may be null
 *                      when the user has never registered)
 *   noProfile        — when `true`, treats the user as "never registered"
 *                      (typically because a 404 came back from the API)
 *   suspended        — when `true`, shows the "suspended by admin" branch
 *                      (comes from the user object, not the seller doc)
 *   className        — optional wrapper class overrides
 *   surfaceLabel     — "single vehicle listing", "multi-lot auction", etc.
 *
 * Reuses existing Card / Button / Badge primitives + i18n.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  ShieldAlert, ShieldCheck, ShieldOff, Clock, XCircle, IdCard, ArrowRight,
} from 'lucide-react';

const KIND_CONFIG = {
  approved:      { icon: ShieldCheck, tone: 'emerald' },
  pending:       { icon: Clock,       tone: 'amber' },
  under_review:  { icon: Clock,       tone: 'blue' },
  rejected:      { icon: XCircle,     tone: 'rose' },
  suspended:     { icon: ShieldOff,   tone: 'orange' },
  not_registered:{ icon: IdCard,      tone: 'slate' },
};

const TONE_CLASSES = {
  emerald: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  amber:   'bg-amber-50 border-amber-200 text-amber-800',
  blue:    'bg-blue-50 border-blue-200 text-blue-800',
  rose:    'bg-rose-50 border-rose-200 text-rose-800',
  orange:  'bg-orange-50 border-orange-200 text-orange-800',
  slate:   'bg-slate-50 border-slate-200 text-slate-800',
};

const DealerVerificationGate = ({
  sellerProfile,
  noProfile = false,
  suspended = false,
  surfaceLabel,
  className = '',
}) => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');

  // Resolve the state key.
  let kind = 'not_registered';
  if (suspended) kind = 'suspended';
  else if (noProfile || !sellerProfile) kind = 'not_registered';
  else if (sellerProfile.verification_status === 'approved') kind = 'approved';
  else if (sellerProfile.verification_status === 'rejected') kind = 'rejected';
  else if (sellerProfile.verification_status === 'under_review') kind = 'under_review';
  else kind = 'pending';

  // If approved and not suspended, don't render the gate — parent should
  // render the form instead. This is a safety no-op guard.
  if (kind === 'approved') return null;

  const config = KIND_CONFIG[kind];
  const Icon = config.icon;

  // Copy per state
  const heading = {
    pending:        [isFr ? 'Vérification du concessionnaire en attente' : 'Dealer verification pending',
                     isFr ? 'Vérification en attente' : 'Verification pending'][0],
    under_review:   isFr ? 'Vérification en cours d’examen' : 'Verification under review',
    rejected:       isFr ? 'Vérification refusée' : 'Verification rejected',
    suspended:      isFr ? 'Compte concessionnaire suspendu' : 'Dealer account suspended',
    not_registered: isFr ? 'Vérification du concessionnaire requise' : 'Dealer verification required',
  }[kind];

  const body = {
    pending: isFr
      ? 'Votre dossier concessionnaire a été soumis et attend l’examen par notre équipe. Une fois approuvé, vous pourrez créer des annonces de véhicules.'
      : 'Your dealer application has been submitted and is waiting for review by our team. Once approved you’ll be able to create vehicle listings.',
    under_review: isFr
      ? 'Un administrateur examine actuellement votre licence et vos documents. Vous recevrez une notification dès que la décision sera prise.'
      : 'An administrator is reviewing your licence and documents right now. You’ll be notified as soon as a decision is made.',
    rejected: isFr
      ? 'Votre demande a été refusée. Corrigez les points signalés ci-dessous puis soumettez à nouveau vos documents pour être vérifié.'
      : 'Your application was rejected. Address the issues flagged below, then resubmit your documents to get verified.',
    suspended: isFr
      ? 'Votre compte concessionnaire est actuellement suspendu par un administrateur. Vous ne pouvez pas créer, publier ou importer d’annonces tant que la suspension n’est pas levée.'
      : 'Your dealer account is currently suspended by an administrator. You cannot create, publish, or import listings until the suspension is lifted.',
    not_registered: isFr
      ? `Pour créer un(e) ${surfaceLabel || 'annonce de véhicule'}, vous devez d’abord vous enregistrer comme concessionnaire et faire vérifier votre licence provinciale.`
      : `To create a ${surfaceLabel || 'vehicle listing'}, you must first register as a dealer and have your provincial licence verified.`,
  }[kind];

  const rejectionReason = sellerProfile?.rejection_reason || sellerProfile?.notes;
  const suspensionReason = sellerProfile?.vehicle_dealer_suspended_reason;

  const primaryCta = {
    pending:        { label: isFr ? 'Voir ma demande'      : 'View my application', to: '/vehicle-auctions/seller/register' },
    under_review:   { label: isFr ? 'Voir ma demande'      : 'View my application', to: '/vehicle-auctions/seller/register' },
    rejected:       { label: isFr ? 'Renouveler la vérification' : 'Resubmit for verification', to: '/vehicle-auctions/seller/register' },
    suspended:      { label: isFr ? 'Contacter le support' : 'Contact Support',     to: '/contact' },
    not_registered: { label: isFr ? 'Vérifier concessionnaire' : 'Verify Dealer',   to: '/vehicle-auctions/seller/register' },
  }[kind];

  return (
    <div className={`min-h-[60vh] flex items-center justify-center p-4 ${className}`}
         data-testid="dealer-verification-gate">
      <Card className={`max-w-2xl w-full border ${TONE_CLASSES[config.tone]}`}>
        <CardContent className="p-6 sm:p-8 space-y-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5">
              <Icon className="h-7 w-7" data-testid={`gate-icon-${kind}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white">
                  {heading}
                </h2>
                <Badge className={TONE_CLASSES[config.tone]} data-testid={`gate-status-${kind}`}>
                  {kind.replace(/_/g, ' ').toUpperCase()}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {body}
              </p>

              {rejectionReason && kind === 'rejected' && (
                <div className="mt-3 p-3 rounded bg-rose-100/70 border border-rose-200 text-sm text-rose-900"
                     data-testid="gate-rejection-reason">
                  <strong>{isFr ? 'Motif du refus : ' : 'Rejection reason: '}</strong>
                  {rejectionReason}
                </div>
              )}
              {suspensionReason && kind === 'suspended' && (
                <div className="mt-3 p-3 rounded bg-orange-100/70 border border-orange-200 text-sm text-orange-900"
                     data-testid="gate-suspension-reason">
                  <strong>{isFr ? 'Motif de la suspension : ' : 'Suspension reason: '}</strong>
                  {suspensionReason}
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2">
            <Button
              onClick={() => navigate(primaryCta.to)}
              className="flex-1 sm:flex-initial bg-slate-900 hover:bg-slate-800 text-white gap-2"
              data-testid="gate-primary-cta"
            >
              <ShieldAlert className="h-4 w-4" />
              {primaryCta.label}
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button
              onClick={() => navigate('/vehicle-auctions')}
              variant="outline"
              className="flex-1 sm:flex-initial"
              data-testid="gate-back-btn"
            >
              {isFr ? 'Retour aux enchères' : 'Back to auctions'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default DealerVerificationGate;
