import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './StorageHero.css';

const StorageHero = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');

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
          {isFr ? "ENCHÈRES D'UNITÉS D'ENTREPOSAGE" : 'STORAGE UNIT AUCTIONS'}
        </span>

        <h1 className="storage-hero__title">
          {isFr ? 'Trésors cachés.' : 'Hidden Treasures.'}
          <span className="storage-hero__title-line2">
            {isFr ? ' Révélés.' : ' Revealed.'}
          </span>
          <div className="storage-hero__title-fr">
            {isFr ? 'Hidden Treasures. Revealed.' : 'Trésors cachés. Révélés.'}
          </div>
        </h1>

        <p className="storage-hero__subtitle">
          {isFr
            ? "Enchérissez sur des unités d'entreposage abandonnées de facilités canadiennes vérifiées. Aucuns frais acheteur. Aucune charge cachée. Juste des enchères pures."
            : "Bid on abandoned storage units from verified Canadian facilities. No buyer fees. No hidden charges. Just pure auction."}
        </p>
        <p className="storage-hero__subtitle storage-hero__subtitle--fr">
          {isFr
            ? "Bid on abandoned storage units from verified Canadian facilities. No buyer fees."
            : "Enchérissez sur des unités d'entreposage abandonnées de facilités canadiennes vérifiées. Aucuns frais acheteur."}
        </p>

        <div className="storage-hero__ctas">
          <Link
            to="/storage-auctions/browse"
            className="storage-hero__cta storage-hero__cta--primary"
            data-testid="storage-hero-browse-btn"
          >
            {isFr ? 'Parcourir les enchères →' : 'Browse Storage Auctions →'}
          </Link>
          <Link
            to="/storage-auctions/register-facility"
            className="storage-hero__cta storage-hero__cta--secondary"
            data-testid="storage-hero-register-btn"
          >
            {isFr ? 'Lister votre facilité' : 'List Your Facility'}
          </Link>
        </div>

        <div className="storage-hero__badges">
          <span className="storage-hero__badge">🔒 {isFr ? 'Facilités vérifiées uniquement' : 'Verified Facilities Only'}</span>
          <span className="storage-hero__badge">💰 {isFr ? 'Aucuns frais acheteur' : 'No Buyer Fees'}</span>
          <span className="storage-hero__badge">🇨🇦 {isFr ? 'Plateforme canadienne' : 'Canadian Platform'}</span>
          <span className="storage-hero__badge">⚡ {isFr ? 'Enchères en temps réel' : 'Real-Time Bidding'}</span>
        </div>
      </div>
    </section>
  );
};

export default StorageHero;
