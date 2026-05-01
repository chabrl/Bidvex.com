import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './StorageHero.css';

// Single source of truth for hero copy — content swaps based on user language.
const STORAGE_HERO_CONTENT = {
  en: {
    eyebrow: 'STORAGE UNIT AUCTIONS',
    line1: 'Hidden Treasures.',
    line2: 'Revealed.',
    subtitle: 'Bid on abandoned storage units from verified Canadian facilities. No buyer fees on cash auctions. Pure bidding.',
    cta_browse: 'Browse Auctions →',
    cta_list: 'List Your Facility',
    badge1: '🔒 Verified facilities only',
    badge2: '💰 Transparent fees',
    badge3: '🇨🇦 Canadian platform',
    badge4: '⚡ Real-time bidding',
  },
  fr: {
    eyebrow: "ENCHÈRES D'UNITÉS D'ENTREPOSAGE",
    line1: 'Trésors cachés.',
    line2: 'Révélés.',
    subtitle: "Enchérissez sur des unités d'entreposage abandonnées de facilités canadiennes vérifiées. Frais transparents. Enchères pures.",
    cta_browse: 'Parcourir les enchères →',
    cta_list: 'Lister votre facilité',
    badge1: '🔒 Facilités vérifiées uniquement',
    badge2: '💰 Frais transparents',
    badge3: '🇨🇦 Plateforme canadienne',
    badge4: '⚡ Enchères en temps réel',
  },
};

const StorageHero = () => {
  const { i18n } = useTranslation();
  const lang = (i18n.language || '').startsWith('fr') ? 'fr' : 'en';
  const t = STORAGE_HERO_CONTENT[lang];

  // 12 particle dots positioned absolutely
  const particles = Array.from({ length: 12 }).map((_, i) => {
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
  });

  return (
    <section className="storage-hero" data-testid="storage-hero">
      {/* Particle dots */}
      {particles}

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

      {/* Hero content */}
      <div className="storage-hero__inner">
        <span className="storage-hero__label" data-testid="storage-hero-label">
          {t.eyebrow}
        </span>

        <h1 className="storage-hero__title" data-testid="storage-hero-title">
          {t.line1}
          <span className="storage-hero__title-line2">{` ${t.line2}`}</span>
        </h1>

        <p className="storage-hero__subtitle" data-testid="storage-hero-subtitle">
          {t.subtitle}
        </p>

        <div className="storage-hero__ctas">
          <Link
            to="/storage-auctions/browse"
            className="storage-hero__cta storage-hero__cta--primary"
            data-testid="storage-hero-browse-btn"
          >
            {t.cta_browse}
          </Link>
          <Link
            to="/storage-auctions/register-facility"
            className="storage-hero__cta storage-hero__cta--secondary"
            data-testid="storage-hero-register-btn"
          >
            {t.cta_list}
          </Link>
        </div>

        <div className="storage-hero__badges">
          <span className="storage-hero__badge">{t.badge1}</span>
          <span className="storage-hero__badge">{t.badge2}</span>
          <span className="storage-hero__badge">{t.badge3}</span>
          <span className="storage-hero__badge">{t.badge4}</span>
        </div>
      </div>
    </section>
  );
};

export default StorageHero;
