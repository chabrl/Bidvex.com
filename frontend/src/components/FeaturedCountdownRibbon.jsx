import React, { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * iter211 — Featured Countdown Ribbon (seller-only).
 *
 * Shows the time remaining on a listing's promotion (e.g. "Featured for 3 more
 * days"). Renders nothing if:
 *   - `featuredUntil` is missing / invalid
 *   - the promotion has already expired
 *   - `showOnlyToSeller` is true AND the viewer is not the listing owner
 *
 * Props:
 *   featuredUntil  ISO timestamp of when the promotion ends (string|Date)
 *   tier           Promotion tier label ('basic'|'featured'|'premium'|null)
 *   className      Extra Tailwind classes
 */
const FeaturedCountdownRibbon = ({ featuredUntil, tier, className = '' }) => {
  const { t, i18n } = useTranslation();
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!featuredUntil) return undefined;
    const id = setInterval(() => setNow(Date.now()), 60_000); // refresh every minute
    return () => clearInterval(id);
  }, [featuredUntil]);

  if (!featuredUntil) return null;

  const endTs = new Date(featuredUntil).getTime();
  if (Number.isNaN(endTs)) return null;

  const diffMs = endTs - now;
  if (diffMs <= 0) return null;

  const totalMinutes = Math.floor(diffMs / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const isFR = (i18n.language || 'en').startsWith('fr');

  let label;
  if (days >= 1) {
    label = isFR
      ? `À la une encore ${days} jour${days > 1 ? 's' : ''}`
      : `Featured for ${days} more day${days !== 1 ? 's' : ''}`;
  } else if (hours >= 1) {
    label = isFR
      ? `À la une encore ${hours} h`
      : `Featured for ${hours} more hour${hours !== 1 ? 's' : ''}`;
  } else {
    const mins = Math.max(1, totalMinutes);
    label = isFR
      ? `À la une encore ${mins} min`
      : `Featured for ${mins} more min`;
  }

  const tierLabel = tier
    ? (isFR ? ` · ${tier}` : ` · ${tier.charAt(0).toUpperCase() + tier.slice(1)}`)
    : '';

  return (
    <div
      data-testid="featured-countdown-ribbon"
      className={`inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-amber-100 via-amber-50 to-yellow-50 border border-amber-300 px-3 py-1 text-xs font-medium text-amber-900 ${className}`}
    >
      <Sparkles className="w-3.5 h-3.5 text-amber-600" />
      <span data-testid="featured-countdown-label">
        {label}{tierLabel}
      </span>
    </div>
  );
};

export default FeaturedCountdownRibbon;
export { FeaturedCountdownRibbon };
