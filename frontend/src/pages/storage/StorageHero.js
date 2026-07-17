import React from 'react';

import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import './StorageHero.css';
import { LangLink } from '../../components/LangLink';

/**
 * StorageHero — iter193 single-language rendering.
 * Respects the global EN/FR toggle. The whole hero renders in the active language only.
 *
 * Phase 6.2 hotfix — When the visitor is already an approved storage facility
 * OR a global admin, the "Register Your Facility" CTA swaps for a direct
 * "Facility Dashboard" jump so the user never sees the registration teaser
 * after approval.
 */
const StorageHero = () => {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const isFr = (i18n.language || '').startsWith('fr');
  const isFacilityOrAdmin = !!user && (
    user.storage_facility_approved === true
    || user.account_type === 'storage_facility'
    || user.is_storage_facility === true
    || user.role === 'admin'
    || user.role === 'super_admin'
    || user.is_admin === true
  );

  return (
    <section className="storage-hero" data-testid="storage-hero">
      {/* Particle dots */}
      {Array.from({ length: 12 }).map((_, i) => {
        const top = (i * 37 + 12) % 100;
        const left = (i * 73 + 8) % 100;
        const size = 3 + (i % 4);
        const delay = (i * 0.4) % 3;
        return (
          <span
            key={i}
            className="storage-particle"
            style={{
              top: `${top}%`,
              left: `${left}%`,
              width: `${size}px`,
              height: `${size}px`,
              animationDelay: `${delay}s`,
            }}
          />
        );
      })}

      {/* Floating padlocks */}
      <span className="storage-hero__padlock padlock-1" aria-hidden>🔒</span>
      <span className="storage-hero__padlock padlock-2" aria-hidden>🔒</span>
      <span className="storage-hero__padlock padlock-3" aria-hidden>🔒</span>
      <span className="storage-hero__padlock padlock-4" aria-hidden>🔒</span>
      <span className="storage-hero__padlock padlock-5" aria-hidden>🔒</span>
      <span className="storage-hero__padlock padlock-6" aria-hidden>🔒</span>

      {/* Storage door silhouettes */}
      <div className="storage-doors" aria-hidden>
        <div className="storage-door"><span /></div>
        <div className="storage-door"><span /></div>
        <div className="storage-door"><span /></div>
      </div>

      <div className="storage-hero__inner">
        <span className="storage-hero__label" data-testid="storage-hero-label">
          {t('storage.hero.label')}
        </span>

        <h1 className="storage-hero__title" data-testid="storage-hero-title">
          {t('storage.hero.titleLine1')}
          <span className="storage-hero__title-line2">{t('storage.hero.titleLine2')}</span>
        </h1>

        <p className="storage-hero__subtitle" data-testid="storage-hero-subtitle">
          {t('storage.hero.subtitle')}
        </p>

        <div className="storage-hero__ctas">
          <LangLink
            to="/storage-auctions/browse"
            className="storage-hero__cta storage-hero__cta--primary"
            data-testid="storage-hero-browse-btn"
          >
            {t('storage.hero.ctaBrowse')}
          </LangLink>
          {isFacilityOrAdmin ? (
            <>
              <LangLink
                to="/facility/dashboard"
                className="storage-hero__cta storage-hero__cta--secondary"
                data-testid="storage-hero-facility-dashboard-btn"
              >
                📊 {isFr ? 'Tableau de bord' : 'Facility Dashboard'}
              </LangLink>
              <LangLink
                to="/create-listing?type=storage_locker"
                className="storage-hero__cta storage-hero__cta--secondary"
                data-testid="storage-hero-create-unit-btn"
              >
                ➕ {isFr ? 'Créer une enchère' : 'Create Unit Auction'}
              </LangLink>
            </>
          ) : (
            <LangLink
              to="/storage-auctions/register-facility"
              className="storage-hero__cta storage-hero__cta--secondary"
              data-testid="storage-hero-register-btn"
            >
              {t('storage.hero.ctaRegister')}
            </LangLink>
          )}
        </div>

        <div className="storage-hero__badges">
          <span className="storage-hero__badge">{t('storage.hero.badge1')}</span>
          <span className="storage-hero__badge">{t('storage.hero.badge2')}</span>
          <span className="storage-hero__badge">{t('storage.hero.badge3')}</span>
          <span className="storage-hero__badge">{t('storage.hero.badge4')}</span>
        </div>
      </div>
    </section>
  );
};

export default StorageHero;
