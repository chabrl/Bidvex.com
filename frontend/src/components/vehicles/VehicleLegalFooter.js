/**
 * iter201 — Phase 2 — Vehicle Auctions Bilingual Legal Footer.
 *
 * Drop into any vehicle-section page (homepage vehicle promo, listings index,
 * VehicleDetailPage, CreateVehicleListingPage, etc.) to satisfy the CEO's
 * Part 4 disclaimer requirement.
 *
 * Renders the EN or FR text based on the active i18n language, with the other
 * language tucked behind an expandable "Show other language" toggle so the
 * page stays clean.
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';

const EN_TEXT = `BidVex vehicle auctions operate in compliance with applicable federal and provincial motor vehicle dealer legislation across Canada. Seller dealer licences are verified by BidVex compliance staff. BidVex does not guarantee vehicle condition, history, or title. Buyers are responsible for conducting due diligence including lien searches and vehicle history checks prior to bidding. Vehicle purchases are final and binding upon auction close. Provincial transfer taxes and registration fees are the buyer's responsibility. BidVex Inc. acts as the auction platform only and is not a party to the sale transaction.`;

const FR_TEXT = `Les enchères de véhicules BidVex sont conformes aux lois fédérales et provinciales applicables sur les concessionnaires de véhicules automobiles au Canada. Les licences de concessionnaire des vendeurs sont vérifiées par l'équipe de conformité de BidVex. BidVex ne garantit pas l'état, l'historique ou le titre des véhicules. Les acheteurs sont responsables de la diligence raisonnable, notamment les recherches de privilèges et les vérifications d'historique avant d'enchérir. Les achats sont définitifs à la clôture de l'enchère. Les taxes de transfert provinciales et les frais d'immatriculation sont à la charge de l'acheteur. BidVex Inc. agit uniquement à titre de plateforme d'enchères et n'est pas partie à la transaction.`;

const VehicleLegalFooter = ({ className = '' }) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [showOther, setShowOther] = useState(false);

  const primary = isFr ? FR_TEXT : EN_TEXT;
  const secondary = isFr ? EN_TEXT : FR_TEXT;
  const otherLabel = isFr ? 'View English version' : 'Voir la version française';
  const hideLabel = isFr ? 'Hide English' : 'Masquer le français';

  return (
    <footer
      className={`mt-12 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 ${className}`}
      data-testid="vehicle-legal-footer"
    >
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-start gap-3 max-w-4xl">
          <ShieldCheck className="h-5 w-5 text-slate-500 dark:text-slate-400 flex-shrink-0 mt-0.5" aria-hidden />
          <div className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            <p data-testid="vehicle-legal-footer-primary">{primary}</p>
            <button
              type="button"
              onClick={() => setShowOther((s) => !s)}
              className="mt-2 inline-flex items-center gap-1 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 underline-offset-2 hover:underline"
              data-testid="vehicle-legal-footer-toggle"
            >
              {showOther ? hideLabel : otherLabel}
              {showOther ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
            {showOther && (
              <p className="mt-2 italic text-slate-500 dark:text-slate-400" data-testid="vehicle-legal-footer-secondary">
                {secondary}
              </p>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
};

export default VehicleLegalFooter;
