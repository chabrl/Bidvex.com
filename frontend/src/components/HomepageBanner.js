import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const HomepageBanner = () => {
  const navigate = useNavigate();
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);

  // Default banners (fallback if no banners from API)
  const defaultBanners = [
    {
      id: 1,
      title: "Discover. Bid. Win.",
      subtitle: "Experience the thrill of live auctions. Join thousands of bidders competing for unique items at unbeatable prices.",
      image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1200&h=600&fit=crop",
      cta1: { text: "Browse Auctions", action: () => navigate('/marketplace') },
      cta2: { text: "How It Works", action: () => navigate('/how-it-works'), outline: true },
      gradient: "from-blue-600 via-blue-500 to-cyan-500"
    },
    {
      id: 2,
      title: "Start Bidding Today",
      subtitle: "Discover rare finds and exclusive deals in our trusted marketplace",
      image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1200&h=400&fit=crop",
      cta1: { text: "Browse Auctions", action: () => navigate('/marketplace') },
      cta2: { text: "How It Works", action: () => navigate('/how-it-works'), outline: true },
      gradient: "from-blue-600 via-blue-500 to-cyan-500"
    },
    {
      id: 3,
      title: "Sell Your Items",
      subtitle: "Reach thousands of buyers and get the best price for your items",
      image: "https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=1200&h=400&fit=crop",
      cta1: { text: "Create Listing", action: () => navigate('/create-listing') },
      cta2: { text: "Learn More", action: () => navigate('/how-it-works'), outline: true },
      gradient: "from-purple-600 via-purple-500 to-pink-500"
    }
  ];

  // Fetch banners from API
  useEffect(() => {
    const fetchBanners = async () => {
      try {
        // Add cache-busting to ensure fresh data
        const response = await axios.get(`${API}/banners/active?t=${Date.now()}`, {
          headers: { 'Cache-Control': 'no-cache' }
        });
        if (response.data.banners && response.data.banners.length > 0) {
          // Transform API banners to component format
          const transformedBanners = response.data.banners
            .filter(b => b.is_active)
            .sort((a, b) => (b.priority || 0) - (a.priority || 0))
            .map(banner => ({
              id: banner.id,
              title: banner.title,
              subtitle: banner.subtitle || banner.description || "",
              image: banner.image_url,
              cta1: { 
                text: banner.cta_text || "View More", 
                action: () => {
                  if (banner.cta_url) {
                    if (banner.cta_url.startsWith('http')) {
                      window.location.href = banner.cta_url;
                    } else {
                      navigate(banner.cta_url);
                    }
                  }
                }
              },
              cta2: banner.cta2_text ? { 
                text: banner.cta2_text, 
                action: () => {
                  if (banner.cta2_url) {
                    if (banner.cta2_url.startsWith('http')) {
                      window.location.href = banner.cta2_url;
                    } else {
                      navigate(banner.cta2_url);
                    }
                  }
                },
                outline: true 
              } : null,
              gradient: banner.gradient || "from-blue-600 via-blue-500 to-cyan-500"
            }));
          
          setBanners(transformedBanners);
        } else {
          setBanners(defaultBanners);
        }
      } catch (error) {
        console.error('Failed to fetch banners:', error);
        setBanners(defaultBanners);
      } finally {
        setLoading(false);
      }
    };

    fetchBanners();
  }, [navigate]);

  const activeBanners = banners.length > 0 ? banners : defaultBanners;

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % activeBanners.length);
  }, [activeBanners.length]);

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + activeBanners.length) % activeBanners.length);
  }, [activeBanners.length]);

  const goToSlide = (index) => {
    setCurrentSlide(index);
    setIsAutoPlaying(false);
  };

  // Auto-slide effect
  useEffect(() => {
    if (!isAutoPlaying || loading) return;
    
    const interval = setInterval(() => {
      nextSlide();
    }, 5000); // Change slide every 5 seconds

    return () => clearInterval(interval);
  }, [isAutoPlaying, nextSlide, loading]);

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

  if (loading) {
    return (
      <div className="relative w-full h-[400px] md:h-[500px] overflow-hidden rounded-2xl shadow-2xl mb-12 bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500 flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

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
            {/* Background with gradient overlay */}
            <div className="absolute inset-0">
              {activeBanners[currentSlide].image ? (
                <>
                  <img
                    src={activeBanners[currentSlide].image}
                    alt={activeBanners[currentSlide].title}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div className={`absolute inset-0 bg-gradient-to-r ${activeBanners[currentSlide].gradient || 'from-blue-600/80 via-blue-500/70 to-cyan-500/60'}`}></div>
                </>
              ) : (
                <div className={`absolute inset-0 bg-gradient-to-r ${activeBanners[currentSlide].gradient || 'from-blue-600 via-blue-500 to-cyan-500'}`}></div>
              )}
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
                  {activeBanners[currentSlide].title}
                </motion.h2>
                
                <motion.p
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="text-lg md:text-xl text-white/90"
                >
                  {activeBanners[currentSlide].subtitle}
                </motion.p>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  className="flex flex-col sm:flex-row gap-4"
                >
                  <Button
                    onClick={activeBanners[currentSlide].cta1.action}
                    className="bg-white text-blue-900 border-0 text-lg px-8 py-6 rounded-full shadow-lg hover:shadow-xl hover:bg-blue-50 hover:scale-105 transition-all duration-300"
                  >
                    {activeBanners[currentSlide].cta1.text}
                  </Button>
                  
                  {activeBanners[currentSlide].cta2 && (
                    <Button
                      onClick={activeBanners[currentSlide].cta2.action}
                      variant="outline"
                      className="text-lg px-8 py-6 rounded-full border-2 border-white bg-white/10 backdrop-blur-sm text-white hover:bg-white hover:text-blue-900 shadow-lg transition-all duration-300"
                    >
                      {activeBanners[currentSlide].cta2.text}
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
        {activeBanners.map((_, index) => (
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
