/**
 * iter358 — LanguageContext.
 *
 * Reads the active language from the URL path prefix (/en/... or /fr/...),
 * syncs it to i18next + <html lang>, and exposes helpers for URL
 * translation + real navigation on language toggle.
 *
 * Placed INSIDE <BrowserRouter> so `useLocation` works.
 */
import React, { createContext, useContext, useEffect, useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  detectLangFromPath,
  toLangPath,
  translatePath,
  stripLangPrefix,
  EN_TO_FR,
  FR_TO_EN,
  CANONICAL_HOST,
} from '../i18n/urlMap';

const LanguageContext = createContext({
  lang: 'en',
  urlHasLangPrefix: false,
  switchLang: () => {},
  buildLangPath: (path) => path,
  buildAlternateUrls: () => ({ en: '', fr: '', xDefault: '' }),
});

export function LanguageProvider({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { i18n } = useTranslation();

  const urlHasLangPrefix = location.pathname === '/en' || location.pathname === '/fr'
    || location.pathname.startsWith('/en/') || location.pathname.startsWith('/fr/');

  // Detect from URL first; fall back to i18n's current language.
  const lang = urlHasLangPrefix
    ? detectLangFromPath(location.pathname)
    : (i18n.language && i18n.language.startsWith('fr') ? 'fr' : 'en');

  // iter443 — Sync i18n and <html lang> when the URL prefix changes.
  //
  // Only force `i18n.changeLanguage(lang)` when the URL is authoritative
  // for the language (i.e. `/en/*` or `/fr/*` prefix present). When the
  // URL has NO prefix, the user's persisted language preference —
  // already loaded synchronously by `i18n.init({ lng: … })` — MUST win.
  // Forcing changeLanguage on a fallback-computed `lang` was overwriting
  // the persisted preference on every cold-load, causing the app to
  // ignore `localStorage.i18nextLng` / `bidvex_language` and default to
  // English on first paint.
  useEffect(() => {
    if (urlHasLangPrefix && i18n.language !== lang) {
      i18n.changeLanguage(lang);
    }
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang;
    }
  }, [lang, i18n, urlHasLangPrefix]);

  const switchLang = useCallback((targetLang) => {
    if (targetLang !== 'en' && targetLang !== 'fr') return;
    if (targetLang === lang && urlHasLangPrefix) return;

    // iter363 → iter450 — Language toggle 404 fix.
    // Only navigate when the current path is language-prefix-eligible.
    // Otherwise (authenticated / utility pages like /settings, /messages,
    // /admin, /watchlist, /vehicle-auctions/create, /storage-auctions/bulk-import,
    // /vehicle-multi-lot/create, /vehicle-multi-lot/{id}/edit, etc.), just
    // change the i18n language without navigation.
    //
    // A "deep segment" (the part AFTER a mapped parent like /vehicle-auctions)
    // is only considered language-safe when it looks like an ID (has digits,
    // or is a UUID / long hex hash). Named sub-pages made purely of
    // lowercase letters + hyphens (e.g. "create", "bulk-import",
    // "for-facilities", "register-facility", "how-it-works", "browse",
    // "edit") are NEVER language-prefix-eligible because we don't ship
    // `/en/{parent}/{sub}` or `/fr/{parent}/{sub}` routes for them.
    const bare = stripLangPrefix(location.pathname);

    const looksLikeId = (segment) => {
      if (!segment) return false;
      if (/\d/.test(segment)) return true;                     // has any digit
      if (/^[a-f0-9-]{8,}$/i.test(segment)) return true;       // uuid / hex-hash
      return false;
    };

    const isDeepIdRoute = () => {
      const keys = Object.keys(EN_TO_FR).concat(Object.keys(FR_TO_EN));
      for (const parent of keys) {
        if (parent === '/') continue;
        const prefix = parent + '/';
        if (!bare.startsWith(prefix)) continue;
        const tail = bare.slice(prefix.length);
        // Only route deep IDs — the tail's FIRST segment must look like an ID.
        const firstSeg = tail.split('/')[0];
        return looksLikeId(firstSeg);
      }
      return false;
    };

    const isPrefixEligible = urlHasLangPrefix
      || bare === '/'
      || bare in EN_TO_FR
      || bare in FR_TO_EN
      || isDeepIdRoute();

    if (!isPrefixEligible) {
      // Just change the language; keep the URL as-is. Persistence is
      // handled by i18next's `languageChanged` listener in i18n.js.
      if (i18n.language !== targetLang) i18n.changeLanguage(targetLang);
      if (typeof document !== 'undefined') document.documentElement.lang = targetLang;
      return;
    }

    // Build the new URL: same page in the target language.
    // If the current URL has NO lang prefix, we still add one AND translate.
    const newPath = toLangPath(location.pathname + location.search + location.hash, targetLang);

    // Trigger a real navigation event — this is what makes Google index
    // /fr/encheres-vehicules as a distinct URL with French content.
    navigate(newPath);
  }, [lang, urlHasLangPrefix, location.pathname, location.search, location.hash, navigate, i18n]);

  const buildLangPath = useCallback((path) => {
    if (!path || typeof path !== 'string') return path;
    if (path.startsWith('http') || path.startsWith('mailto:') || path.startsWith('tel:')) return path;
    if (path.startsWith('/en/') || path.startsWith('/fr/') || path === '/en' || path === '/fr') return path;
    return toLangPath(path, lang);
  }, [lang]);

  const buildAlternateUrls = useCallback(() => {
    // Given the current URL, emit the EN + FR + x-default absolute URLs.
    const bare = stripLangPrefix(location.pathname);
    const enPath = FR_TO_EN[bare] || bare;
    const frPath = EN_TO_FR[bare] || bare;
    return {
      en: `${CANONICAL_HOST}/en${enPath === '/' ? '' : enPath}`,
      fr: `${CANONICAL_HOST}/fr${frPath === '/' ? '' : frPath}`,
      xDefault: `${CANONICAL_HOST}/en${enPath === '/' ? '' : enPath}`,
      current: `${CANONICAL_HOST}/${lang}${(lang === 'fr' ? frPath : enPath) === '/' ? '' : (lang === 'fr' ? frPath : enPath)}`,
    };
  }, [location.pathname, lang]);

  const value = useMemo(() => ({
    lang,
    urlHasLangPrefix,
    switchLang,
    buildLangPath,
    buildAlternateUrls,
  }), [lang, urlHasLangPrefix, switchLang, buildLangPath, buildAlternateUrls]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useLanguage = () => useContext(LanguageContext);
