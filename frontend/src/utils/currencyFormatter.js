import i18n from '../i18n';

/**
 * Format a numeric amount as localized currency.
 *
 * EN:    $1,250.50
 * FR-QC: 1 250,50 $
 *
 * @param {number|string|null|undefined} amount - The numeric value to format
 * @param {string} [currency='CAD'] - ISO 4217 currency code
 * @returns {string} Formatted currency string
 */
export function formatCurrency(amount, currency = 'CAD') {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (num == null || isNaN(num)) return currency === 'USD' ? '$0.00' : '$0.00';

  const lang = i18n.language || 'en';
  const isFr = lang.startsWith('fr');

  try {
    const formatted = new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
    return formatted;
  } catch {
    // Fallback
    return `$${num.toFixed(2)}`;
  }
}

/**
 * Format a number as compact currency (for large values).
 * e.g., $1.2K, $3.4M
 */
export function formatCurrencyCompact(amount, currency = 'CAD') {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (num == null || isNaN(num)) return '$0';

  const lang = i18n.language || 'en';
  const isFr = lang.startsWith('fr');

  try {
    return new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency,
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(num);
  } catch {
    return `$${num.toFixed(0)}`;
  }
}

/**
 * Format a percentage value for display.
 * EN: 15.0%  |  FR: 15,0 %
 */
export function formatPercent(value, decimals = 1) {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (num == null || isNaN(num)) return '0%';

  const lang = i18n.language || 'en';
  const isFr = lang.startsWith('fr');

  try {
    return new Intl.NumberFormat(isFr ? 'fr-CA' : 'en-CA', {
      style: 'percent',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(num / 100);
  } catch {
    return `${num.toFixed(decimals)}%`;
  }
}
