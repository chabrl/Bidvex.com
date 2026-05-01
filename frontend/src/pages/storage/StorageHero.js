import React from 'react';
import { Link } from 'react-router-dom';
import './StorageHero.css';

/**
 * StorageHero — renders EN + FR simultaneously.
 * Quebec Bill 96 requires both languages to be visible on the same page.
 * We render English as the primary (larger) line and French as a secondary
 * (smaller, sky-tinted) line directly beneath it.
 */
const StorageHero = () => (
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

    {/* Hero content — both languages always visible */}
    <div className="storage-hero__inner">
      <span className="storage-hero__label" data-testid="storage-hero-label-en">
        STORAGE UNIT AUCTIONS
      </span>
      <span className="storage-hero__label storage-hero__label--fr" data-testid="storage-hero-label-fr">
        ENCHÈRES D'UNITÉS D'ENTREPOSAGE
      </span>

      <h1 className="storage-hero__title" data-testid="storage-hero-title-en">
        Hidden Treasures.<span className="storage-hero__title-line2"> Revealed.</span>
      </h1>
      <h2 className="storage-hero__title-fr-visible" data-testid="storage-hero-title-fr">
        Trésors cachés. <span className="storage-hero__title-fr-line2">Révélés.</span>
      </h2>

      <p className="storage-hero__subtitle" data-testid="storage-hero-subtitle-en">
        Bid on abandoned storage units from verified Canadian facilities. No buyer fees on cash auctions. Pure bidding.
      </p>
      <p className="storage-hero__subtitle-fr-visible" data-testid="storage-hero-subtitle-fr">
        Enchérissez sur des unités d'entreposage abandonnées de facilités canadiennes vérifiées. Frais transparents. Enchères pures.
      </p>

      <div className="storage-hero__ctas">
        <Link
          to="/storage-auctions/browse"
          className="storage-hero__cta storage-hero__cta--primary"
          data-testid="storage-hero-browse-btn"
        >
          <span className="cta-en">Browse Auctions →</span>
          <span className="cta-fr">Parcourir les enchères →</span>
        </Link>
        <Link
          to="/storage-auctions/register-facility"
          className="storage-hero__cta storage-hero__cta--secondary"
          data-testid="storage-hero-register-btn"
        >
          <span className="cta-en">List Your Facility</span>
          <span className="cta-fr">Lister votre facilité</span>
        </Link>
      </div>

      <div className="storage-hero__badges">
        <span className="storage-hero__badge">
          <span>🔒 Verified facilities only</span>
          <span className="badge-fr">🔒 Facilités vérifiées uniquement</span>
        </span>
        <span className="storage-hero__badge">
          <span>💰 Transparent fees</span>
          <span className="badge-fr">💰 Frais transparents</span>
        </span>
        <span className="storage-hero__badge">
          <span>🇨🇦 Canadian platform</span>
          <span className="badge-fr">🇨🇦 Plateforme canadienne</span>
        </span>
        <span className="storage-hero__badge">
          <span>⚡ Real-time bidding</span>
          <span className="badge-fr">⚡ Enchères en temps réel</span>
        </span>
      </div>
    </div>
  </section>
);

export default StorageHero;
