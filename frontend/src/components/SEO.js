import React from 'react';
import { Helmet } from 'react-helmet-async';

/**
 * SEO component for dynamic head management.
 * Use on every page to set unique title + description.
 */
const SEO = ({ 
  title = 'BidVex', 
  description = 'BidVex — Canada\'s trusted online auction marketplace. Bid on electronics, vehicles, art, and more.',
  path = '',
  type = 'website',
  image = '/bidvex-og.png',
  noindex = false,
  jsonLd = null,
}) => {
  const siteUrl = 'https://bidvex.com';
  const fullUrl = `${siteUrl}${path}`;
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
