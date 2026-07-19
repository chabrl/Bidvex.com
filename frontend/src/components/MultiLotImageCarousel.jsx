/**
 * iter363 — MultiLotImageCarousel.
 *
 * Auto-sliding image carousel for multi-lot auction cards (marketplace
 * "Lots Auction" grid + vehicle multi-lot event cards). Only used where
 * the listing has ≥2 images across its lots — single-image cards fall
 * back to the plain SafeImage rendering by design.
 *
 * Requirements:
 *   - Up to 10 images (defensively capped even if caller passes more).
 *   - Advances every 2.5s while the card is visible in the viewport
 *     (IntersectionObserver pauses the interval when scrolled offscreen
 *     to save battery / CPU on long grids).
 *   - No CLS: uses the same `.grid-card-image` container with a fixed
 *     4:3 aspect-ratio; images are absolutely positioned with fade
 *     transitions so height never shifts.
 *   - Progress dots at the bottom for user affordance.
 *   - Respects `prefers-reduced-motion` — falls back to static first image.
 *
 * Props:
 *   images     : string[]              — URLs (S3 or /static/ paths)
 *   alt        : string
 *   intervalMs : number  (default 2500)
 *   className  : string                — passed to inner <img> tags
 *   testId     : string                — prefix for data-testid attrs
 */
import React, { useEffect, useRef, useState } from 'react';
import SafeImage from './SafeImage';

const MAX_IMAGES = 10;

export default function MultiLotImageCarousel({
  images = [],
  alt = '',
  intervalMs = 2500,
  className = '',
  testId = 'multi-lot-carousel',
}) {
  // Dedupe + cap to MAX_IMAGES.
  const uniqueImages = React.useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const url of images) {
      if (!url || typeof url !== 'string') continue;
      if (seen.has(url)) continue;
      seen.add(url);
      out.push(url);
      if (out.length >= MAX_IMAGES) break;
    }
    return out;
  }, [images]);

  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const containerRef = useRef(null);
  const prefersReducedMotion = useRef(
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  // IntersectionObserver — pause when card scrolls offscreen.
  useEffect(() => {
    if (uniqueImages.length <= 1) return; // nothing to animate
    if (!containerRef.current) return;
    if (typeof IntersectionObserver === 'undefined') return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) setVisible(entry.isIntersecting);
      },
      { threshold: 0.1 },
    );
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, [uniqueImages.length]);

  // Interval — advance only when visible + not motion-reduced.
  useEffect(() => {
    if (uniqueImages.length <= 1) return;
    if (!visible) return;
    if (prefersReducedMotion.current) return;
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % uniqueImages.length);
    }, Math.max(1000, intervalMs));
    return () => clearInterval(timer);
  }, [uniqueImages.length, visible, intervalMs]);

  // Single-image fallback → static rendering.
  if (uniqueImages.length === 0) return null;
  if (uniqueImages.length === 1) {
    return (
      <SafeImage
        src={uniqueImages[0]}
        alt={alt}
        width={400}
        height={300}
        loading="lazy"
        className={className}
        data-testid={`${testId}-single`}
      />
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full"
      data-testid={testId}
      data-active-index={index}
    >
      {uniqueImages.map((src, i) => (
        <div
          key={src + i}
          className={`absolute inset-0 transition-opacity duration-500 ${
            i === index ? 'opacity-100' : 'opacity-0 pointer-events-none'
          }`}
          aria-hidden={i !== index}
        >
          <SafeImage
            src={src}
            alt={alt}
            width={400}
            height={300}
            loading={i === 0 ? 'eager' : 'lazy'}
            className={className}
          />
        </div>
      ))}
      {/* Progress dots */}
      <div
        className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5"
        data-testid={`${testId}-dots`}
      >
        {uniqueImages.map((_, i) => (
          <span
            key={i}
            className={`h-1.5 rounded-full transition-all ${
              i === index ? 'bg-white w-4' : 'bg-white/60 w-1.5'
            } shadow-md`}
          />
        ))}
      </div>
    </div>
  );
}
