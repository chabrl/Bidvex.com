import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useSiteConfig } from '../contexts/SiteConfigContext';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import HeroPhone from '../components/HeroPhone';
import RecentlySoldTicker from '../components/RecentlySoldTicker';
import { 
  ArrowRight, Gavel, TrendingUp, Shield, Users, Award, Flame, 
  Search, Trophy, CreditCard, Sparkles, Clock, CheckCircle2,
  Zap, Play, ChevronRight, Timer, Package
} from 'lucide-react';
import { formatCurrency, formatListingPrice } from '../utils/currencyFormatter';
import SEO from '../components/SEO';
import SwipeableCardRow from '../components/SwipeableCardRow';
import { useTopSellers, useHotItems, useEndingSoon, useFeatured, useNewListings, useRecentlySold } from '../hooks/useHomePageData';
import useMarketplaceSync from '../hooks/useMarketplaceSync';
// iter202 Phase B — Replaces legacy HomepageLiveVehicles with the new carousel.
// Position constraint: AFTER StorageAuctionsPromo, BEFORE HotItemsSection (Tendances).
// Visibility constraint: hidden when feature flag OFF or zero active listings.
import HomepageVehicleCarousel from '../components/vehicles/HomepageVehicleCarousel';
import ProfessionalAuctionsPromo from '../components/ProfessionalAuctionsPromo';

// Smart routing: vehicles go to /vehicle-auctions/:id, everything else to /listing/:id
const getItemDetailPath = (item) => {
  const cat = (item.category || '').toLowerCase();
  if (cat === 'vehicle' || cat === 'vehicles' || cat === 'car' || cat === 'auto') {
    return `/vehicle-auctions/${item.id}`;
  }
  return item.auction_id ? `/lots/${item.auction_id}` : `/listing/${item.id}`;
};

// Custom hook for scroll-triggered animations with fallback visibility
const useScrollReveal = (threshold = 0.1) => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    // Fallback: Ensure visibility after 1.5s if IntersectionObserver fails
    const fallbackTimer = setTimeout(() => {
      setIsVisible(true);
    }, 1500);

    // Check if IntersectionObserver is supported
    if (!('IntersectionObserver' in window)) {
      setIsVisible(true);
      return () => clearTimeout(fallbackTimer);
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          clearTimeout(fallbackTimer);
          observer.unobserve(entry.target);
        }
      },
      { threshold, rootMargin: '50px' }
    );

    if (ref.current) {
      observer.observe(ref.current);
    } else {
      // If ref not available, show content immediately
      setIsVisible(true);
    }

    return () => {
      clearTimeout(fallbackTimer);
      observer.disconnect();
    };
  }, [threshold]);

  return [ref, isVisible];
};

