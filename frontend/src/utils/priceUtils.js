/**
 * iter233 — Price × Quantity multiplier utility.
 *
 * Encapsulates the *display-only* total-price math driven by the
 * `price_multiplied_by_quantity` boolean on every listing/lot document.
 *
 * Bidding logic (per spec) ALWAYS operates on the per-unit price; the
 * multiplier is purely for marketplace card + multi-lot card display.
 *
 *   computeDisplayPrice(listing) → {
 *     totalPrice:    number,   // basePrice × multiplier
 *     unitPrice:     number,   // basePrice (per-unit)
 *     isMultiplied:  boolean,  // true when display should show "× qty" UI
 *     quantity:      number,
 *     multiplier:    number,
 *   }
 *
 * basePrice resolution order: hammer_price → current_bid → starting_price → 0.
 * The multiplier kicks in only when `price_multiplied_by_quantity === true`
 * AND `quantity > 1` (defensively coerces missing/null fields).
 */
export function computeDisplayPrice(listing) {
  if (!listing || typeof listing !== 'object') {
    return { totalPrice: 0, unitPrice: 0, isMultiplied: false, quantity: 1, multiplier: 1 };
  }

  const {
    price_multiplied_by_quantity,
    quantity = 1,
    current_bid,
    current_price,
    starting_price,
    starting_bid,
    hammer_price,
    final_hammer_price,
  } = listing;

  // Resolve base unit price — hammer wins, then live bid, then start.
  const basePrice = Number(
    hammer_price
    ?? final_hammer_price
    ?? current_bid
    ?? current_price
    ?? starting_price
    ?? starting_bid
    ?? 0,
  ) || 0;

  const qty = Math.max(1, parseInt(quantity, 10) || 1);
  const shouldMultiply = !!price_multiplied_by_quantity && qty > 1;
  const multiplier = shouldMultiply ? qty : 1;

  return {
    totalPrice:   basePrice * multiplier,
    unitPrice:    basePrice,
    isMultiplied: multiplier > 1,
    quantity:     qty,
    multiplier,
  };
}

/**
 * Resolve the right "tense" label for the price callout based on listing
 * status + presence of a hammer / current bid. Used by marketplace cards.
 */
export function resolveDisplayPriceLabel(listing, lang = 'en') {
  const status = (listing?.status || '').toLowerCase();
  const isEnded = ['ended', 'sold', 'closed', 'completed'].includes(status);
  const hasBids = Number(listing?.current_bid ?? listing?.current_price ?? 0) > 0;

  if (isEnded) {
    return lang === 'fr' ? 'Prix total' : 'Total Price';
  }
  if (hasBids) {
    return lang === 'fr' ? 'Offre totale' : 'Total Bid';
  }
  return lang === 'fr' ? 'Total de départ' : 'Starting Total';
}

/**
 * Money formatter — wraps Intl.NumberFormat with CAD defaults and falls
 * back to a manual format if Intl isn't available.
 */
export function formatCurrency(value, { currency = 'CAD', lang = 'en' } = {}) {
  const n = Number(value) || 0;
  try {
    return new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `$${n.toFixed(2)}`;
  }
}

export default computeDisplayPrice;
