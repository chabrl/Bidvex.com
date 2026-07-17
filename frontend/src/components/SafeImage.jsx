/**
 * Phase 5 Hotfix v4 — SafeImage (refined threshold-based base64 handling)
 *
 * Drop-in replacement for `<img>` that guarantees a renderable image while
 * letting real user-uploaded base64 photos render naturally. Three modes:
 *
 *   1. `src` is null, undefined, or empty string → branded placeholder
 *   2. `src` is a SHORT base64 data URL (< 5,000 chars) → branded placeholder
 *      Rationale: a tiny base64 string is almost always a 1×1 transparent
 *      pixel, a broken thumbnail, or a sentinel value from a stale migration.
 *      Real photos encode to >> 5,000 characters (a 500×500 JPEG ≈ 30–60KB
 *      ≈ 40,000–80,000 chars after base64). Letting real photos through
 *      means Alex Boulanger's leather banquette images render instantly
 *      while the marketplace card stays clean of broken placeholders.
 *   3. `<img>` onError fires (network failure, 404, corrupt file) →
 *      branded placeholder
 *
 * Placeholder URL: `https://bidvex.com/assets/placeholder-ad.jpg`
 *
 * Usage:
 *   <SafeImage src={imageUrl} alt="..." className="..." />
 */
import React, { useState, useMemo } from 'react';

export const PLACEHOLDER_IMAGE = 'https://bidvex.com/assets/placeholder-ad.jpg';

// Threshold under which a base64 data URL is treated as junk / placeholder
// and swapped for the branded image. 5,000 chars is comfortably above
// 1×1 transparent PNGs (~90 chars), corrupt-thumb fragments (<1KB), and
// stale migration sentinels — but well below any real listing photo.
export const BASE64_MIN_RENDERABLE_LENGTH = 5000;

const _isSafeSrc = (src) => {
  if (!src) return false;
  if (typeof src !== 'string') return false;
  const trimmed = src.trim();
  if (!trimmed) return false;
  if (trimmed.startsWith('data:')) {
    // Allow large base64 strings (real photos) to render directly.
    return trimmed.length >= BASE64_MIN_RENDERABLE_LENGTH;
  }
  return true;
};

export const SafeImage = ({ src, alt = '', onError, decoding, loading, fetchPriority, ...rest }) => {
  const initialSrc = useMemo(() => (_isSafeSrc(src) ? src : PLACEHOLDER_IMAGE), [src]);
  const [currentSrc, setCurrentSrc] = useState(initialSrc);

  // Re-evaluate when the parent updates the src prop (controlled usage).
  React.useEffect(() => {
    setCurrentSrc(_isSafeSrc(src) ? src : PLACEHOLDER_IMAGE);
  }, [src]);

  const handleError = (e) => {
    if (e?.currentTarget?.src !== PLACEHOLDER_IMAGE) {
      setCurrentSrc(PLACEHOLDER_IMAGE);
    }
    if (typeof onError === 'function') {
      try { onError(e); } catch (_) { /* silent */ }
    }
  };

  return (
    <img
      {...rest}
      src={currentSrc}
      alt={alt}
      // iter358 CWV — default `decoding="async"` so image decode never
      // blocks the main thread. `loading` and `fetchPriority` are passed
      // through unchanged (caller decides — usually `lazy` on grids +
      // `eager`/`high` on hero LCP images).
      decoding={decoding || 'async'}
      loading={loading}
      fetchpriority={fetchPriority || undefined}
      onError={handleError}
      data-testid={rest['data-testid'] || 'safe-image'}
    />
  );
};

export default SafeImage;
