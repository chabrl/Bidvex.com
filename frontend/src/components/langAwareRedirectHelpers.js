/**
 * iter450 — Pure helpers for the language-aware redirect decision.
 *
 * Kept in a separate module (no react-router imports) so unit tests
 * can run without dragging Jest through the router transform.
 */
import { EN_TO_FR, stripLangPrefix } from '../i18n/urlMap';

/**
 * Read the persisted language from localStorage.
 *
 * Priority order (matches i18n.js):
 *   1. `bidvex_language`  — our primary key
 *   2. `i18nextLng`       — legacy fallback for older users
 *
 * Returns 'en' | 'fr'. Defaults to 'en' when nothing supported is
 * stored or when localStorage throws (SSR / privacy modes).
 */
export const readPersistedLang = () => {
  try {
    for (const key of ['bidvex_language', 'i18nextLng']) {
      const stored = localStorage.getItem(key);
      if (stored === 'en' || stored === 'fr') return stored;
    }
  } catch (_e) {
    // ignore
  }
  return 'en';
};

/**
 * Pure target-selection helper.
 *
 * Given a canonical EN path (e.g. `/en/marketplace`) and the persisted
 * language, return the destination URL. Slug is translated via
 * EN_TO_FR when the target language is FR. Preserves ?search and #hash.
 */
export const computeLangAwareTarget = (enPath, lang, search = '', hash = '') => {
  const bare = stripLangPrefix(enPath || '/');
  let target;
  if (lang === 'fr') {
    const frSlug = EN_TO_FR[bare] || bare;
    target = `/fr${frSlug}`.replace(/\/$/, '') || '/fr/';
  } else {
    target = `/en${bare}`.replace(/\/$/, '') || '/en/';
  }
  return `${target}${search}${hash}`;
};
