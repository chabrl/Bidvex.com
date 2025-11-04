import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const HomepageBanner = () => {
  const navigate = useNavigate();
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);

  const banners = [
    {
      id: 1,
      title: "Start Bidding Today",
      subtitle: "Discover rare finds and exclusive deals in our trusted marketplace",
      image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1200&h=400&fit=crop",
      cta1: { text: "Browse Auctions", action: () => navigate('/marketplace') },
      cta2: { text: "How It Works", action: () => navigate('/how-it-works'), outline: true }
    },
    {
      id: 2,
      title: "Sell Your Items",
      subtitle: "Reach thousands of buyers and get the best price for your items",
      image: "https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=1200&h=400&fit=crop",
      cta1: { text: "Create Listing", action: () => navigate('/create-listing') },
      cta2: { text: "Learn More", action: () => navigate('/how-it-works'), outline: true }
    },
    {
      id: 3,
      title: "Join as a Business",
      subtitle: "Access exclusive features and grow your auction business with BidVex",
      image: "https://images.unsplash.com/photo-1560472355-536de3962603?w=1200&h=400&fit=crop",
      cta1: { text: "Register Now", action: () => navigate('/auth') },
      cta2: { text: "Contact Sales", action: () => navigate('/messages'), outline: true }
    }
  ];

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % banners.length);
  }, [banners.length]);

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + banners.length) % banners.length);
  }, [banners.length]);

  const goToSlide = (index) => {
    setCurrentSlide(index);
    setIsAutoPlaying(false);
  };

  // Auto-slide effect
  useEffect(() => {
    if (!isAutoPlaying) return;
    
    const interval = setInterval(() => {
      nextSlide();
    }, 5000); // Change slide every 5 seconds

    return () => clearInterval(interval);
  }, [isAutoPlaying, nextSlide]);

  // Handle touch/swipe for mobile
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);

  const minSwipeDistance = 50;

  const onTouchStart = (e) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const onTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const onTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > minSwipeDistance;
    const isRightSwipe = distance < -minSwipeDistance;

    if (isLeftSwipe) {
      nextSlide();
      setIsAutoPlaying(false);
    } else if (isRightSwipe) {
      prevSlide();
      setIsAutoPlaying(false);
    }
  };

  return (
    <div className="relative w-full h-[400px] md:h-[500px] overflow-hidden rounded-2xl shadow-2xl mb-12">
      {/* Banner Slides */}
      <div
        className="relative w-full h-full"
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={currentSlide}
            initial={{ opacity: 0, x: 100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -100 }}
            transition={{ duration: 0.5 }}
            className="absolute inset-0"
          >
            {/* Background Image with Overlay */}
            <div className="absolute inset-0">
              <img
                src={banners[currentSlide].image}
                alt={banners[currentSlide].title}
                className="w-full h-full object-cover"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/50 to-transparent"></div>
            </div>

            {/* Content */}
            <div className="relative z-10 h-full flex items-center px-8 md:px-16 max-w-7xl mx-auto">
              <div className="max-w-2xl space-y-6">
                <motion.h2
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="text-4xl md:text-6xl font-bold text-white leading-tight"
                >
                  {banners[currentSlide].title}
                </motion.h2>
                
                <motion.p
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="text-lg md:text-xl text-white/90"
                >
                  {banners[currentSlide].subtitle}
                </motion.p>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  className="flex flex-col sm:flex-row gap-4"
                >
                  <Button
                    onClick={banners[currentSlide].cta1.action}
                    className="gradient-button text-white border-0 text-lg px-8 py-6 rounded-full shadow-lg hover:shadow-xl"
                  >
                    {banners[currentSlide].cta1.text}
                  </Button>
                  
                  {banners[currentSlide].cta2 && (
                    <Button
                      onClick={banners[currentSlide].cta2.action}
                      variant="outline"
                      className="text-lg px-8 py-6 rounded-full border-2 border-white text-white hover:bg-white hover:text-primary shadow-lg"
                    >
                      {banners[currentSlide].cta2.text}
                    </Button>
                  )}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation Arrows - Desktop */}
      <div className="hidden md:flex absolute top-1/2 -translate-y-1/2 left-4 right-4 justify-between pointer-events-none">
        <Button
          onClick={prevSlide}
          variant="ghost"
          size="icon"
          className="pointer-events-auto w-12 h-12 rounded-full bg-white/20 hover:bg-white/40 backdrop-blur-sm text-white border border-white/30"
        >
          <ChevronLeft className="h-6 w-6" />
        </Button>
        <Button
          onClick={nextSlide}
          variant="ghost"
          size="icon"
          className="pointer-events-auto w-12 h-12 rounded-full bg-white/20 hover:bg-white/40 backdrop-blur-sm text-white border border-white/30"
        >
          <ChevronRight className="h-6 w-6" />
        </Button>
      </div>

      {/* Dots Indicator */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex gap-2">
        {banners.map((_, index) => (
          <button
            key={index}
            onClick={() => goToSlide(index)}
            className={`w-3 h-3 rounded-full transition-all ${
              index === currentSlide
                ? 'bg-white w-8'
                : 'bg-white/50 hover:bg-white/75'
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>

      {/* Auto-play pause button */}
      <button
        onClick={() => setIsAutoPlaying(!isAutoPlaying)}
        className="absolute top-4 right-4 bg-white/20 hover:bg-white/40 backdrop-blur-sm text-white px-3 py-1 rounded-full text-sm border border-white/30 transition-colors"
      >
        {isAutoPlaying ? '⏸ Pause' : '▶ Play'}
      </button>
    </div>
  );
};

export default HomepageBanner;
