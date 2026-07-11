import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';

/**
 * Contextual footer banner — rendered ONLY on /storage-auctions/* routes.
 * Replaces the global Storage Auctions footer section that was removed in iter170.
 *
 * Phase 6.2 hotfix — Approved facilities + global admins see the dashboard CTA
 * instead of the "Register Your Facility" CTA.
 */
const STORAGE_FOOTER_CONTENT = {
  en: {
    title: 'Do you manage a storage facility?',
    sub: 'Register and start selling abandoned units today.',
    cta: 'Register My Facility →',
    nav_browse: 'Browse Auctions',
    nav_how: 'How It Works',
    nav_terms: 'Terms & Conditions',
    nav_for: 'For Facilities',
    approved_title: 'Welcome back, facility manager',
    approved_sub: 'Jump straight back into your dashboard or list a new unit.',
    approved_cta_dashboard: '📊 Facility Dashboard',
    approved_cta_create: '➕ Create Unit Auction',
  },
  fr: {
    title: "Vous gérez une facilité d'entreposage ?",
    sub: 'Inscrivez-vous et commencez à vendre des unités abandonnées aujourd\'hui.',
    cta: 'Inscrire ma facilité →',
    nav_browse: 'Parcourir les enchères',
    nav_how: 'Comment ça marche',
    nav_terms: 'Conditions',
    nav_for: 'Pour facilités',
    approved_title: 'Bon retour, gestionnaire',
    approved_sub: 'Retournez directement à votre tableau de bord ou créez une nouvelle enchère.',
    approved_cta_dashboard: '📊 Tableau de bord',
    approved_cta_create: '➕ Créer une enchère',
  },
};

const StorageFooterBanner = () => {
  const { i18n } = useTranslation();
  const lang = (i18n.language || '').startsWith('fr') ? 'fr' : 'en';
  const t = STORAGE_FOOTER_CONTENT[lang];
  const { user } = useAuth();
  const isFacilityOrAdmin = !!user && (
    user.storage_facility_approved === true
    || user.account_type === 'storage_facility'
    || user.is_storage_facility === true
    || user.role === 'admin'
    || user.role === 'super_admin'
    || user.is_admin === true
  );

  return (
    <div
      className="storage-footer-banner border-t border-slate-200 dark:border-slate-800 bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-900 dark:to-slate-950 py-12 px-4"
      data-testid="storage-footer-banner"
    >
      <div className="max-w-4xl mx-auto text-center">
        <h3 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-2">
          {isFacilityOrAdmin ? t.approved_title : t.title}
        </h3>
        <p className="text-base text-slate-600 dark:text-slate-300 mb-6">
          {isFacilityOrAdmin ? t.approved_sub : t.sub}
        </p>
        {isFacilityOrAdmin ? (
          <div className="flex flex-wrap gap-3 justify-center" data-testid="storage-footer-facility-ctas">
            <Link
              to="/facility/dashboard"
              className="inline-flex items-center gap-2 bg-[#3FB4CB] hover:bg-[#2FA0BA] text-[#0B2545] font-bold rounded-full px-7 py-3 transition-all hover:-translate-y-0.5 hover:shadow-lg"
              data-testid="storage-footer-dashboard-cta"
            >
              {t.approved_cta_dashboard}
            </Link>
            <Link
              to="/create-listing?type=storage_locker"
              className="inline-flex items-center gap-2 border-2 border-[#3FB4CB] text-[#0B2545] dark:text-[#3FB4CB] font-bold rounded-full px-7 py-3 transition-all hover:-translate-y-0.5 hover:bg-[#3FB4CB]/10"
              data-testid="storage-footer-create-cta"
            >
              {t.approved_cta_create}
            </Link>
          </div>
        ) : (
          <Link
            to="/storage-auctions/register-facility"
            className="inline-flex items-center gap-2 bg-[#3FB4CB] hover:bg-[#2FA0BA] text-[#0B2545] font-bold rounded-full px-7 py-3 transition-all hover:-translate-y-0.5 hover:shadow-lg"
            data-testid="storage-footer-register-cta"
          >
            {t.cta}
          </Link>
        )}

        <div className="mt-8 flex flex-wrap justify-center items-center gap-x-5 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
          <Link to="/storage-auctions/browse" className="hover:text-slate-900 dark:hover:text-white transition-colors">
            {t.nav_browse}
          </Link>
          <span>·</span>
          <Link to="/storage-auctions/how-it-works" className="hover:text-slate-900 dark:hover:text-white transition-colors">
            {t.nav_how}
          </Link>
          <span>·</span>
          <Link to="/storage-auctions/terms" className="hover:text-slate-900 dark:hover:text-white transition-colors">
            {t.nav_terms}
          </Link>
          <span>·</span>
          <Link to="/storage-auctions/for-facilities" className="hover:text-slate-900 dark:hover:text-white transition-colors">
            {t.nav_for}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default StorageFooterBanner;
