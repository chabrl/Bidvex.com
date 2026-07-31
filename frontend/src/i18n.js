import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// All translations live in JSON files — single source of truth
import enTranslations from './locales/en.json';
import frTranslations from './locales/fr.json';

// Helper to get persisted language from localStorage.
//
// iter438 — Read order-of-preference:
//   1. `bidvex_language`  — our primary key (set on every language change)
//   2. `i18nextLng`       — i18next's default cache key (legacy /
//      cross-tab fallback for users who lived on an older init before
//      we renamed the cache key). Honoring both keys prevents a
//      cold-load flash of English when someone lands on the app with
//      only the legacy key populated.
// If either key holds a supported code ('en' | 'fr'), it's returned
// synchronously so `i18n.init({ lng })` picks it up BEFORE React
// mounts.
const getPersistedLanguage = () => {
  try {
    for (const key of ['bidvex_language', 'i18nextLng']) {
      const stored = localStorage.getItem(key);
      if (stored && ['en', 'fr'].includes(stored)) {
        return stored;
      }
    }
  } catch (e) {
    console.warn('localStorage not available for language persistence');
  }
  return null;
};

// iter443 — On module load, mirror the legacy `i18nextLng` value into
// our primary `bidvex_language` key BEFORE i18n.init() runs. This makes
// i18next-browser-languagedetector (which reads only `bidvex_language`
// via `lookupLocalStorage`) return the correct language on the FIRST
// render, eliminating the cold-load English flash for users who arrived
// with only the legacy cache key set.
try {
  const primary = localStorage.getItem('bidvex_language');
  if (!primary || !['en', 'fr'].includes(primary)) {
    const legacy = localStorage.getItem('i18nextLng');
    if (legacy && ['en', 'fr'].includes(legacy)) {
      localStorage.setItem('bidvex_language', legacy);
    }
  }
} catch (e) {
  // ignore — SSR / privacy modes
}

// Helper to persist language choice.
// iter438 — Mirror the value into both our primary key and the
// legacy `i18nextLng` so cross-tab / cross-init reads stay in sync.
export const persistLanguage = (lng) => {
  try {
    localStorage.setItem('bidvex_language', lng);
    localStorage.setItem('i18nextLng', lng);
  } catch (e) {
    console.warn('Could not persist language preference');
  }
};

const resources = {
  en: { translation: enTranslations },
  fr: { translation: frTranslations },
};

// Initialize i18next
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    lng: getPersistedLanguage() || undefined,
    fallbackLng: 'en',
    debug: false,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'bidvex_language',
      caches: ['localStorage'],
    },
    react: {
      useSuspense: false,
    },
  });

// Persist language on change
i18n.on('languageChanged', (lng) => {
  persistLanguage(lng);
});

export default i18n;
