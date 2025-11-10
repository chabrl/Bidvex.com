/**
 * Currency formatting utilities for BidVex
 * Supports CAD and USD with proper symbols and formatting
 */

export const CURRENCIES = {
  CAD: {
    code: 'CAD',
    symbol: '$',
    flag: '🇨🇦',
    name: 'Canadian Dollar',
    nameFr: 'Dollar Canadien',
  },
  USD: {
    code: 'USD',
    symbol: '$',
    flag: '🇺🇸',
    name: 'US Dollar',
    nameFr: 'Dollar Américain',
  },
};

/**
 * Format currency with symbol and proper decimal places
 * @param {number} amount - The amount to format
 * @param {string} currency - Currency code (CAD or USD)
 * @param {boolean} showSymbol - Whether to show the currency symbol
 * @returns {string} Formatted currency string
 */
export const formatCurrency = (amount, currency = 'CAD', showSymbol = true) => {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return showSymbol ? `${CURRENCIES[currency]?.symbol || '$'}0.00` : '0.00';
  }

  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);

  if (showSymbol) {
    return `${CURRENCIES[currency]?.symbol || '$'}${formatted}`;
  }

  return formatted;
};

/**
 * Format currency with flag emoji
 * @param {number} amount - The amount to format
 * @param {string} currency - Currency code (CAD or USD)
 * @returns {string} Formatted currency with flag
 */
export const formatCurrencyWithFlag = (amount, currency = 'CAD') => {
  const formatted = formatCurrency(amount, currency, true);
  const flag = CURRENCIES[currency]?.flag || '';
  return `${flag} ${formatted} ${currency}`;
};

/**
 * Get currency icon component
 * @param {string} currency - Currency code (CAD or USD)
 * @returns {string} Currency flag emoji
 */
export const getCurrencyIcon = (currency = 'CAD') => {
  return CURRENCIES[currency]?.flag || '🇨🇦';
};

/**
 * Get currency symbol
 * @param {string} currency - Currency code (CAD or USD)
 * @returns {string} Currency symbol
 */
export const getCurrencySymbol = (currency = 'CAD') => {
  return CURRENCIES[currency]?.symbol || '$';
};

/**
 * Get currency name
 * @param {string} currency - Currency code (CAD or USD)
 * @param {string} lang - Language code ('en' or 'fr')
 * @returns {string} Currency name
 */
export const getCurrencyName = (currency = 'CAD', lang = 'en') => {
  if (lang === 'fr') {
    return CURRENCIES[currency]?.nameFr || 'Dollar Canadien';
  }
  return CURRENCIES[currency]?.name || 'Canadian Dollar';
};

/**
 * Format price for display in listings
 * @param {number} price - The price to format
 * @param {string} currency - Currency code (CAD or USD)
 * @param {boolean} compact - Use compact format (e.g., $1.2K)
 * @returns {string} Formatted price
 */
export const formatPrice = (price, currency = 'CAD', compact = false) => {
  if (compact && price >= 1000) {
    const k = price / 1000;
    return `${CURRENCIES[currency]?.symbol || '$'}${k.toFixed(1)}K ${currency}`;
  }
  return `${formatCurrency(price, currency)} ${currency}`;
};
