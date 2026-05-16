/**
 * Phase 5 Hotfix — SafeImage
 *
 * Drop-in replacement for `<img>` that guarantees a renderable image in
 * all three failure modes flagged by users:
 *
 *   1. `src` is null, undefined, or an empty string
 *   2. `src` is a base64 data URL (e.g. `data:image/png;base64,...`)
 *      — these often come from un-migrated legacy listings and may render
 *      as 1×1 transparent pixels, leaving the marketplace card visually
 *      empty.
 *   3. The underlying `<img>` fires `onError` (network failure, 404,
 *      corrupt file, blocked cross-origin, etc.)
 *
 * All three cases swap to the branded BidVex placeholder hosted at
 * `https://bidvex.com/assets/placeholder-ad.jpg` (and the equivalent
 * preview-domain path) so the UI never shows a broken / invisible image.
 *
 * Usage:
 *   <SafeImage src={imageUrl} alt="..." className="..." />
 */
import React, { useState, useMemo } from 'react';

export const PLACEHOLDER_IMAGE = 'https://bidvex.com/assets/placeholder-ad.jpg';

const _isSafeSrc = (src) => {
  if (!src) return false;
  if (typeof src !== 'string') return false;
  const trimmed = src.trim();
  if (!trimmed) return false;
  if (trimmed.startsWith('data:')) return false; // base64 / data URLs
  return true;
};

export const SafeImage = ({ src, alt = '', onError, ...rest }) => {
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
      onError={handleError}
      data-testid={rest['data-testid'] || 'safe-image'}
    />
  );
};

export default SafeImage;
