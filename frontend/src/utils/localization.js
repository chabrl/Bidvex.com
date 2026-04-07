import i18n from '../i18n';

/**
 * Get the localized value of a field from a data object.
 * Looks for `field_en` / `field_fr` based on current i18n language.
 * Falls back to the base `field` if localized version is missing.
 *
 * @param {Object} item - The data object (listing, lot, etc.)
 * @param {string} field - Base field name (e.g., 'title', 'description')
 * @returns {string} The localized value
 *
 * Usage:
 *   getLocalized(listing, 'title')    // returns title_fr when lang=fr
 *   getLocalized(lot, 'description')  // returns description_en when lang=en
 */
export function getLocalized(item, field) {
  if (!item) return '';
  const lang = (i18n.language || 'en').substring(0, 2);
  const localizedKey = `${field}_${lang}`;
  const localizedValue = item[localizedKey];

  // Return localized version if it exists and is non-empty
  if (localizedValue && localizedValue.trim()) {
    return localizedValue;
  }

  // Fallback: try the other language, then the base field
  const fallbackLang = lang === 'fr' ? 'en' : 'fr';
  const fallbackKey = `${field}_${fallbackLang}`;
  return item[fallbackKey] || item[field] || '';
}

/**
 * Format currency amount following strict Quebec/Canadian standards.
 * EN: $5,000.00
 * FR: 5 000,00 $ (space before dollar sign, comma for decimals)
 *
 * @param {number} amount
 * @param {string} currency - ISO 4217 code (default 'CAD')
 * @returns {string}
 */
export function formatLocalizedCurrency(amount, currency = 'CAD') {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (num == null || isNaN(num)) return '$0.00';

  const lang = (i18n.language || 'en').substring(0, 2);
  const isFr = lang === 'fr';

  try {
    return new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  } catch {
    return `$${num.toFixed(2)}`;
  }
}

/**
 * Get dynamic Buyer Premium text for legal/terms display.
 * Returns the premium percentage and formatted text based on user tier.
 *
 * @param {string} tier - Subscription tier ('free', 'basic', 'premium', 'vip')
 * @param {number|null} customRate - Custom buyer premium rate from partner listing
 * @returns {{ rate: number, textEn: string, textFr: string }}
 */
export function getBuyerPremiumText(tier, customRate = null) {
  // Default rates by tier
  const tierRates = {
    free: 5,
    basic: 5,
    premium: 3.5,
    vip: 3,
  };

  const rate = customRate != null ? customRate * 100 : (tierRates[tier] || 5);
  const lang = (i18n.language || 'en').substring(0, 2);

  const textEn = `A buyer's premium of ${rate}% will be added to the hammer price of each lot.`;
  const textFr = `Une prime d'acheteur de ${rate.toFixed(1).replace('.', ',')} % sera ajout\u00e9e au prix d'adjudication de chaque lot.`;

  return {
    rate,
    text: lang === 'fr' ? textFr : textEn,
    textEn,
    textFr,
  };
}
