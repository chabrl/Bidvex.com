/**
 * iter231 — Schema.org Product / Vehicle JSON-LD for auction listings.
 *
 * Solves Google Merchant Center's "Price Mismatch" warning by giving the
 * crawler a deterministic price source that mirrors what we publish in
 * the feed (= current_bid, NEVER buy_now_price). Also adds Offer
 * priceValidUntil so Google understands the auction's end-time.
 *
 * Includes an "AggregateOffer" wrapper so Google reads the live bid as
 * a range (starting_price → current_bid) instead of a single static
 * price — appropriate for an auction.
 *
 * Drop it once at the top of every listing detail page:
 *   <ListingJsonLd listing={listing} canonicalUrl="..." />
 */
import React from 'react';

const SITE = 'https://bidvex.com';

const _safeNum = (v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v));
const _img = (v) => (Array.isArray(v) ? v.filter(Boolean) : v ? [v] : []);

export default function ListingJsonLd({ listing, canonicalUrl }) {
  if (!listing?.id) return null;

  const isVehicle = (listing.category || listing.listing_type || '').toLowerCase().includes('vehicle')
                || listing.listing_type === 'vehicle';

  const startingPrice = _safeNum(listing.starting_price ?? listing.starting_bid ?? listing.reserve_price);
  const currentBid    = _safeNum(listing.current_bid ?? listing.highest_bid ?? startingPrice);
  const validUntil    = listing.auction_end_date || listing.ends_at || listing.end_time;
  const availability  = (() => {
    const s = (listing.status || '').toLowerCase();
    if (['ended', 'sold', 'closed', 'completed'].includes(s)) return 'https://schema.org/SoldOut';
    if (s === 'paused') return 'https://schema.org/Discontinued';
    return 'https://schema.org/InStock';
  })();

  const url = canonicalUrl || `${SITE}/${isVehicle ? 'vehicles' : 'listings'}/${listing.id}`;

  // Common offer envelope — AggregateOffer when we have both starting + current,
  // single Offer otherwise.
  const offer = (startingPrice && currentBid && startingPrice !== currentBid)
    ? {
        '@type':          'AggregateOffer',
        priceCurrency:    listing.currency || 'CAD',
        lowPrice:         startingPrice,
        highPrice:        currentBid,
        offerCount:       listing.bid_count || 1,
        availability,
        url,
        priceValidUntil:  validUntil,
        seller:           { '@type': 'Organization', name: 'BidVex Inc.' },
      }
    : {
        '@type':          'Offer',
        priceCurrency:    listing.currency || 'CAD',
        price:            currentBid ?? startingPrice ?? 0,
        availability,
        url,
        priceValidUntil:  validUntil,
        itemCondition:    'https://schema.org/UsedCondition',
        seller:           { '@type': 'Organization', name: 'BidVex Inc.' },
      };

  // Build the Product node — Vehicle subtype when applicable
  const product = isVehicle
    ? {
        '@context':       'https://schema.org',
        '@type':          'Vehicle',
        '@id':            listing.id,                  // ← matches feed `id` 1:1
        sku:              listing.id,
        name:             listing.title || `${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`.trim(),
        description:      listing.description || '',
        image:            _img(listing.images || listing.image),
        url,
        vehicleIdentificationNumber: listing.vin,
        brand:            listing.make ? { '@type': 'Brand', name: listing.make } : undefined,
        model:            listing.model,
        productionDate:   listing.year ? String(listing.year) : undefined,
        mileageFromOdometer: listing.mileage_km
          ? { '@type': 'QuantitativeValue', value: listing.mileage_km, unitCode: 'KMT' }
          : undefined,
        fuelType:         listing.fuel_type,
        bodyType:         listing.body_type,
        vehicleTransmission: listing.transmission,
        color:            listing.exterior_color,
        offers:           offer,
      }
    : {
        '@context':  'https://schema.org',
        '@type':     'Product',
        '@id':       listing.id,
        sku:         listing.id,
        name:        listing.title,
        description: listing.description || '',
        image:       _img(listing.images || listing.image),
        url,
        category:    listing.category,
        brand:       listing.brand ? { '@type': 'Brand', name: listing.brand } : undefined,
        offers:      offer,
      };

  // Remove undefined keys recursively so Google's parser doesn't trip
  const clean = JSON.parse(JSON.stringify(product));

  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: JSON.stringify(clean) }}
      data-testid="listing-jsonld"
    />
  );
}
