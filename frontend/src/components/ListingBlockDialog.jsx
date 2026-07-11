import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { ShieldAlert, ExternalLink, Search } from 'lucide-react';

/**
 * iter342 — Context-aware listing block dialog.
 * Renders ONLY the message matching the typed `block_reason` enum returned
 * by the backend. Non-vehicle sellers never see dealer-licensing text.
 * Every reason includes a "Request Manual Review" CTA (iter312 flow).
 */
const FALLBACK_MESSAGES = {
  vehicle_dealer_required: {
    title_en: 'Vehicle listing not allowed',
    title_fr: 'Annonce de véhicule refusée',
    en: 'Vehicle listings on BidVex require a verified provincial dealer licence (OMVIC in ON, AMVIC in AB, VSA in BC, SAAQ in QC). If you are a licensed dealer, contact vehicles@bidvex.com to verify your account. If you are selling a personal vehicle, please use the Marketplace section instead.',
    fr: "Les annonces de véhicules sur BidVex nécessitent une licence de concessionnaire provincial vérifiée (OMVIC en ON, AMVIC en AB, VSA en C.-B., SAAQ au QC). Si vous êtes un concessionnaire licencié, contactez vehicles@bidvex.com pour vérifier votre compte. Si vous vendez un véhicule personnel, utilisez plutôt la section Marché.",
  },
  prohibited_item: {
    title_en: 'Listing not permitted',
    title_fr: 'Annonce non autorisée',
    en: 'This listing contains content that is not permitted on BidVex. Please review our Prohibited Items policy at bidvex.com/legal/prohibited. If you believe this is an error, contact service@bidvex.com.',
    fr: "Cette annonce contient du contenu non autorisé sur BidVex. Veuillez consulter notre politique d'articles interdits à bidvex.com/legal/prohibited. Si vous pensez qu'il s'agit d'une erreur, contactez service@bidvex.com.",
  },
  ai_review_required: {
    title_en: 'Manual review required',
    title_fr: 'Examen manuel requis',
    en: 'Your listing has been flagged for manual review by our team. It will appear in your Drafts while under review. We typically respond within 24 hours. You will be notified by email when it is approved or if changes are needed.',
    fr: "Votre annonce a été signalée pour examen manuel par notre équipe. Elle apparaîtra dans vos brouillons pendant l'examen. Nous répondons généralement dans les 24 heures. Vous serez informé par courriel lorsqu'elle sera approuvée ou si des modifications sont nécessaires.",
  },
  false_positive_suspected: {
    title_en: 'Listing flagged automatically',
    title_fr: 'Annonce signalée automatiquement',
    en: "Your listing was flagged automatically. If you believe this is a mistake, click 'Request Manual Review' and our team will review it within 24 hours. Your listing will be saved as a draft in the meantime.",
    fr: "Votre annonce a été signalée automatiquement. Si vous pensez qu'il s'agit d'une erreur, cliquez sur 'Demander un examen manuel' et notre équipe l'examinera dans les 24 heures. Votre annonce sera sauvegardée comme brouillon entre-temps.",
  },
};

