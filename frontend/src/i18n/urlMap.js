/**
 * iter358 — Bilingual URL translation map.
 *
 * Maps canonical English slugs ↔ French slugs. Used by:
 *   • LangLink (component wrapper around React Router's <Link>)
 *   • Navbar language toggle (real navigation on click)
 *   • PageHead (hreflang cross-references)
 *   • App.js route registrations
 *
 * Keep entries in sync with:
 *   • backend/services/prerender_service._REGIONAL_LANDINGS (SSR truth)
 *   • backend/routes/sitemap.STATIC_PAGES (indexed URLs)
 *   • backend/services/press_release.press_release_paths()
 *
 * IMPORTANT: only slugs with unique FR translations are listed here.
 * Slugs that are identical in EN + FR (e.g., /faq, /contact, /auth)
 * are omitted — LangLink returns them unchanged.
 */

// Canonical EN slug → FR slug (path only, no lang prefix).
export const EN_TO_FR = {
  '/': '/',
  '/marketplace': '/marche',
  '/lots': '/lots',
  '/items': '/items',
  '/vehicle-auctions': '/encheres-vehicules',
  '/storage-auctions': '/encheres-entreposage',
  '/how-it-works': '/comment-ca-marche',
  '/how-brokers-work': '/comment-fonctionnent-les-courtiers',
  '/about': '/a-propos',
  '/about-us': '/a-propos',
  '/pricing': '/tarifs',
  '/terms-of-service': '/conditions-utilisation',
  '/legal/terms': '/legal/conditions',
  '/privacy-policy': '/politique-confidentialite',
  '/legal/privacy': '/legal/confidentialite',
  '/legal/refunds': '/legal/remboursements',
  '/refund-policy': '/politique-remboursement',
  '/careers': '/carrieres',
  '/community': '/communaute',
  '/blogs': '/blogues',
  '/prohibited-items': '/articles-interdits',
  '/press/quebec-launch': '/presse/lancement-quebec',
  '/affiliate-program': '/programme-affilies',
  '/broker-directory': '/annuaire-courtiers',
  '/brokers': '/courtiers',
  '/become-a-broker': '/devenir-courtier',
  '/become-a-partner': '/devenir-partenaire',
  '/vehicle-auctions-quebec': '/encheres-vehicules-quebec',
  '/storage-auctions-quebec': '/encheres-entreposage-quebec',
  '/vehicle-auctions-montreal': '/encheres-vehicules-montreal',
  '/vehicle-auctions-quebec-city': '/encheres-vehicules-quebec-ville',
  '/vehicle-auctions-sherbrooke': '/encheres-vehicules-sherbrooke',
  '/vehicle-auctions-laval': '/encheres-vehicules-laval',
  '/vehicle-auctions-gatineau': '/encheres-vehicules-gatineau',
  '/vehicle-auctions-saguenay': '/encheres-vehicules-saguenay',
  '/vehicle-auctions-trois-rivieres': '/encheres-vehicules-trois-rivieres',
  '/vehicle-auctions-longueuil': '/encheres-vehicules-longueuil',
  '/storage-auctions-montreal': '/encheres-entreposage-montreal',
  '/storage-auctions-quebec-city': '/encheres-entreposage-quebec-ville',
  '/storage-auctions-sherbrooke': '/encheres-entreposage-sherbrooke',
  '/storage-auctions-laval': '/encheres-entreposage-laval',
};

// FR slug → EN slug (inverse map).
export const FR_TO_EN = Object.fromEntries(
  Object.entries(EN_TO_FR).map(([en, fr]) => [fr, en])
);

/**
 * Strip a `/en/` or `/fr/` prefix from a path.
 * Returns the "bare" path, always starting with '/'.
 */
export function stripLangPrefix(path) {
  if (!path) return '/';
  if (path === '/en' || path === '/fr') return '/';
  if (path.startsWith('/en/')) return path.slice(3) || '/';
  if (path.startsWith('/fr/')) return path.slice(3) || '/';
  return path;
}

/**
 * Detect the active language from a URL path.
 * Returns 'en', 'fr', or the fallback ('en' by default).
 */
export function detectLangFromPath(path, fallback = 'en') {
  if (!path) return fallback;
  if (path === '/fr' || path.startsWith('/fr/')) return 'fr';
  if (path === '/en' || path.startsWith('/en/')) return 'en';
  return fallback;
}

/**
 * Translate a bare path (no lang prefix) into its target-language
 * equivalent. Returns the input unchanged when no translation exists.
 */
export function translatePath(path, targetLang) {
  const bare = stripLangPrefix(path || '/');
  if (targetLang === 'fr') {
    return EN_TO_FR[bare] || bare;
  }
  // targetLang === 'en' (default)
  return FR_TO_EN[bare] || bare;
}

/**
 * Build a fully-qualified in-app path with the language prefix.
 * Example:
 *   toLangPath('/marketplace', 'fr') → '/fr/marche'
 *   toLangPath('/vehicle-auctions/abc123', 'en') → '/en/vehicle-auctions/abc123'
 *
 * Preserves query strings and hash fragments.
 */
export function toLangPath(path, targetLang) {
  if (!path) return `/${targetLang}/`;
  // Parse trailing ?search#hash
  const hashIdx = path.indexOf('#');
  const hash = hashIdx >= 0 ? path.slice(hashIdx) : '';
  const pathNoHash = hashIdx >= 0 ? path.slice(0, hashIdx) : path;
  const qIdx = pathNoHash.indexOf('?');
  const query = qIdx >= 0 ? pathNoHash.slice(qIdx) : '';
  const rawPath = qIdx >= 0 ? pathNoHash.slice(0, qIdx) : pathNoHash;

  // Split path into head (first segment) + tail (deep path).
  // We only translate the first segment; deep IDs pass through.
  const bare = stripLangPrefix(rawPath);
  const segments = bare.split('/').filter(Boolean);
  const head = segments.length ? '/' + segments[0] : '/';
  const tail = segments.length > 1 ? '/' + segments.slice(1).join('/') : '';

  let translatedHead;
  if (targetLang === 'fr') {
    // Try full-path match first (for multi-segment routes like /legal/terms).
    translatedHead = EN_TO_FR[bare] || (EN_TO_FR[head] ? EN_TO_FR[head] + tail : bare);
  } else {
    translatedHead = FR_TO_EN[bare] || (FR_TO_EN[head] ? FR_TO_EN[head] + tail : bare);
  }
  if (translatedHead === '/') translatedHead = '';
  return `/${targetLang}${translatedHead}${query}${hash}`;
}

// Absolute host for hreflang emission (client-side).
export const CANONICAL_HOST = 'https://bidvex.com';
