/**
 * iter364 — Listing image URL resolver.
 *
 * Given a listing / vehicle / storage-auction / lot object, returns the
 * best available image URL, following the field-name priority chain used
 * across BidVex's data collections:
 *
 *   1. images[0]     (most listings)
 *   2. image_url     (some seed data + admin manual entries)
 *   3. photos[0]     (vehicle listings, storage auctions)
 *   4. thumbnail_url (broker/facility profiles)
 *   5. photo_url     (legacy admin uploads)
 *   6. /static/placeholder.png fallback
 *
 * Combined with <SafeImage>'s onError → placeholder.png behaviour, this
 * eliminates the "grey placeholder boxes on listing cards" bug reported
 * in iter364.
 */
export const LISTING_IMAGE_PLACEHOLDER = '/static/placeholder.png';

export function getListingImage(item) {
  if (!item || typeof item !== 'object') return LISTING_IMAGE_PLACEHOLDER;
  const candidates = [
    item.images?.[0],
    item.image_url,
    item.photos?.[0],
    item.thumbnail_url,
    item.photo_url,
    item.image,          // very old data shape
    item.thumbnail,      // very old data shape
  ];
  for (const c of candidates) {
    if (typeof c === 'string' && c.trim() && !c.trim().startsWith('data:image/png;base64,iVBORw0KG')) {
      // Skip empty strings + the tiny 1×1 transparent PNG sentinel some
      // legacy migrations used before real photo upload was implemented.
      return c;
    }
  }
  return LISTING_IMAGE_PLACEHOLDER;
}

export default getListingImage;
