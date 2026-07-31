/**
 * iter440 — Shared listing-image upload helper.
 *
 * All create-listing flows across BidVex (marketplace listings,
 * multi-item lots, vehicle listings, storage cleanouts, …) must upload
 * images to S3 via `POST /api/uploads/listing-image` and submit the
 * returned public HTTPS URL. Submitting base64 data URLs directly in
 * the listing payload was flagged by the nightly sweep because Mongo
 * documents balloon past the 16MB limit and the API-level guardrail
 * rejects the request outright (see `routes/listings.py` line 1213).
 *
 * Keep this file the single source of truth for the upload flow — do
 * NOT reimplement it inline in a new form.
 *
 * @param {File} file             — a browser File object from an <input type="file">
 * @param {object} [opts]
 * @param {string} [opts.authHeader]   — optional bearer token (auto-included by axios interceptor for most callers)
 * @returns {Promise<string>}     — public S3 URL. Throws if the upload fails or the response has no url.
 */
import axios from 'axios';

// Read the API base once at import time. Same pattern as every other
// caller in the codebase.
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export async function uploadListingImage(file, opts = {}) {
  if (!file) throw new Error('uploadListingImage: file is required');

  const form = new FormData();
  form.append('file', file);

  const headers = { 'Content-Type': 'multipart/form-data' };
  if (opts.authHeader) headers.Authorization = opts.authHeader;

  const res = await axios.post(`${API}/uploads/listing-image`, form, { headers });

  const url = res?.data?.url;
  if (!url || typeof url !== 'string' || url.startsWith('data:')) {
    throw new Error('uploadListingImage: no S3 URL returned by server');
  }
  return url;
}

/**
 * Upload many files in parallel — returns an array of URLs in the same
 * order as the input files. Fails fast on the first upload error so
 * the caller can surface a single toast.
 */
export async function uploadListingImages(files) {
  if (!files || !files.length) return [];
  return Promise.all(Array.from(files).map((f) => uploadListingImage(f)));
}

export default uploadListingImage;
