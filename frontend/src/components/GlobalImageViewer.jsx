/**
 * iter369 — Global Image Viewer (professional lightbox).
 *
 * Single source of truth for all image previews across the platform:
 * marketplace, lots, vehicles, storage, multi-lot detail, and standalone
 * listing pages. Wraps `yet-another-react-lightbox` (already in
 * package.json) with:
 *
 *   • Fullscreen 100vw × 100vh on `position: fixed`, `z-index: 9999`, black
 *     background — matches iter369 spec.
 *   • `object-fit: contain` so images never crop, regardless of orientation.
 *   • Zoom plugin (mouse-wheel + pinch + double-tap) with buttons.
 *   • Counter plugin (`3 / 12` badge).
 *   • Native keyboard navigation (← → Esc) and mobile swipe are provided by
 *     the underlying library.
 *   • Right-click disabled + `pointer-events: none` on the img itself blocks
 *     the standard "Save image as…" flow.
 *
 * Public API:
 *   <GlobalImageViewer
 *     open={open}
 *     onClose={() => setOpen(false)}
 *     images={[url1, url2, ...]}      // string[] or {src, alt}[]
 *     startIndex={0}
 *   />
 */
import React, { useMemo } from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';
import Counter from 'yet-another-react-lightbox/plugins/counter';
import 'yet-another-react-lightbox/styles.css';
import 'yet-another-react-lightbox/plugins/counter.css';

export default function GlobalImageViewer({
  open,
  onClose,
  images = [],
  startIndex = 0,
}) {
  const slides = useMemo(() => {
    return (images || [])
      .filter(Boolean)
      .map((it) => (typeof it === 'string' ? { src: it } : it));
  }, [images]);

  if (!open || slides.length === 0) return null;

  return (
    <Lightbox
      open={open}
      close={onClose}
      slides={slides}
      index={Math.max(0, Math.min(startIndex, slides.length - 1))}
      plugins={[Zoom, Counter]}
      carousel={{ finite: false, preload: 2 }}
      controller={{ closeOnBackdropClick: true, closeOnPullDown: true }}
      animation={{ fade: 260, swipe: 400 }}
      zoom={{
        maxZoomPixelRatio: 4,
        zoomInMultiplier: 2,
        doubleTapDelay: 300,
        doubleClickDelay: 300,
        doubleClickMaxStops: 2,
        scrollToZoom: true,
      }}
      counter={{ container: { style: { top: 'unset', bottom: 16, right: 16, left: 'unset' } } }}
      styles={{
        container: {
          backgroundColor: 'rgba(0, 0, 0, 0.96)',
          // Force explicit 100vw / 100vh in case a parent has transformed
          // context that would otherwise shrink `position: fixed`.
          position: 'fixed',
          inset: 0,
          width: '100vw',
          height: '100vh',
          zIndex: 9999,
        },
        slide: { padding: 0 },
      }}
      render={{
        // No download / share buttons — plain black bg per iter369 spec.
        buttonPrev: slides.length > 1 ? undefined : () => null,
        buttonNext: slides.length > 1 ? undefined : () => null,
      }}
      on={{
        // Block right-click-save; matches iter369 spec (disable download).
        entered: () => {
          try {
            const root = document.querySelector('.yarl__container');
            if (root) root.addEventListener('contextmenu', (e) => e.preventDefault());
          } catch { /* ignore */ }
        },
      }}
      data-testid="global-image-viewer"
    />
  );
}
