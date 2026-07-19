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
          // iter363 — Pillow-generated neutral auction mockup (not the
          // BidVex homepage) so there's no recursive-mirror effect. Both
          // EN + FR variants exist at /static/hero-phone-{lang}.png.
          // Content: sample vehicle auction card in the current language.
          src={fr ? "/static/hero-phone-fr.png" : "/static/hero-phone-en.png"}
          onError={(e) => {
            if (!e.currentTarget.dataset.fellBack) {
              e.currentTarget.dataset.fellBack = "1";
              // Fallback: use the original mockup PNG if the new static
              // assets haven't been served yet (e.g., during first deploy).
              e.currentTarget.src = "/assets/hero-phone-mockup.png";
            }
          }}
          alt={fr ? "Aperçu de l'application mobile BidVex" : "BidVex mobile app preview"}
          className="hero-phone-image"
          loading="eager"
          fetchPriority="high"
          draggable={false}
          width="460"
          height="945"
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
