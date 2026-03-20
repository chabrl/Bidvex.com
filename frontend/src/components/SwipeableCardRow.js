import React, { useCallback, useEffect, useState } from 'react';
import useEmblaCarousel from 'embla-carousel-react';

/**
 * SwipeableCardRow — Mobile swipeable carousel, desktop grid.
 *
 * Props:
 *   items       – array of data objects
 *   renderCard  – (item, index) => JSX card element
 *   gridCols    – Tailwind grid classes for sm+ (e.g. "sm:grid-cols-2 lg:grid-cols-4")
 *   mobileWidth – Tailwind width class for each slide on mobile (default: "w-[80vw]")
 *   gap         – gap class applied to both carousel and grid (default: "gap-4 sm:gap-6")
 *   className   – extra wrapper classes
 */
const SwipeableCardRow = ({
  items,
  renderCard,
  gridCols = 'sm:grid-cols-2 lg:grid-cols-4',
  mobileWidth = 'w-[80vw]',
  gap = 'gap-4 sm:gap-6',
  className = '',
}) => {
  const [emblaRef, emblaApi] = useEmblaCarousel({
    loop: false,
    align: 'start',
    containScroll: 'trimSnaps',
    dragFree: false,
  });

  const [activeIndex, setActiveIndex] = useState(0);
  const [scrollSnaps, setScrollSnaps] = useState([]);

  const onSelect = useCallback(() => {
    if (!emblaApi) return;
    setActiveIndex(emblaApi.selectedScrollSnap());
  }, [emblaApi]);

  useEffect(() => {
    if (!emblaApi) return;
    setScrollSnaps(emblaApi.scrollSnapList());
    emblaApi.on('select', onSelect);
    emblaApi.on('reInit', () => {
      setScrollSnaps(emblaApi.scrollSnapList());
      onSelect();
    });
    onSelect();
  }, [emblaApi, onSelect]);

  if (!items || items.length === 0) return null;

  return (
    <div className={className} data-testid="swipeable-card-row">
      {/* ===== MOBILE CAROUSEL (visible below sm) ===== */}
      <div className="sm:hidden">
        <div className="overflow-hidden" ref={emblaRef}>
          <div className="flex gap-3 touch-pan-y">
            {items.map((item, index) => (
              <div
                key={item.id || index}
                className={`flex-none ${mobileWidth} min-w-0`}
              >
                {renderCard(item, index)}
              </div>
            ))}
          </div>
        </div>

        {/* Dot indicators */}
        {scrollSnaps.length > 1 && (
          <div className="flex justify-center gap-1.5 mt-4" data-testid="carousel-dots">
            {scrollSnaps.map((_, idx) => (
              <button
                key={idx}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  idx === activeIndex
                    ? 'bg-cyan-500 w-6'
                    : 'bg-slate-300 dark:bg-slate-600 w-1.5'
                }`}
                onClick={() => emblaApi?.scrollTo(idx)}
                aria-label={`Go to slide ${idx + 1}`}
              />
            ))}
          </div>
        )}
      </div>

      {/* ===== DESKTOP GRID (visible sm and up) ===== */}
      <div className={`hidden sm:grid ${gridCols} ${gap}`}>
        {items.map((item, index) => renderCard(item, index))}
      </div>
    </div>
  );
};

export default SwipeableCardRow;
