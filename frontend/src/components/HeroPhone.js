import React from 'react';
import { useTranslation } from 'react-i18next';
import './HeroPhone.css';

/**
 * iter364 — Hero phone mockup (client-provided assets).
 *
 * Uses the two premium hand+phone renders shipped by the client:
 *   • EN → /assets/hero-phone-en.png  ("Discover. Bid. Win.")
 *   • FR → /assets/hero-phone-fr.png  ("Découvrez. Misez. Gagnez.")
 *
 * These renders are self-contained (hand, angled phone, on-screen
 * "Live Auctions Happening Now" pill, translated headline + CTAs) so
 * the earlier floating-badge overlays were removed to avoid visual
 * clashes with the hand + off-axis phone bezel.
 *
 * Sizing (per iter364 spec):
 *   • Desktop: width 420px, hand allowed to extend outside container
 *     (`overflow: visible` on wrapper).
 *   • Mobile <=768px: max-width 280px, headline stacks above phone.
 */
const HeroPhone = () => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');

  return (
    <div className="hero-phone-container" data-testid="hero-phone-container">
      {/* Ambient glow — kept because the client-provided phone drop-shadow
          is subtle and the glow adds motion; positioned behind the hand. */}
      <div className="hero-phone-glow" aria-hidden="true" />

      {/* Client-provided phone+hand mockup — language-aware. */}
      <div className="hero-phone-wrapper hero-phone-section">
        <img
          src={fr ? '/assets/hero-phone-fr.png' : '/assets/hero-phone-en.png'}
          onError={(e) => {
            if (!e.currentTarget.dataset.fellBack) {
              e.currentTarget.dataset.fellBack = '1';
              // Legacy Pillow-rendered fallback if the /assets file is
              // missing on first deploy — better than a broken image.
              e.currentTarget.src = '/assets/hero-phone-mockup.png';
            }
          }}
          alt={fr
            ? "Aperçu de l'application mobile BidVex — Découvrez. Misez. Gagnez."
            : 'BidVex mobile app preview — Discover. Bid. Win.'}
          className="hero-phone-image hero-phone-mockup"
          loading="eager"
          fetchPriority="high"
          draggable={false}
          width="1295"
          height="1215"
        />
      </div>
    </div>
  );
};

export default HeroPhone;
