import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from './ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Convert hex to rgba
const hexToRgba = (hex, alpha) => {
  if (!hex || hex.length < 7) return `rgba(0, 0, 0, ${alpha})`;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

// Default banner styling
const DEFAULT_STYLING = {
  title_color: '#FFFFFF',
  subtitle_color: '#FFFFFF',
  button_color: '#FFFFFF',
  button_text_color: '#000000',
  text_color: '#FFFFFF',
  font_family: 'Inter',
  title_font_size: '48px',
  subtitle_font_size: '18px',
  overlay_color: '#000000',
  overlay_opacity: 0.4,
};

const HomepageBanner = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const currentLang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);

  // Default banners (fallback if no banners from API)
  const defaultBanners = [
    {
      id: 'default-1',
      title: "Discover. Bid. Win.",
      subtitle: "Experience the thrill of live auctions. Join thousands of bidders competing for unique items at unbeatable prices.",
      image_url: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1920&h=600&fit=crop",
      cta_text: "Browse Auctions",
      cta_link: "/marketplace",
      ...DEFAULT_STYLING,
    },
    {
      id: 'default-2',
      title: "Start Bidding Today",
      subtitle: "Discover rare finds and exclusive deals in our trusted marketplace",
      image_url: "https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=1920&h=600&fit=crop",
      cta_text: "Explore Now",
      cta_link: "/marketplace",
      ...DEFAULT_STYLING,
    },
  ];

  // Fetch banners from API
  useEffect(() => {
    const fetchBanners = async () => {
      try {
        const response = await axios.get(`${API}/banners/active?t=${Date.now()}`, {
          headers: { 'Cache-Control': 'no-cache' }
        });
        
        if (response.data?.hero_banners && response.data.hero_banners.length > 0) {
          // Use hero_banners with full styling and bilingual support
          const transformedBanners = response.data.hero_banners
            .sort((a, b) => (a.order || 0) - (b.order || 0))
            .map(banner => ({
              id: banner.id,
              // Bilingual content fields
              title_en: banner.title_en || banner.title || '',
              title_fr: banner.title_fr || '',
              subtitle_en: banner.subtitle_en || banner.subtitle || '',
              subtitle_fr: banner.subtitle_fr || '',
              cta_text_en: banner.cta_text_en || banner.cta_text || 'Learn More',
              cta_text_fr: banner.cta_text_fr || 'En savoir plus',
              // Legacy fields
              title: banner.title || '',
              subtitle: banner.subtitle || '',
              cta_text: banner.cta_text || 'Learn More',
              // Images
              image_url: banner.image_desktop || banner.image_url || banner.image_mobile,
              image_mobile: banner.image_mobile,
              cta_link: banner.cta_link || '/marketplace',
              // Styling fields - all independent
              title_color: banner.title_color || DEFAULT_STYLING.title_color,
              subtitle_color: banner.subtitle_color || DEFAULT_STYLING.subtitle_color,
              button_color: banner.button_color || DEFAULT_STYLING.button_color,
              button_text_color: banner.button_text_color || DEFAULT_STYLING.button_text_color,
              text_color: banner.text_color || DEFAULT_STYLING.text_color,
              font_family: banner.font_family || DEFAULT_STYLING.font_family,
              title_font_size: banner.title_font_size || DEFAULT_STYLING.title_font_size,
              subtitle_font_size: banner.subtitle_font_size || DEFAULT_STYLING.subtitle_font_size,
              overlay_color: banner.overlay_color || DEFAULT_STYLING.overlay_color,
              overlay_opacity: banner.overlay_opacity ?? DEFAULT_STYLING.overlay_opacity,
            }));
          
          setBanners(transformedBanners);
        } else if (response.data?.banners && response.data.banners.length > 0) {
          // Fallback to regular banners
          const transformedBanners = response.data.banners
            .filter(b => b.is_active)
            .sort((a, b) => (b.priority || 0) - (a.priority || 0))
            .map(banner => ({
              id: banner.id,
              title: banner.title || '',
              subtitle: banner.subtitle || banner.description || '',
              image_url: banner.image_url,
              cta_text: banner.cta_text || 'View More',
              cta_link: banner.cta_url || '/marketplace',
              ...DEFAULT_STYLING,
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
    if (!isAutoPlaying || loading || activeBanners.length <= 1) return;
    
    const interval = setInterval(() => {
      nextSlide();
    }, 5000);

    return () => clearInterval(interval);
  }, [isAutoPlaying, nextSlide, loading, activeBanners.length]);

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

  const handleCtaClick = (banner) => {
    if (banner.cta_link) {
      if (banner.cta_link.startsWith('http')) {
        window.location.href = banner.cta_link;
      } else {
        navigate(banner.cta_link);
      }
    }
  };

  // Get responsive font sizes
  const getResponsiveFontSize = (size, mobile = false) => {
    if (!size) return mobile ? '28px' : '48px';
    const numSize = parseInt(size);
    if (mobile) {
      // Scale down for mobile
      return `${Math.max(20, numSize * 0.6)}px`;
    }
    return size;
  };

  if (loading) {
    return (
      <div className="relative w-full h-[400px] md:h-[500px] overflow-hidden bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500 flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  const currentBanner = activeBanners[currentSlide];
  const overlayRgba = hexToRgba(currentBanner.overlay_color, currentBanner.overlay_opacity);
  
  // Get bilingual content based on current language
  const displayTitle = currentLang === 'fr' 
    ? (currentBanner.title_fr || currentBanner.title_en || currentBanner.title)
    : (currentBanner.title_en || currentBanner.title);
  const displaySubtitle = currentLang === 'fr'
    ? (currentBanner.subtitle_fr || currentBanner.subtitle_en || currentBanner.subtitle)
    : (currentBanner.subtitle_en || currentBanner.subtitle);
  const displayCtaText = currentLang === 'fr'
    ? (currentBanner.cta_text_fr || currentBanner.cta_text_en || currentBanner.cta_text)
    : (currentBanner.cta_text_en || currentBanner.cta_text);

  return (
    <div className="relative w-full h-[400px] md:h-[500px] lg:h-[600px] overflow-hidden">
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
            {/* Background image */}
            <div className="absolute inset-0">
              {currentBanner.image_url ? (
                <>
                  {/* Desktop image */}
                  <img
                    src={currentBanner.image_url}
                    alt={currentBanner.title}
                    className="hidden md:block w-full h-full object-cover"
                    loading="lazy"
                  />
                  {/* Mobile image (use mobile-specific or fall back to desktop) */}
                  <img
                    src={currentBanner.image_mobile || currentBanner.image_url}
                    alt={currentBanner.title}
                    className="md:hidden w-full h-full object-cover"
                    loading="lazy"
                  />
                </>
              ) : (
                <div className="absolute inset-0 bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500" />
              )}
              
              {/* Dynamic Overlay */}
              <div 
                className="absolute inset-0"
                style={{ backgroundColor: overlayRgba }}
              />
            </div>

            {/* Content */}
            <div className="relative z-10 h-full flex items-center px-6 md:px-12 lg:px-16 max-w-7xl mx-auto">
              <div className="max-w-2xl space-y-4 md:space-y-6">
                <motion.h1
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="leading-tight"
                  style={{
                    fontFamily: currentBanner.font_family,
                    fontWeight: 'bold',
                  }}
                >
                  {/* Desktop font size */}
                  <span 
                    className="hidden md:inline" 
                    style={{ 
                      fontSize: currentBanner.title_font_size,
                      color: currentBanner.title_color,
                    }}
                  >
                    {displayTitle}
                  </span>
                  {/* Mobile font size */}
                  <span 
                    className="md:hidden"
                    style={{ 
                      fontSize: getResponsiveFontSize(currentBanner.title_font_size, true),
                      color: currentBanner.title_color,
                    }}
                  >
                    {displayTitle}
                  </span>
                </motion.h1>
                
                <motion.p
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  style={{
                    fontFamily: currentBanner.font_family,
                    opacity: 0.9,
                  }}
                  className="md:text-lg"
                >
                  {/* Desktop subtitle */}
                  <span 
                    className="hidden md:inline" 
                    style={{ 
                      fontSize: currentBanner.subtitle_font_size,
                      color: currentBanner.subtitle_color,
                    }}
                  >
                    {displaySubtitle}
                  </span>
                  {/* Mobile subtitle */}
                  <span 
                    className="md:hidden"
                    style={{
                      fontSize: getResponsiveFontSize(currentBanner.subtitle_font_size, true),
                      color: currentBanner.subtitle_color,
                    }}
                  >
                    {displaySubtitle}
                  </span>
                </motion.p>

                {displayCtaText && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                  >
                    <Button
                      onClick={() => handleCtaClick(currentBanner)}
                      className="text-base md:text-lg px-6 md:px-8 py-4 md:py-6 rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300"
                      style={{
                        backgroundColor: currentBanner.button_color,
                        color: currentBanner.button_text_color,
                      }}
                    >
                      {displayCtaText}
                    </Button>
                  </motion.div>
                )}
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation Arrows - Desktop only, show only if multiple banners */}
      {activeBanners.length > 1 && (
        <div className="hidden md:flex absolute top-1/2 -translate-y-1/2 left-4 right-4 justify-between pointer-events-none">
          <Button
            onClick={prevSlide}
            variant="ghost"
            size="icon"
            className="pointer-events-auto w-12 h-12 rounded-full bg-white/20 hover:bg-white/40 backdrop-blur-sm border border-white/30"
            style={{ color: currentBanner.text_color }}
          >
            <ChevronLeft className="h-6 w-6" />
          </Button>
          <Button
            onClick={nextSlide}
            variant="ghost"
            size="icon"
            className="pointer-events-auto w-12 h-12 rounded-full bg-white/20 hover:bg-white/40 backdrop-blur-sm border border-white/30"
            style={{ color: currentBanner.text_color }}
          >
            <ChevronRight className="h-6 w-6" />
          </Button>
        </div>
      )}

      {/* Dots Indicator - show only if multiple banners */}
      {activeBanners.length > 1 && (
        <div className="absolute bottom-4 md:bottom-6 left-1/2 -translate-x-1/2 flex gap-2">
          {activeBanners.map((_, index) => (
            <button
              key={index}
              onClick={() => goToSlide(index)}
              className={`h-2 md:h-3 rounded-full transition-all ${
                index === currentSlide
                  ? 'w-6 md:w-8'
                  : 'w-2 md:w-3 hover:opacity-100'
              }`}
              style={{
                backgroundColor: currentBanner.text_color,
                opacity: index === currentSlide ? 1 : 0.5,
              }}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      )}

      {/* Auto-play pause button - show only if multiple banners */}
      {activeBanners.length > 1 && (
        <button
          onClick={() => setIsAutoPlaying(!isAutoPlaying)}
          className="absolute top-4 right-4 px-3 py-1 rounded-full text-sm border transition-colors backdrop-blur-sm"
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
            borderColor: 'rgba(255, 255, 255, 0.3)',
            color: currentBanner.text_color,
          }}
        >
          {isAutoPlaying ? '⏸ Pause' : '▶ Play'}
        </button>
      )}
    </div>
  );
};

export default HomepageBanner;
