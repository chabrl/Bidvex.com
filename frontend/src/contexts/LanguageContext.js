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

  // Sync i18n and <html lang> when the URL prefix changes.
  useEffect(() => {
    if (i18n.language !== lang) {
      i18n.changeLanguage(lang);
    }
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang;
    }
  }, [lang, i18n]);

  const switchLang = useCallback((targetLang) => {
    if (targetLang !== 'en' && targetLang !== 'fr') return;
    if (targetLang === lang && urlHasLangPrefix) return;

    // Build the new URL: same page in the target language.
    // If the current URL has NO lang prefix, we still add one AND translate.
    const newPath = toLangPath(location.pathname + location.search + location.hash, targetLang);

    // Trigger a real navigation event — this is what makes Google index
    // /fr/encheres-vehicules as a distinct URL with French content.
    navigate(newPath);
  }, [lang, urlHasLangPrefix, location.pathname, location.search, location.hash, navigate]);

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
