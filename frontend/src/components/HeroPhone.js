import React from 'react';
import { useTranslation } from 'react-i18next';
import './HeroPhone.css';

/**
 * Hero phone mockup with floating animation, ambient glow, and 3 live-activity badges.
 * Bilingual badge labels (EN/FR) chosen automatically.
 */
const HeroPhone = () => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');

  return (
    <div className="hero-phone-container" data-testid="hero-phone-container">
      {/* Ambient glow */}
      <div className="hero-phone-glow" aria-hidden="true" />

      {/* Top-left badge — new bid (hidden on small screens) */}
      <div className="hero-badge hero-badge--top-left" aria-hidden="true">
        <span className="hero-badge__dot hero-badge__dot--green" />
        <span className="hero-badge__text">
          {fr ? '🔨 Nouvelle enchère — 245 $' : '🔨 New bid — $245'}
        </span>
      </div>

      {/* Top-right badge — bidder count */}
      <div className="hero-badge hero-badge--top-right" aria-hidden="true">
        <span className="hero-badge__text">
          {fr ? '👤 14 enchérisseurs en direct' : '👤 14 bidders live'}
        </span>
        <span className="hero-badge__dot hero-badge__dot--blue" />
      </div>

      {/* Phone image (floating wrapper) */}
      <div className="hero-phone-wrapper">
        <img
          src="/assets/hero-phone-mockup.png"
          alt={fr ? "Application mobile BidVex" : "BidVex mobile app"}
          className="hero-phone-image"
          loading="eager"
          fetchpriority="high"
          draggable={false}
        />
      </div>

      {/* Bottom badge — sold notification */}
      <div className="hero-badge hero-badge--bottom" aria-hidden="true">
        <span className="hero-badge__icon">✅</span>
        <div className="hero-badge__info">
          <span className="hero-badge__label">{fr ? 'Article vendu' : 'Item Sold'}</span>
          <span className="hero-badge__value">{fr ? '1 280 $ · il y a 3 s' : '$1,280 · 3s ago'}</span>
        </div>
      </div>
    </div>
  );
};

export default HeroPhone;
