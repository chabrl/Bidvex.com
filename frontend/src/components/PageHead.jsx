/**
 * iter358 — PageHead.
 *
 * Emits <title>, <meta name="description">, canonical + hreflang link tags
 * on the SPA side so client-rendered pages (non-crawler traffic) still
 * show the correct language variant links.
 *
 * Bots continue to receive the pure SSR HTML from backend/routes/prerender.py.
 */
import React from 'react';
import { Helmet } from 'react-helmet-async';
import { useLanguage } from '../contexts/LanguageContext';

export function PageHead({ title, description, ogImage }) {
  const { lang, buildAlternateUrls } = useLanguage();
  const alt = buildAlternateUrls();
  return (
    <Helmet>
      {title && <title>{title}</title>}
      {description && <meta name="description" content={description} />}
      <link rel="canonical" href={alt.current} />
      <link rel="alternate" hrefLang="en-CA" href={alt.en} />
      <link rel="alternate" hrefLang="fr-CA" href={alt.fr} />
      <link rel="alternate" hrefLang="x-default" href={alt.xDefault} />
      <html lang={lang} />
      {ogImage && <meta property="og:image" content={ogImage} />}
      <meta property="og:locale" content={lang === 'fr' ? 'fr_CA' : 'en_CA'} />
      <meta property="og:locale:alternate" content={lang === 'fr' ? 'en_CA' : 'fr_CA'} />
    </Helmet>
  );
}

export default PageHead;