export const ListingBlockDialog = ({
  open,
  onOpenChange,
  reason = 'vehicle_dealer_required',
  signals = [],
  messages = null,          // { en, fr } override from backend detail
  reviewRequested = false,
  reviewSubmitting = false,
  onRequestReview,
}) => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const copy = FALLBACK_MESSAGES[reason] || FALLBACK_MESSAGES.false_positive_suspected;
  const isVehicle = reason === 'vehicle_dealer_required';
  const body = fr
    ? (messages?.fr || copy.fr)
    : (messages?.en || copy.en);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="vehicle-compliance-dialog"
        className="sm:max-w-2xl border-rose-200"
      >
        <DialogHeader>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 mb-2">
            <ShieldAlert className="h-6 w-6 text-rose-600" />
          </div>
          <DialogTitle
            data-testid="vehicle-compliance-dialog-title"
            className="text-center text-xl font-semibold text-slate-900"
          >
            {fr ? copy.title_fr : copy.title_en}
          </DialogTitle>
          <DialogDescription
            data-testid="vehicle-compliance-dialog-body"
            className="text-center text-sm leading-relaxed text-slate-600 pt-2"
          >
            {body}
          </DialogDescription>
        </DialogHeader>

        {signals.length > 0 && (
          <div
            data-testid="vehicle-compliance-signals"
            className="mt-2 rounded-md bg-slate-50 border border-slate-200 px-3 py-2"
          >
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">
              {fr ? 'Signaux détectés' : 'Detected signals'}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {signals.map((sig, i) => (
                <span
                  key={i}
                  className="font-mono text-[11px] bg-white border border-slate-200 rounded px-2 py-0.5 text-slate-700"
                >
                  {sig}
                </span>
              ))}
            </div>
          </div>
        )}

        <DialogFooter
          data-testid="vehicle-compliance-footer"
          className="mt-4 flex flex-col sm:flex-row sm:flex-wrap sm:items-stretch sm:justify-center gap-3 py-2"
        >
          {reviewRequested ? (
            <div
              data-testid="vehicle-compliance-review-submitted"
              className="w-full rounded-lg border border-slate-200 bg-slate-50 text-center"
              style={{ padding: '24px' }}
            >
              <p className="text-base font-semibold text-emerald-900 mb-2">
                ✅ {fr ? 'Demande de révision soumise' : 'Review Request Submitted'}
              </p>
              <p className="text-sm text-slate-700 leading-relaxed max-w-md mx-auto">
                {fr
                  ? "Notre équipe vérifiera manuellement cette annonce dans les 24 heures. Vous recevrez un courriel et une notification système dès l'approbation. Votre annonce est sauvegardée comme brouillon entre-temps."
                  : 'Our team will manually review this listing within 24 hours. You will receive an email and a system notification once approved. Your listing is saved as a draft in the meantime.'}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => onOpenChange(false)}
                data-testid="vehicle-compliance-review-close-btn"
              >
                {fr ? 'Fermer' : 'Close'}
              </Button>
            </div>
          ) : (
            <>
              {isVehicle && (
                <>
                  <Button
                    variant="outline"
                    data-testid="vehicle-compliance-secondary-btn"
                    onClick={() => {
                      onOpenChange(false);
                      navigate('/vehicle-auctions');
                    }}
                    className="flex-1 sm:flex-none sm:min-w-[180px] whitespace-nowrap h-11"
                  >
                    <ExternalLink className="mr-2 h-4 w-4 flex-shrink-0" />
                    <span className="truncate">
                      {fr ? 'Enchères de véhicules' : 'Go to Vehicle Auctions'}
                    </span>
                  </Button>
                  <Button
                    data-testid="vehicle-compliance-primary-btn"
                    onClick={() => {
                      onOpenChange(false);
                      navigate('/vehicle-auctions/dealer-license');
                    }}
                    className="flex-1 sm:flex-none sm:min-w-[180px] whitespace-nowrap h-11 bg-rose-600 hover:bg-rose-700 text-white"
                  >
                    <span className="truncate">
                      {fr ? 'Vérifier ma licence' : 'Verify dealer licence'}
                    </span>
                  </Button>
                </>
              )}
              <Button
                variant="outline"
                data-testid="vehicle-compliance-manual-review-btn"
                onClick={onRequestReview}
                disabled={reviewSubmitting}
                className="flex-1 sm:flex-none sm:min-w-[180px] whitespace-nowrap h-11 border-amber-400 bg-amber-50 text-amber-900 hover:bg-amber-100 hover:border-amber-500 disabled:opacity-60"
                style={{ paddingLeft: 20, paddingRight: 20 }}
              >
                <Search className="mr-2 h-4 w-4 flex-shrink-0" />
                <span className="truncate">
                  {reviewSubmitting
                    ? (fr ? 'Envoi…' : 'Sending…')
                    : (fr ? 'Demander un examen manuel' : 'Request Manual Review')}
                </span>
              </Button>
              {!isVehicle && (
                <Button
                  variant="outline"
                  data-testid="vehicle-compliance-close-btn"
                  onClick={() => onOpenChange(false)}
                  className="flex-1 sm:flex-none sm:min-w-[120px] whitespace-nowrap h-11"
                >
                  {fr ? 'Fermer' : 'Close'}
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ListingBlockDialog;
