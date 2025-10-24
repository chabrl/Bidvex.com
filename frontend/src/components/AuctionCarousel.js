import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useEmblaCarousel from 'embla-carousel-react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import WatchlistButton from './WatchlistButton';
import Countdown from 'react-countdown';
import { Clock } from 'lucide-react';

const AuctionCarousel = ({ title, items, type = 'auction' }) => {
  const navigate = useNavigate();
  const [emblaRef, emblaApi] = useEmblaCarousel({
    loop: false,
    align: 'start',
    slidesToScroll: 1,
    breakpoints: {
      '(min-width: 640px)': { slidesToScroll: 2 },
      '(min-width: 1024px)': { slidesToScroll: 3 },
    },
  });

  const [prevBtnEnabled, setPrevBtnEnabled] = useState(false);
  const [nextBtnEnabled, setNextBtnEnabled] = useState(false);

  const scrollPrev = useCallback(() => {
    if (emblaApi) emblaApi.scrollPrev();
  }, [emblaApi]);

  const scrollNext = useCallback(() => {
    if (emblaApi) emblaApi.scrollNext();
  }, [emblaApi]);

  const onSelect = useCallback(() => {
    if (!emblaApi) return;
    setPrevBtnEnabled(emblaApi.canScrollPrev());
    setNextBtnEnabled(emblaApi.canScrollNext());
  }, [emblaApi]);

  useEffect(() => {
    if (!emblaApi) return;
    onSelect();
    emblaApi.on('select', onSelect);
    emblaApi.on('reInit', onSelect);
  }, [emblaApi, onSelect]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowLeft') scrollPrev();
      if (e.key === 'ArrowRight') scrollNext();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [scrollPrev, scrollNext]);

  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="relative">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl sm:text-3xl font-bold">{title}</h2>
        <div className="hidden md:flex gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={scrollPrev}
            disabled={!prevBtnEnabled}
            className="rounded-full"
            aria-label="Previous"
          >
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={scrollNext}
            disabled={!nextBtnEnabled}
            className="rounded-full"
            aria-label="Next"
          >
            <ChevronRight className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* Carousel */}
      <div className="overflow-hidden" ref={emblaRef}>
        <div className="flex gap-4 touch-pan-y">
          {items.map((item, index) => (
            <div
              key={item.id || index}
              className="flex-none w-full sm:w-[calc(50%-0.5rem)] lg:w-[calc(33.333%-0.667rem)] min-w-0"
            >
              {type === 'auction' ? (
                <AuctionCard item={item} onClick={() => navigate(`/listing/${item.id}`)} />
              ) : (
                <SellerCard item={item} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Mobile Navigation Dots */}
      <div className="flex md:hidden justify-center gap-2 mt-6">
        {Array.from({ length: Math.ceil(items.length / 1) }).map((_, index) => (
          <button
            key={index}
            className={`w-2 h-2 rounded-full transition-all ${
              index === 0 ? 'bg-primary w-6' : 'bg-gray-300 dark:bg-gray-600'
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
};

const AuctionCard = ({ item, onClick }) => {
  const auctionEndDate = item.auction_end_date ? new Date(item.auction_end_date) : null;
  const isEnded = auctionEndDate && new Date() > auctionEndDate;
  const timeLeft = auctionEndDate ? auctionEndDate - new Date() : 0;
  const isUrgent = timeLeft > 0 && timeLeft < 3600000; // Less than 1 hour

  return (
    <Card 
      className="group overflow-hidden hover:shadow-xl transition-all duration-300 cursor-pointer h-full"
      onClick={onClick}
    >
      {/* Image */}
      <div className="relative h-56 bg-gray-100 overflow-hidden">
        {item.images?.[0] ? (
          <img 
            src={item.images[0]} 
            alt={item.title} 
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-6xl">📦</div>
        )}
        
        {/* Watchlist Button */}
        <div 
          className="absolute top-3 left-3 z-10"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-white dark:bg-gray-900 rounded-full p-2 shadow-lg">
            <WatchlistButton listingId={item.id} size="small" />
          </div>
        </div>

        {/* Countdown Timer */}
        {auctionEndDate && !isEnded && (
          <div className="absolute top-3 right-3 z-10">
            <Badge className={`${isUrgent ? 'bg-red-600 animate-pulse' : 'bg-blue-600'} text-white border-0 shadow-lg`}>
              <Clock className="h-3 w-3 mr-1" />
              <Countdown
                date={auctionEndDate}
                renderer={({ days, hours, minutes }) => (
                  <span className="font-bold text-xs">
                    {days > 0 && `${days}d `}{hours}h {minutes}m
                  </span>
                )}
              />
            </Badge>
          </div>
        )}

        {/* Status Badges */}
        {item.is_promoted && (
          <div className="absolute bottom-3 right-3">
            <Badge className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white border-0">
              Featured
            </Badge>
          </div>
        )}
        {isEnded && (
          <div className="absolute bottom-3 left-3">
            <Badge variant="destructive">Ended</Badge>
          </div>
        )}
      </div>

      {/* Content */}
      <CardContent className="p-4 space-y-3">
        <h3 className="font-bold text-lg line-clamp-2 group-hover:text-primary transition-colors">
          {item.title}
        </h3>
        
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground uppercase">Current Bid</p>
          <p className="text-2xl font-bold gradient-text">
            ${item.current_price?.toFixed(2) || item.starting_price?.toFixed(2)}
          </p>
        </div>

        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{item.bid_count || 0} bids</span>
          {item.category && <Badge variant="outline" className="text-xs">{item.category}</Badge>}
        </div>
      </CardContent>
    </Card>
  );
};

const SellerCard = ({ item }) => {
  return (
    <Card className="overflow-hidden hover:shadow-xl transition-all duration-300 h-full">
      <CardContent className="p-6 text-center space-y-4">
        <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center">
          <span className="text-3xl font-bold text-white">
            {item.seller_name?.charAt(0) || 'S'}
          </span>
        </div>
        <div>
          <h3 className="font-bold text-lg mb-1">{item.seller_name || 'Seller'}</h3>
          <p className="text-sm text-muted-foreground">{item.count} items sold</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground uppercase">Total Sales</p>
          <p className="text-xl font-bold gradient-text">${item.total_sales?.toFixed(2)}</p>
        </div>
      </CardContent>
    </Card>
  );
};

export default AuctionCarousel;
