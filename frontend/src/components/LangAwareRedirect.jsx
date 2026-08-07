/**
 * LangAwareRedirect — iter450
 *
 * Replacement for the hard-coded `<Navigate to="/en/marketplace" replace />`
 * pattern used across App.js for unprefixed public routes.
 *
 * The old form forced every visitor to `/en/*` even when their persisted
 * language preference was FR — which then made the URL authoritative in
 * LanguageContext and OVERWROTE the FR preference on every render.
 *
 * This thin wrapper defers all pure logic to
 * `langAwareRedirectHelpers.js` so unit tests can cover the target
 * selection + persisted-lang reading without booting react-router.
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import {
  readPersistedLang,
  computeLangAwareTarget,
} from './langAwareRedirectHelpers';

// Re-export for callers already importing from this file.
export { readPersistedLang, computeLangAwareTarget };

/**
 * `enPath` is the canonical EN path this redirect should map to when
 * the user's persisted language is EN. Example: `/en/marketplace`.
 * The FR twin is derived automatically via `EN_TO_FR` so callers stay
 * DRY.
 */
export const LangAwareRedirect = ({ enPath }) => {
  const location = useLocation();
  const lang = readPersistedLang();
  const to = computeLangAwareTarget(enPath, lang, location.search, location.hash);
  return <Navigate to={to} replace />;
};

export default LangAwareRedirect;
