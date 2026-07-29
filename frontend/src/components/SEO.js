import React from 'react';
import { Helmet } from 'react-helmet-async';
import { useLocation } from 'react-router-dom';

/**
 * SEO — dynamic per-page head component.
 *
 * iter411 — Now emits a normalized <link rel="canonical" href="…"> tag:
 *   * Base is `https://bidvex.com` (the canonical apex domain).
 *   * The homepage keeps its trailing slash (`https://bidvex.com/`).
 *   * Every other path is stripped of any trailing slash
 *     (`/marketplace/` → `/marketplace`) so we never expose duplicate
 *     URLs to Google (both variants would otherwise be indexed and
 *     compete for the same query).
 *   * When callers don't pass an explicit `path` prop, we fall back to
 *     the current `useLocation().pathname` — so any page that renders
 *     <SEO /> without a path still gets a correct canonical.
 */
export const SITE_URL = 'https://bidvex.com';

/**
 * Given a raw path (with or without leading `/`, with or without a
 * trailing `/`), return the absolute canonical URL. The homepage rule
 * ("keep the slash") is applied here so callers don't have to think
 * about it.
 */
export function buildCanonicalUrl(rawPath = '/') {
  let p = String(rawPath || '/');
  if (!p.startsWith('/')) p = `/${p}`;
  // Strip any query string / hash — canonicals must be one URL only.
  p = p.split('?')[0].split('#')[0];
  // Homepage keeps the trailing slash; every other path loses it.
  if (p !== '/' && p.endsWith('/')) p = p.replace(/\/+$/, '') || '/';
  return `${SITE_URL}${p === '/' ? '/' : p}`;
}

const SEO = ({
  title = 'BidVex',
  description = "BidVex — Canada's trusted online auction marketplace. Bid on electronics, vehicles, art, and more.",
  path,
  type = 'website',
  image = '/bidvex-og.png',
  noindex = false,
  jsonLd = null,
}) => {
  // iter411 — Prefer the caller-supplied `path`; otherwise auto-derive
  // from the current router location so every mount emits a canonical.
  const location = useLocation();
  const resolvedPath = typeof path === 'string' ? path : (location?.pathname || '/');
  const fullUrl = buildCanonicalUrl(resolvedPath);
  const fullTitle = title === 'BidVex' ? title : `${title} | BidVex`;

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={fullUrl} />

      {/* Open Graph */}
      <meta property="og:type" content={type} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={fullUrl} />
      <meta property="og:image" content={image} />
      <meta property="og:site_name" content="BidVex" />
      <meta property="og:locale" content="en_CA" />
      <meta property="og:locale:alternate" content="fr_CA" />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={image} />

      {noindex && <meta name="robots" content="noindex, nofollow" />}

      {/* Bilingual hreflang — BidVex is one URL with client-side language
          toggle, so EN/FR alternates point at the same canonical URL and
          x-default resolves to the EN version. */}
      <link rel="alternate" hrefLang="en-ca" href={fullUrl} />
      <link rel="alternate" hrefLang="fr-ca" href={fullUrl} />
      <link rel="alternate" hrefLang="x-default" href={fullUrl} />

      {/* JSON-LD Structured Data */}
      {jsonLd && (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd)}
        </script>
      )}
    </Helmet>
  );
};

export default SEO;
