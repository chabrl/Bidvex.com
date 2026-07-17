/**
 * iter358 — LangLink.
 *
 * Drop-in replacement for react-router's <Link> that auto-prepends the
 * active language prefix and translates the FR slug when appropriate.
 *
 * Rules:
 *   • External URLs (http://, mailto:, tel:) pass through unchanged.
 *   • Absolute paths already carrying a lang prefix pass through.
 *   • Everything else gets `/${lang}` prepended, with FR slug remap.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';

export function LangLink({ to, children, ...rest }) {
  const { buildLangPath } = useLanguage();
  const finalTo = typeof to === 'string' ? buildLangPath(to) : to;
  return (
    <Link to={finalTo} {...rest}>
      {children}
    </Link>
  );
}

export default LangLink;