const HomePage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isSectionVisible } = useSiteConfig();
  const [heroLoaded, setHeroLoaded] = useState(false);
  const [activeAuctions, setActiveAuctions] = useState(0);
  const queryClient = useQueryClient();

  // Lightweight public stats — live auctions count for hero pulse
  useEffect(() => {
    let cancelled = false;
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/stats/public`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.active_auctions === 'number') {
          setActiveAuctions(data.active_auctions);
        }
      })
      .catch(() => { /* silent — never break hero on stats failure */ });
    return () => { cancelled = true; };
  }, []);

  // React Query hooks replace manual useState + useEffect fetching
  const { data: topSellers = [] } = useTopSellers(8);
  const { data: hotItems = [] } = useHotItems(6);
  const { data: endingSoon = [] } = useEndingSoon(12, user?.id);
  const { data: featured = [] } = useFeatured(12);
  const { data: newListings = [] } = useNewListings(12);
  const { data: recentlySold = [] } = useRecentlySold(12);

  // Real-time marketplace sync — update cached cards on bid/extension events
  const handleMarketplaceUpdate = useCallback((msg) => {
    const { listing_id, current_price, bid_count, new_auction_end } = msg;
    const patchItem = (old) => {
      if (!Array.isArray(old)) return old;
      return old.map(item => {
        if (item.id !== listing_id) return item;
        const updated = { ...item };
        if (current_price != null) updated.current_price = current_price;
        if (bid_count != null) updated.bid_count = bid_count;
        if (new_auction_end) updated.auction_end_date = new_auction_end;
        return updated;
      });
    };
    // Patch all homepage query caches
    for (const key of ['ending-soon', 'hot-items', 'featured', 'new-listings']) {
      queryClient.setQueriesData({ queryKey: [key] }, patchItem);
    }
  }, [queryClient]);

  useMarketplaceSync(handleMarketplaceUpdate);

  useEffect(() => {
    // Trigger hero animation after mount
    setTimeout(() => setHeroLoaded(true), 100);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="home-page">
      <SEO 
        title="BidVex — Canada's Online Auction Marketplace"
        description="Bid on electronics, vehicles, art, collectibles & more. Real-time auctions with secure payments. Join thousands of Canadian buyers and sellers."
        path="/"
        jsonLd={{
          "@context": "https://schema.org",
          "@type": "WebSite",
          "name": "BidVex",
          "url": "https://bidvex.com",
          "description": "Canada's trusted online auction marketplace",
          "potentialAction": {
            "@type": "SearchAction",
            "target": "https://bidvex.com/marketplace?search={search_term_string}",
            "query-input": "required name=search_term_string"
          }
        }}
      />
      {/* Recently Sold Ticker (iter175) — only renders when ≥10 sold auctions exist */}
      <RecentlySoldTicker />

      {/* ========== EXTRAORDINARY HERO SECTION ========== */}
      <section className="relative min-h-[90vh] flex items-center overflow-hidden">
        {/* Animated Gradient Background */}
        <div className="absolute inset-0 animated-gradient" />
        
        {/* Animated Pattern Overlay */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }} />
        </div>
        
        {/* Floating Orbs */}
        <div className="absolute top-20 left-10 w-64 h-64 bg-cyan-400/20 rounded-full blur-[80px] float-animation" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-blue-600/20 rounded-full blur-[100px] float-animation" style={{ animationDelay: '-2s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/10 rounded-full blur-[120px]" />
        
        {/* Particle Effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 bg-cyan-400 rounded-full opacity-60"
              style={{
                top: `${Math.random() * 100}%`,
                left: `${Math.random() * 100}%`,
                animation: `sparkle ${2 + Math.random() * 3}s ease-in-out infinite`,
                animationDelay: `${Math.random() * 2}s`
              }}
            />
          ))}
        </div>

        {/* Hero Content — 2-column grid: text + phone mockup */}
        <div className="relative max-w-7xl mx-auto px-4 py-20 md:py-28 w-full">
          <div className="grid lg:grid-cols-[1.15fr_1fr] gap-10 lg:gap-16 items-center">
            {/* Left Content */}
            <div className="text-white space-y-8">
              {/* Animated Badge */}
              <div className={`transition-all duration-1000 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                <Badge className="bg-white/10 backdrop-blur-md text-white border border-cyan-400/30 text-sm px-5 py-2.5 shadow-lg shadow-cyan-500/20">
                  <Sparkles className="h-4 w-4 mr-2 inline text-cyan-400" />
                  {t('homepage.liveAuctionsNow')}
                </Badge>
              </div>
              
              {/* Animated Headline */}
              <div className="space-y-4">
                <h1 className={`text-5xl md:text-6xl lg:text-7xl font-bold leading-[1.1] transition-all duration-1000 delay-200 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                  <span className="block text-white">{t('homepage.discover')}</span>
                  <span className="block bg-gradient-to-r from-cyan-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
                    {t('homepage.bid')}
                  </span>
                  <span className="block text-white">{t('homepage.win')}</span>
                </h1>
              </div>
              
              {/* Animated Description */}
              <p className={`text-lg md:text-xl text-white max-w-lg leading-relaxed transition-all duration-1000 delay-400 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                {t('homepage.heroDescription')}
              </p>
              
              {/* Animated CTA Buttons */}
              <div className={`flex flex-col sm:flex-row gap-4 transition-all duration-1000 delay-500 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                <Button 
                  onClick={() => navigate('/marketplace')}
                  className="btn-shine bg-gradient-to-r from-cyan-500 to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-slate-900 font-bold px-8 py-6 text-lg shadow-xl shadow-cyan-500/30 hover:shadow-2xl hover:shadow-cyan-400/40 transition-all hover:-translate-y-1 whitespace-nowrap"
                >
                  <Zap className="mr-2 h-5 w-5 flex-shrink-0" />
                  {t('hero.browseAuctions')}
                  <ArrowRight className="ml-2 h-5 w-5 flex-shrink-0" />
                </Button>
                <Button 
                  onClick={() => navigate('/how-it-works')}
                  variant="outline"
                  className="border-2 border-white/30 bg-white/5 backdrop-blur-sm text-white hover:bg-white/15 hover:border-cyan-400/50 px-8 py-6 text-lg transition-all whitespace-nowrap"
                >
                  <Play className="mr-2 h-5 w-5 flex-shrink-0" />
                  {t('homepage.howItWorks')}
                </Button>
              </div>

              {/* Live auction counter — only render when there are real active auctions */}
              {activeAuctions > 0 && (
                <div
                  className="inline-flex items-center gap-2 bg-white/10 backdrop-blur rounded-full px-4 py-2 text-white border border-white/20"
                  data-testid="live-auctions-pill"
                >
                  <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                  <span className="font-bold tabular-nums">{activeAuctions}</span>
                  <span className="text-sm opacity-80">
                    {(i18n.language || 'en').startsWith('fr') ? 'Enchères en direct maintenant' : 'Live Auctions Now'}
                  </span>
                </div>
              )}

              {/* Trust Indicators */}
              <div className={`flex flex-wrap items-center gap-6 pt-4 transition-all duration-1000 delay-700 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                {[
                  { icon: <Shield className="h-5 w-5" />, text: t('homepage.securePayments'), color: 'text-green-400' },
                  { icon: <CheckCircle2 className="h-5 w-5" />, text: t('homepage.verifiedSellers'), color: 'text-cyan-400' },
                  { icon: <Trophy className="h-5 w-5" />, text: t('homepage.buyerProtection'), color: 'text-yellow-400' }
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-blue-100/80">
                    <span className={item.color}>{item.icon}</span>
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Right column — animated phone mockup */}
            <div className="relative flex items-center justify-center" data-testid="hero-right-column">
              <HeroPhone />
            </div>
          </div>
        </div>
        
        {/* Wave Divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full">
            <path d="M0 120L48 108C96 96 192 72 288 60C384 48 480 48 576 54C672 60 768 72 864 78C960 84 1056 84 1152 78C1248 72 1344 60 1392 54L1440 48V120H1392C1344 120 1248 120 1152 120C1056 120 960 120 864 120C768 120 672 120 576 120C480 120 384 120 288 120C192 120 96 120 48 120H0Z" fill="#F8FAFC" className="dark:fill-slate-900"/>
          </svg>
        </div>
      </section>

      {/* ========== LIVE AUCTIONS SECTION ========== */}
      {isSectionVisible('ending_soon') && (
        <LiveAuctionsSection items={endingSoon} navigate={navigate} />
      )}

      {/* iter217 Phase 3 — Professional Auctions section (after hero, before Storage Auctions) */}
      <ProfessionalAuctionsPromo navigate={navigate} />

      {/* ========== STORAGE AUCTIONS PROMO (iter171 — always bilingual) ========== */}
      <StorageAuctionsPromo navigate={navigate} />

      {/* iter202 Phase B — VEHICLE AUCTIONS CAROUSEL ==================== */}
      {/* Position: AFTER Storage Unit Auctions, BEFORE Tendances/Trending  */}
      {/* Visibility: hidden when flag OFF or zero active listings (B3)    */}
      <HomepageVehicleCarousel />

      {/* ========== LIVE STORAGE LOTS (iter172) ========== */}
      <HomepageLiveStorage navigate={navigate} />

      {/* ========== HOT ITEMS WITH LIVE ANIMATIONS ========== */}
      {isSectionVisible('hot_items') && (
        <HotItemsSection items={hotItems} navigate={navigate} />
      )}

      {/* ========== FEATURED AUCTIONS ========== */}
      {isSectionVisible('featured') && (
        <FeaturedSection items={featured} navigate={navigate} />
      )}

      {/* ========== BROWSE INDIVIDUAL ITEMS (Uses browse_items toggle) ========== */}
      {isSectionVisible('browse_items') && (
        <NewListingsSection items={newListings} navigate={navigate} />
      )}

      {/* ========== WHY CHOOSE BIDVEX (Trust Features) ========== */}
      {isSectionVisible('trust_features') && (
        <FeaturesSection navigate={navigate} />
      )}

      {/* ========== TOP SELLERS ========== */}
      {isSectionVisible('top_sellers') && topSellers.length > 0 && (
        <TopSellersSection sellers={topSellers} />
      )}

      {/* ========== HOW IT WORKS ========== */}
      {isSectionVisible('how_it_works') && (
        <HowItWorksSection navigate={navigate} />
      )}
    </div>
  );
};

// ========== LIVE AUCTIONS SECTION ==========
const LiveAuctionsSection = ({ items, navigate }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-12 sm:py-16 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800">
      <div className="max-w-7xl mx-auto">
        <div className={`flex items-center justify-between mb-8 sm:mb-10 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            <div className="relative shrink-0">
              <Clock className="h-6 w-6 sm:h-8 sm:w-8 text-red-500" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full animate-ping" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full" />
            </div>
            <div className="min-w-0">
              <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-slate-50 truncate">{t('homepage.endingSoon')}</h2>
              <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 truncate">{t('homepage.endingSoonDesc')}</p>
            </div>
          </div>
          <Button onClick={() => navigate('/marketplace?sort=ending')} variant="outline" className="flex border-2 border-slate-300 dark:border-cyan-500/50 hover:border-cyan-500 hover:text-cyan-600 dark:text-slate-200 dark:hover:text-cyan-400 whitespace-nowrap shrink-0 text-xs sm:text-sm px-3 sm:px-4">
            {t('homepage.viewAll')} <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>

        <SwipeableCardRow
          items={items.slice(0, 4)}
          gridCols="sm:grid-cols-2 lg:grid-cols-4"
          mobileWidth="w-[80vw]"
          renderCard={(item, index) => (
            <LiveAuctionCard key={item.id} item={item} index={index} isVisible={isVisible} navigate={navigate} />
          )}
        />
      </div>
    </section>
  );
};

// ========== LIVE AUCTION CARD ==========
const LiveAuctionCard = ({ item, index, isVisible, navigate }) => {
  const { t } = useTranslation();
  const [timeLeft, setTimeLeft] = useState('');

  useEffect(() => {
    const calculateTimeLeft = () => {
      const end = new Date(item.auction_end_date);
      const now = new Date();
      const diff = end - now;
      
      if (diff <= 0) return t('homepage.ended');
      
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      if (hours > 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
      return `${hours}h ${minutes}m ${seconds}s`;
    };

    setTimeLeft(calculateTimeLeft());
    const timer = setInterval(() => setTimeLeft(calculateTimeLeft()), 1000);
    return () => clearInterval(timer);
  }, [item.auction_end_date, t]);

  const isUrgent = timeLeft.includes('m') && !timeLeft.includes('h') && !timeLeft.includes('d');

  return (
    <Card 
      className={`card-hover-pop cursor-pointer overflow-hidden border-0 shadow-lg bg-white dark:bg-slate-800/50 dark:backdrop-blur-sm transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
      style={{ transitionDelay: `${index * 100}ms` }}
      onClick={() => navigate(getItemDetailPath(item))}
    >
      <div className="relative h-40 sm:h-48 overflow-hidden bg-slate-100 dark:bg-slate-700">
        {item.images?.[0] ? (
          <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-600">
            <span className="text-5xl">📦</span>
          </div>
        )}
        
        {/* Live Timer Badge */}
        <div className={`absolute top-3 right-3 px-3 py-1.5 rounded-full text-sm font-bold flex items-center gap-2 ${isUrgent ? 'bg-red-500 text-white pulse-urgent' : 'bg-slate-900/80 backdrop-blur text-white pulse-timer'}`}>
          <Timer className="h-4 w-4" />
          {timeLeft}
        </div>
        
        {/* Live Indicator */}
        <div className="absolute top-3 left-3 px-2 py-1 bg-cyan-500 text-white text-xs font-semibold rounded-full flex items-center gap-1.5">
          <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
          {t('homepage.live')}
        </div>
      </div>
      
      <CardContent className="p-4 sm:p-5">
        <h3 className="font-semibold text-base sm:text-lg mb-2 sm:mb-3 line-clamp-1 text-slate-900 dark:text-slate-50">{item.title}</h3>
        <div className="flex justify-between items-end">
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('homepage.currentBid')}</p>
            <p className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
              {formatListingPrice(item.current_price, item.currency)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-500 dark:text-slate-400">{item.total_bids || 0} {t('homepage.bids')}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ========== HOT ITEMS SECTION ==========
const HotItemsSection = ({ items, navigate }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section 
      ref={ref} 
      className="py-12 sm:py-16 lg:py-20 px-4 sm:px-6 lg:px-8 relative overflow-hidden bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:bg-none dark:text-white"
      style={{ '--hot-dark-bg': 'linear-gradient(135deg, #1E3A8A 0%, #0F172A 40%, #06B6D4 100%)' }}
    >
      {/* Dark mode gradient background */}
      <div className="absolute inset-0 hidden dark:block" style={{ background: 'linear-gradient(135deg, #1E3A8A 0%, #0F172A 40%, #06B6D4 100%)' }} />
      {/* Background Orbs */}
      <div className="absolute inset-0 opacity-20 dark:opacity-30">
        <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full blur-[150px] bg-cyan-400 dark:bg-cyan-500" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full blur-[150px] bg-blue-400 dark:bg-blue-800" />
      </div>

      <div className="relative max-w-7xl mx-auto">
        {/* Header */}
        <div className={`flex items-center justify-between mb-8 sm:mb-12 transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            <div className="p-2.5 sm:p-3 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl shadow-lg shadow-orange-500/30 shrink-0">
              <Flame className="h-6 w-6 sm:h-8 sm:w-8 text-white" />
            </div>
            <div className="min-w-0">
              <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-white truncate">{t('homepage.hotItems')}</h2>
              <p className="text-sm sm:text-base text-slate-600 dark:text-cyan-200/90 truncate">{t('homepage.hotItemsDesc')}</p>
            </div>
          </div>
          <Button 
            onClick={() => navigate('/marketplace?sort=hot')} 
            variant="outline"
            className="hidden sm:flex items-center gap-1 px-3 sm:px-5 py-2 rounded-md font-semibold transition-all hover:-translate-y-0.5 whitespace-nowrap border-2 border-slate-300 dark:border-cyan-500/60 text-slate-700 dark:text-white hover:border-cyan-500 hover:text-cyan-600 dark:hover:bg-cyan-500/20 dark:hover:border-cyan-400 shrink-0 text-xs sm:text-sm"
          >
            {t('homepage.viewAll')} <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>

        {/* Cards Grid / Mobile Carousel */}
        <SwipeableCardRow
          items={items}
          gridCols="sm:grid-cols-2 lg:grid-cols-3"
          mobileWidth="w-[85vw]"
          renderCard={(item, index) => (
            <Card 
              key={item.id}
              className={`hover-glow-cyan cursor-pointer overflow-hidden border shadow-lg hover:shadow-xl transition-all duration-700 bg-white dark:bg-white/5 dark:backdrop-blur-md border-slate-200 dark:border-white/20 h-full ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${index * 150}ms` }}
              onClick={() => navigate(getItemDetailPath(item))}              data-testid="hot-item-card"
            >
              <div className="relative h-44 sm:h-52 overflow-hidden">
                {item.images?.[0] ? (
                  <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover transition-transform duration-500 hover:scale-110" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 dark:from-blue-900 dark:to-slate-900">
                    <Package className="h-16 w-16 text-slate-300 dark:text-slate-600" />
                  </div>
                )}
                <Badge className="absolute top-3 right-3 bg-gradient-to-r from-orange-500 to-red-500 text-white border-0 shadow-lg font-semibold text-xs">
                  <Flame className="h-3 w-3 mr-1" /> {item.views || 0} {t('homepage.views')}
                </Badge>
                
                {/* Live Activity Indicator */}
                <div className="absolute bottom-3 left-3 right-3">
                  <div className="bg-slate-900/95 backdrop-blur-md rounded-lg px-3.5 py-2.5 flex items-center gap-2.5 border border-cyan-400/40">
                    <span 
                      className="w-2.5 h-2.5 rounded-full animate-pulse shadow-lg bg-cyan-400 shrink-0"
                      style={{ boxShadow: '0 0 10px #06B6D4, 0 0 20px rgba(6, 182, 212, 0.5)' }} 
                    />
                    <span className="active-bidding-label">{t('homepage.activeBidding')}</span>
                  </div>
                </div>
              </div>
              
              <CardContent className="p-4 sm:p-5">
                <h3 className="font-semibold text-base sm:text-lg mb-2 sm:mb-3 line-clamp-1 text-slate-900 dark:text-white">{item.title}</h3>
                <div className="flex justify-between items-end">
                  <div>
                    <p className="text-xs uppercase tracking-wider font-medium text-slate-500 dark:text-cyan-200/80">{t('homepage.currentBid')}</p>
                    <p className="text-xl sm:text-2xl font-bold text-cyan-600 dark:text-cyan-300">{formatListingPrice(item.current_price, item.currency)}</p>
                  </div>
                  <Button 
                    size="sm" 
                    className="font-bold shadow-lg transition-all hover:-translate-y-0.5 whitespace-nowrap bg-gradient-to-r from-cyan-500 to-blue-500 text-white hover:from-cyan-600 hover:to-blue-600"
                    data-testid="hot-bid-now-btn"
                  >
                    {t('homepage.bidNow')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        />

        {/* Mobile View All Button */}
        <div className="flex sm:hidden justify-center mt-8">
          <Button 
            onClick={() => navigate('/marketplace?sort=hot')} 
            className="font-bold px-8 py-3 whitespace-nowrap bg-gradient-to-r from-cyan-500 to-blue-500 text-white hover:from-cyan-600 hover:to-blue-600 w-full sm:w-auto"
          >
            {t('homepage.viewAll')} <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </section>
  );
};

// ========== FEATURED SECTION ==========
const FeaturedSection = ({ items, navigate }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-12 sm:py-16 px-4 sm:px-6 lg:px-8 bg-white dark:bg-slate-900">
      <div className="max-w-7xl mx-auto">
        <div className={`text-center mb-8 sm:mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Badge className="bg-gradient-to-r from-blue-600 to-cyan-500 text-white border-0 mb-4 px-4 py-2">
            <Sparkles className="h-4 w-4 mr-2 inline" />
            {t('homepage.featured')}
          </Badge>
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-slate-50 mb-3">{t('homepage.curatedAuctions')}</h2>
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">{t('homepage.handPicked')}</p>
        </div>

        <SwipeableCardRow
          items={items.slice(0, 8)}
          gridCols="sm:grid-cols-3 lg:grid-cols-4"
          gap="gap-3 sm:gap-4 lg:gap-6"
          mobileWidth="w-[45vw]"
          renderCard={(item, index) => (
            <Card 
              key={item.id}
              className={`card-hover-pop cursor-pointer overflow-hidden border-0 shadow-md dark:bg-slate-800/50 dark:backdrop-blur-sm transition-all duration-700 h-full ${isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}
              style={{ transitionDelay: `${index * 50}ms` }}
              onClick={() => navigate(getItemDetailPath(item))}            >
              <div className="relative aspect-square overflow-hidden bg-slate-100 dark:bg-slate-700">
                {item.images?.[0] ? (
                  <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-600">
                    <span className="text-4xl">📦</span>
                  </div>
                )}
              </div>
              <CardContent className="p-3 sm:p-4">
                <h3 className="font-medium text-xs sm:text-sm mb-1 sm:mb-2 line-clamp-1 text-slate-900 dark:text-slate-50">{item.title}</h3>
                <p className="text-base sm:text-lg font-bold text-blue-600 dark:text-cyan-400">{formatListingPrice(item.current_price, item.currency)}</p>
              </CardContent>
            </Card>
          )}
        />
      </div>
    </section>
  );
};

// ========== NEW LISTINGS SECTION ==========
const NewListingsSection = ({ items, navigate }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-12 sm:py-16 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-7xl mx-auto">
        <div className={`flex items-center justify-between mb-8 sm:mb-10 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <div className="min-w-0">
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-slate-50">{t('homepage.justListed')}</h2>
            <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 mt-1 sm:mt-2">{t('homepage.freshAuctions')}</p>
          </div>
          <Button onClick={() => navigate('/marketplace?sort=newest')} variant="outline" className="flex border-2 border-slate-300 dark:border-cyan-500/50 hover:border-cyan-500 hover:text-cyan-600 dark:text-slate-200 dark:hover:text-cyan-400 whitespace-nowrap shrink-0 text-xs sm:text-sm px-3 sm:px-4">
            {t('homepage.viewAll')} <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>

        <SwipeableCardRow
          items={items.slice(0, 6)}
          gridCols="sm:grid-cols-3 lg:grid-cols-6"
          gap="gap-3 sm:gap-4"
          mobileWidth="w-[42vw]"
          renderCard={(item, index) => (
            <Card 
              key={item.id}
              className={`card-hover-pop cursor-pointer overflow-hidden border-0 shadow-md dark:bg-slate-800/50 dark:backdrop-blur-sm transition-all duration-700 h-full ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${index * 80}ms` }}
              onClick={() => navigate(getItemDetailPath(item))}            >
              <div className="relative aspect-square overflow-hidden bg-slate-100 dark:bg-slate-700">
                {item.images?.[0] ? (
                  <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-600">
                    <span className="text-3xl">📦</span>
                  </div>
                )}
                <Badge className="absolute top-2 left-2 bg-green-500 text-white text-xs border-0">{t('homepage.new')}</Badge>
              </div>
              <CardContent className="p-3">
                <h3 className="font-medium text-xs mb-1 line-clamp-1 text-slate-900 dark:text-slate-50">{item.title}</h3>
                <p className="text-sm font-bold text-blue-600 dark:text-cyan-400">{formatListingPrice(item.current_price, item.currency)}</p>
              </CardContent>
            </Card>
          )}
        />
      </div>
    </section>
  );
};

// ========== FEATURES SECTION ==========
const FeaturesSection = ({ navigate }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  const features = [
    { icon: <Gavel className="h-7 w-7" />, title: t('homepage.liveBidding'), desc: t('homepage.liveBiddingDesc') },
    { icon: <Shield className="h-7 w-7" />, title: t('homepage.securePayments'), desc: t('homepage.securePaymentsDesc') },
    { icon: <Trophy className="h-7 w-7" />, title: t('homepage.buyerProtection'), desc: t('homepage.buyerProtectionDesc') },
    { icon: <Users className="h-7 w-7" />, title: t('homepage.globalCommunity'), desc: t('homepage.globalCommunityDesc') }
  ];

  return (
    <section ref={ref} className="py-12 sm:py-16 lg:py-20 px-4 sm:px-6 lg:px-8 bg-white dark:bg-slate-800">
      <div className="max-w-7xl mx-auto">
        <div className={`text-center mb-8 sm:mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-slate-50 mb-3">{t('homepage.whyChooseBidvex')}</h2>
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300">{t('homepage.trustedPlatform')}</p>
        </div>

        <SwipeableCardRow
          items={features}
          gridCols="sm:grid-cols-2 lg:grid-cols-4"
          mobileWidth="w-[75vw]"
          renderCard={(feature, index) => (
            <div 
              key={index}
              className={`group p-5 sm:p-8 rounded-2xl bg-gradient-to-br from-slate-50 to-white dark:from-slate-800 dark:to-slate-700 border border-slate-100 dark:border-slate-600 hover:border-cyan-200 dark:hover:border-cyan-500/50 hover:shadow-xl hover:shadow-cyan-500/10 dark:hover:shadow-cyan-500/20 transition-all duration-500 flex flex-col items-center text-center h-full ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${index * 100}ms` }}
            >
              <div className="w-14 h-14 mb-5 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/30 group-hover:scale-110 transition-transform">
                {feature.icon}
              </div>
              <h3 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-slate-50 mb-2">{feature.title}</h3>
              <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 leading-relaxed">{feature.desc}</p>
            </div>
          )}
        />
      </div>
    </section>
  );
};

// ========== TOP SELLERS SECTION ==========
const TopSellersSection = ({ sellers }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  return (
    <section ref={ref} className="py-12 sm:py-16 lg:py-20 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-7xl mx-auto">
        <div className={`text-center mb-8 sm:mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Badge className="bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-700 mb-4"><Award className="h-4 w-4 mr-2 inline" />{t('homepage.topPerformers')}</Badge>
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-slate-50">{t('homepage.topSellers')}</h2>
        </div>

        <SwipeableCardRow
          items={sellers.slice(0, 3)}
          gridCols="sm:grid-cols-2 lg:grid-cols-3"
          mobileWidth="w-[80vw]"
          renderCard={(seller, idx) => (
            <Card 
              key={seller.user?.id || idx} 
              className={`card-hover-pop overflow-hidden border-0 shadow-lg dark:bg-slate-800/50 dark:backdrop-blur-sm transition-all duration-700 h-full ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${idx * 150}ms` }}
            >
              <CardContent className="p-5 sm:p-8 text-center">
                <div className="relative inline-block mb-6">
                  {seller.user?.picture ? (
                    <img src={seller.user.picture} alt={seller.user.name} className="w-24 h-24 rounded-full mx-auto ring-4 ring-slate-100 dark:ring-slate-700" />
                  ) : (
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white text-3xl font-bold mx-auto ring-4 ring-slate-100 dark:ring-slate-700">
                      {seller.user?.name?.charAt(0) || 'S'}
                    </div>
                  )}
                  {idx === 0 && (
                    <div className="absolute -top-2 -right-2 w-10 h-10 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center text-white shadow-lg">
                      🏆
                    </div>
                  )}
                </div>
                <h3 className="font-bold text-xl mb-4 text-slate-900 dark:text-slate-50">{seller.user?.name || 'Top Seller'}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-xl p-4">
                    <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('homepage.totalSales')}</p>
                    <p className="text-xl font-bold text-green-600 dark:text-green-400">${seller.total_sales?.toFixed(0)}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-xl p-4">
                    <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('homepage.itemsSold')}</p>
                    <p className="text-xl font-bold text-slate-700 dark:text-slate-200">{seller.items_sold}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        />
      </div>
    </section>
  );
};

// ========== HOW IT WORKS SECTION ==========
const HowItWorksSection = ({ navigate }) => {
  const { t } = useTranslation();
  const [ref, isVisible] = useScrollReveal(0.1);

  const steps = [
    { icon: <Search className="h-7 w-7" />, title: t('homepage.browse'), desc: t('homepage.browseDesc') },
    { icon: <Gavel className="h-7 w-7" />, title: t('homepage.bidStep'), desc: t('homepage.bidStepDesc') },
    { icon: <Trophy className="h-7 w-7" />, title: t('homepage.winStep'), desc: t('homepage.winStepDesc') }
  ];

  return (
    <section ref={ref} className="py-12 sm:py-16 lg:py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-blue-600 via-cyan-600 to-blue-700 dark:from-blue-900 dark:via-slate-900 dark:to-slate-900 text-white relative overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 opacity-20 dark:opacity-30">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-cyan-300 dark:bg-cyan-500 rounded-full blur-[200px]" />
      </div>

      <div className="relative max-w-5xl mx-auto text-center">
        <div className={`mb-8 sm:mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Badge className="bg-white/20 backdrop-blur border-white/30 dark:border-cyan-400/30 mb-4 text-white font-semibold shadow-lg">{t('homepage.gettingStarted')}</Badge>
          <h2 className="text-2xl sm:text-3xl lg:text-5xl font-bold mb-3 sm:mb-4 text-white drop-shadow-lg">{t('homepage.howItWorksTitle')}</h2>
          <p className="max-w-2xl mx-auto text-base sm:text-lg text-white drop-shadow-md">{t('homepage.startWinning')}</p>
        </div>

        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-6 sm:gap-8 mb-8 sm:mb-12">
          {steps.map((step, index) => (
            <div 
              key={index}
              className={`relative transition-all duration-700 hover:scale-105 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${(index + 1) * 150}ms` }}
            >
              <div className="bg-white/15 dark:bg-white/10 backdrop-blur-md rounded-2xl p-5 sm:p-8 border border-white/20 dark:border-white/10 hover:bg-white/25 dark:hover:bg-white/15 hover:border-white/40 dark:hover:border-cyan-400/50 hover:shadow-2xl hover:shadow-cyan-400/30 dark:hover:shadow-cyan-500/20 transition-all">
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-10 h-10 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-full flex items-center justify-center text-sm font-bold text-white shadow-lg shadow-cyan-400/60">
                  {index + 1}
                </div>
                <div className="w-16 h-16 mx-auto mb-5 rounded-xl bg-gradient-to-br from-white/30 to-white/10 dark:from-cyan-500 dark:to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-400/40 dark:shadow-cyan-500/30 text-white backdrop-blur-sm">
                  {step.icon}
                </div>
                <h3 className="text-xl font-bold mb-3 text-white drop-shadow-md">{step.title}</h3>
                <p className="text-white leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={`transition-all duration-700 delay-500 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Button 
            onClick={() => navigate('/how-it-works')}
            className="btn-shine bg-white hover:bg-white/90 text-blue-700 dark:text-blue-700 font-bold px-10 py-6 text-lg shadow-xl shadow-white/30 hover:shadow-2xl hover:shadow-white/40 hover:-translate-y-1 transition-all whitespace-nowrap"
          >
            {t('homepage.learnMore')}
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </div>
    </section>
  );
};

// ========== STORAGE AUCTIONS PROMO (iter171, fully i18n iter193) ==========
const StorageAuctionsPromo = ({ navigate }) => {
  const { t } = useTranslation();
  const [stats, setStats] = React.useState(null);

  React.useEffect(() => {
    const API = (process.env.REACT_APP_BACKEND_URL || '') + '/api';
    fetch(`${API}/storage-auctions/stats/public`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setStats(d))
      .catch(() => {});
  }, []);

  return (
    <section className="py-14 sm:py-16 bg-sky-50 dark:bg-gradient-to-r dark:from-[#0B2545] dark:to-[#0E2B52] border-t border-sky-100 dark:border-[#0B2545] relative overflow-hidden" data-testid="homepage-storage-promo">
      {/* Subtle particle background (dark mode only) */}
      <div className="absolute inset-0 opacity-0 dark:opacity-30 pointer-events-none">
        <div className="absolute top-4 left-10 w-1.5 h-1.5 bg-[#3FB4CB] rounded-full animate-pulse" />
        <div className="absolute top-12 left-1/4 w-1 h-1 bg-[#3FB4CB] rounded-full animate-pulse" style={{ animationDelay: '0.5s' }} />
        <div className="absolute bottom-8 right-1/4 w-1.5 h-1.5 bg-[#3FB4CB] rounded-full animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 right-10 w-1 h-1 bg-[#3FB4CB] rounded-full animate-pulse" style={{ animationDelay: '1.5s' }} />
      </div>

      {/* iter199 — Decorative blue "wave" arcs that the 3D unit subtly overlaps */}
      <svg
        aria-hidden="true"
        className="absolute right-0 top-1/2 -translate-y-1/2 w-[60%] max-w-[720px] h-[120%] opacity-40 dark:opacity-25 pointer-events-none"
        viewBox="0 0 600 600"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="storageWaveGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#3FB4CB" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#0B2545" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M-50 320 Q 200 80 600 240 T 1200 200" stroke="url(#storageWaveGrad)" strokeWidth="80" fill="none" />
        <path d="M-80 420 Q 220 240 600 360 T 1200 320" stroke="url(#storageWaveGrad)" strokeWidth="60" fill="none" opacity="0.65" />
      </svg>

      <div className="container mx-auto px-4 relative">
        <div className="flex flex-col-reverse md:flex-row items-center gap-8 md:gap-12 lg:gap-20">

          {/* Text content (LEFT on desktop, BELOW on mobile) */}
          <div className="flex-1 text-[#0B2545] dark:text-white w-full max-w-2xl">
            <div
              className="inline-block bg-sky-600 dark:bg-[#3FB4CB] text-white dark:text-[#0B2545] text-xs font-bold px-3 py-1 rounded-full mb-3 uppercase tracking-wider"
              data-testid="homepage-storage-promo-badge"
            >
              {t('home.storagePromo.badge')}
            </div>

            <h2 className="text-3xl md:text-4xl lg:text-5xl font-black mb-4 text-[#0B2545] dark:text-white leading-tight" data-testid="homepage-storage-promo-title">
              {t('home.storagePromo.title')}
            </h2>

            <p className="text-base md:text-lg text-gray-700 dark:text-gray-200 mb-6 leading-relaxed" data-testid="homepage-storage-promo-desc">
              {t('home.storagePromo.description')}
            </p>

            {/* Trust badges — single language, follows global toggle */}
            <div className="flex flex-wrap gap-2.5 mb-6">
              <span className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200 px-3 py-1.5 rounded-full text-xs font-semibold border border-emerald-300 dark:border-emerald-700/40">
                ✅ {t('home.storagePromo.noBuyerFees')}
              </span>
              <span className="bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-300 px-3 py-1.5 rounded-full text-xs font-semibold border border-sky-300 dark:border-sky-700/40">
                🇨🇦 {t('home.storagePromo.canadianFacilities')}
              </span>
              <span className="bg-purple-100 text-purple-800 dark:bg-purple-900/60 dark:text-purple-200 px-3 py-1.5 rounded-full text-xs font-semibold border border-purple-300 dark:border-purple-700/40">
                ⚡ {t('home.storagePromo.realTimeBidding')}
              </span>
            </div>

            {/* Live stats inline (if > 0) */}
            {stats && (stats.total_sold > 0 || stats.active_auctions > 0 || stats.active_facilities > 0) && (
              <div className="flex flex-wrap gap-4 mb-5 text-xs text-gray-700 dark:text-gray-300" data-testid="homepage-storage-promo-stats">
                {stats.active_auctions > 0 && (
                  <span className="font-semibold">
                    <span className="text-sky-700 dark:text-[#3FB4CB] text-base font-black">{stats.active_auctions}</span>{' '}
                    {t('home.storagePromo.liveNow')}
                  </span>
                )}
                {stats.active_facilities > 0 && (
                  <span className="font-semibold">
                    <span className="text-sky-700 dark:text-[#3FB4CB] text-base font-black">{stats.active_facilities}</span>{' '}
                    {t('home.storagePromo.facilities')}
                  </span>
                )}
                {stats.total_sold > 0 && (
                  <span className="font-semibold">
                    <span className="text-sky-700 dark:text-[#3FB4CB] text-base font-black">{stats.total_sold}</span>{' '}
                    {t('home.storagePromo.sold')}
                  </span>
                )}
              </div>
            )}

            {/* CTA buttons — side-by-side on desktop, wrap on mobile */}
            <div className="flex flex-row flex-wrap gap-3">
              <button
                type="button"
                onClick={() => navigate('/storage-auctions')}
                className="bg-sky-600 hover:bg-sky-500 dark:bg-[#3FB4CB] dark:hover:bg-[#2FA0BA] text-white dark:text-[#0B2545] font-bold py-3 px-6 rounded-xl transition-all hover:-translate-y-0.5 hover:shadow-lg"
                data-testid="homepage-storage-promo-browse-btn"
              >
                {t('home.storagePromo.browseStorageBtn')}
              </button>
              <button
                type="button"
                onClick={() => navigate('/storage-auctions/register-facility')}
                className="border-2 border-sky-600 dark:border-[#3FB4CB] text-sky-700 dark:text-[#3FB4CB] hover:bg-sky-100 dark:hover:bg-[#3FB4CB]/10 font-bold py-3 px-6 rounded-xl transition-all"
                data-testid="homepage-storage-promo-register-btn"
              >
                {t('home.storagePromo.listFacilityBtn')}
              </button>
            </div>
          </div>

          {/* iter199 — 3D Storage Unit (RIGHT on desktop, ABOVE on mobile via flex-col-reverse) */}
          <div
            className="flex-shrink-0 w-full md:w-[42%] lg:w-[44%] xl:w-[46%] flex justify-center md:justify-end items-center pointer-events-none"
            data-testid="homepage-storage-promo-3d-wrapper"
          >
            <img
              src="/assets/storage-unit-3d.png"
              alt={t('home.storagePromo.title')}
              loading="lazy"
              className="w-full max-w-[420px] sm:max-w-[480px] md:max-w-none md:w-[110%] lg:w-[115%] h-auto drop-shadow-[0_22px_40px_rgba(11,37,69,0.35)] dark:drop-shadow-[0_22px_50px_rgba(63,180,203,0.25)] md:-translate-y-2 transition-transform duration-700 ease-out hover:md:-translate-y-3 select-none"
              data-testid="homepage-storage-promo-3d-image"
              draggable={false}
            />
          </div>

        </div>
      </div>
    </section>
  );
};

// ========== HOMEPAGE LIVE VEHICLE AUCTIONS (iter172, fully i18n iter193) ==========
const HomepageLiveVehicles = ({ navigate }) => {
  const { t } = useTranslation();
  const [items, setItems] = React.useState(null);
  React.useEffect(() => {
    const API = (process.env.REACT_APP_BACKEND_URL || '') + '/api';
    fetch(`${API}/vehicles?status=active&limit=10`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setItems(d?.vehicles || []))
      .catch(() => setItems([]));
  }, []);

  if (items && items.length === 0) return null; // Hide entirely if 0

  return (
    <section className="py-12 bg-[#0B2545]" data-testid="homepage-live-vehicles">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-3xl font-black text-white">{t('home.liveVehicles.title')}</h2>
          </div>
          <button
            type="button"
            onClick={() => navigate('/vehicles')}
            className="text-[#3FB4CB] font-semibold hover:underline text-sm"
            data-testid="homepage-vehicles-view-all"
          >
            {t('home.viewAllArrow')}
          </button>
        </div>

        {items === null ? (
          <div className="flex gap-4 overflow-x-auto pb-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="min-w-[260px] h-56 bg-slate-800/50 animate-pulse rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory" data-testid="homepage-vehicles-list">
            {items.slice(0, 10).map(v => (
              <div
                key={v.id}
                className="min-w-[260px] snap-start bg-slate-800 rounded-xl overflow-hidden border border-slate-700 hover:border-[#3FB4CB] transition-all cursor-pointer hover:-translate-y-0.5"
                onClick={() => navigate(`/vehicles/${v.id}`)}
                data-testid={`homepage-vehicle-card-${v.id}`}
              >
                <div className="h-36 bg-slate-700 overflow-hidden">
                  {v.photos?.[0] && (
                    <img src={v.photos[0]} alt="" loading="lazy" className="w-full h-full object-cover" />
                  )}
                </div>
                <div className="p-3">
                  <p className="text-xs text-slate-400 truncate">{v.year} {v.make}</p>
                  <p className="text-sm font-bold text-white truncate">{v.model}</p>
                  <p className="text-lg font-black text-[#3FB4CB] mt-1">${Number(v.current_bid || 0).toLocaleString()}</p>
                  <p className="text-[10px] text-slate-500">
                    {t('home.bidsCount', { count: v.bid_count || 0 })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

// ========== HOMEPAGE LIVE STORAGE LOTS (iter172, fully i18n iter193) ==========
const HomepageLiveStorage = ({ navigate }) => {
  const { t } = useTranslation();
  const [items, setItems] = React.useState(null);
  React.useEffect(() => {
    const API = (process.env.REACT_APP_BACKEND_URL || '') + '/api';
    fetch(`${API}/storage-auctions?status=active&limit=10`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setItems(d?.auctions || []))
      .catch(() => setItems([]));
  }, []);

  if (items && items.length === 0) return null;

  return (
    <section className="py-12 bg-sky-50 dark:bg-[#0E2B52]" data-testid="homepage-live-storage">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-3xl font-black text-[#0B2545] dark:text-white">🔒 {t('home.liveStorage.title')}</h2>
          </div>
          <button
            type="button"
            onClick={() => navigate('/storage-auctions')}
            className="text-sky-700 dark:text-[#3FB4CB] font-semibold hover:underline text-sm"
            data-testid="homepage-storage-view-all"
          >
            {t('home.viewAllArrow')}
          </button>
        </div>

        {items === null ? (
          <div className="flex gap-4 overflow-x-auto pb-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="min-w-[260px] h-56 bg-slate-200 dark:bg-slate-800/50 animate-pulse rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory" data-testid="homepage-storage-list">
            {items.slice(0, 10).map(a => (
              <div
                key={a.id}
                className="min-w-[260px] snap-start bg-white dark:bg-slate-800 rounded-xl overflow-hidden border border-sky-200 dark:border-slate-700 hover:border-sky-400 dark:hover:border-[#3FB4CB] transition-all cursor-pointer hover:-translate-y-0.5 shadow-sm"
                onClick={() => navigate(`/storage-auctions/${a.id}`)}
                data-testid={`homepage-storage-card-${a.id}`}
              >
                <div className="h-36 bg-sky-100 dark:bg-slate-700 overflow-hidden flex items-center justify-center text-4xl">
                  {a.photos?.[0] ? (
                    <img src={a.photos[0]} alt="" loading="lazy" className="w-full h-full object-cover" />
                  ) : '🔒'}
                </div>
                <div className="p-3">
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{a.facility_name}</p>
                  <p className="text-sm font-bold text-[#0B2545] dark:text-white truncate">#{a.unit_number} • {a.unit_size}</p>
                  <p className="text-lg font-black text-sky-700 dark:text-[#3FB4CB] mt-1">${Number(a.current_bid || 0).toLocaleString()}</p>
                  <p className="text-[10px] text-slate-500">
                    {t('home.bidsCount', { count: a.bid_count || 0 })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

export default HomePage;
