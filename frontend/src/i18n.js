import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// All translations live in JSON files — single source of truth
import enTranslations from './locales/en.json';
import frTranslations from './locales/fr.json';

// Helper to get persisted language from localStorage
const getPersistedLanguage = () => {
  try {
    const stored = localStorage.getItem('bidvex_language');
    if (stored && ['en', 'fr'].includes(stored)) {
      return stored;
    }
  } catch (e) {
    console.warn('localStorage not available for language persistence');
  }
  return null;
};

// Helper to persist language choice
export const persistLanguage = (lng) => {
  try {
    localStorage.setItem('bidvex_language', lng);
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
