/**
 * iter299 P0 — Bill 96 (Charter of the French Language) helpers.
 *
 * Quebec listings legally require a French title. The backend enforces
 * this (`qc_french_title_required`) — these helpers make the frontend
 * comply BEFORE the API is ever hit, and humanize the API error if it
 * still somehow triggers (e.g. direct API calls).
 */

const QC_TOKENS = ['qc', 'quebec', 'québec'];

/** True when the seller's province OR the listing location is Quebec. */
export function isQuebecListing(sellerProvince, listingRegion, listingCity) {
  const norm = (v) => String(v || '').trim().toLowerCase();
  if (QC_TOKENS.includes(norm(sellerProvince))) return true;
  if (QC_TOKENS.includes(norm(listingRegion))) return true;
  const city = norm(listingCity);
  // Major QC city safety net (mirrors backend _is_quebec_listing).
  return ['montreal', 'montréal', 'quebec city', 'sherbrooke', 'laval',
          'gatineau', 'longueuil', 'trois-rivières', 'trois-rivieres'].includes(city);
}

/**
 * Client-side Bill 96 check. Returns a bilingual error object when the
 * listing is in Quebec and the French title is missing, else null.
 */
export function validateFrenchTitle({ isQC, titleFr }) {
  if (!isQC) return null;
  if (String(titleFr || '').trim()) return null;
  return {
    en: 'A French title is required for Quebec listings under Bill 96.',
    fr: 'Un titre en français est obligatoire pour les annonces québécoises (Loi 96).',
  };
}

/**
 * Humanize the backend Bill 96 422 errors. Returns a readable string in
 * the user's language, or null when the error isn't a Bill 96 error.
 */
export function humanizeQcError(error, isFr) {
  const detail = error?.response?.data?.detail;
  if (!detail || typeof detail !== 'object') return null;
  const code = detail.error || detail.code;
  if (code !== 'qc_french_title_required' && code !== 'qc_french_description_required') {
    return null;
  }
  const msg = isFr ? detail.message_fr : detail.message_en;
  if (msg) return msg;
  return code === 'qc_french_title_required'
    ? (isFr
        ? 'Un titre en français est obligatoire pour les annonces québécoises (Loi 96).'
        : 'A French title is required for Quebec listings under Bill 96.')
    : (isFr
        ? 'Une description en français est obligatoire pour les annonces québécoises (Loi 96).'
        : 'A French description is required for Quebec listings under Bill 96.');
}
