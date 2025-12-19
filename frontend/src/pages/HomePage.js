import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  ArrowRight, Gavel, TrendingUp, Shield, Users, Award, Flame, 
  Search, Trophy, CreditCard, Sparkles, Clock, CheckCircle2,
  Zap, Play, ChevronRight, Timer
} from 'lucide-react';
import HomepageBanner from '../components/HomepageBanner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Custom hook for scroll-triggered animations
const useScrollReveal = (threshold = 0.1) => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, isVisible];
};

const HomePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [topSellers, setTopSellers] = useState([]);
  const [hotItems, setHotItems] = useState([]);
  const [endingSoon, setEndingSoon] = useState([]);
  const [featured, setFeatured] = useState([]);
  const [newListings, setNewListings] = useState([]);
  const [recentlySold, setRecentlySold] = useState([]);
  const [heroLoaded, setHeroLoaded] = useState(false);

  useEffect(() => {
    // Trigger hero animation after mount
    setTimeout(() => setHeroLoaded(true), 100);
    
    fetchTopSellers();
    fetchHotItems();
    fetchEndingSoon();
    fetchFeatured();
    fetchNewListings();
    fetchRecentlySold();
  }, []);

  const fetchTopSellers = async () => {
    try {
      const response = await axios.get(`${API}/stats/top-sellers?limit=8`);
      setTopSellers(response.data);
    } catch (error) {
      console.error('Failed to fetch top sellers:', error);
    }
  };

  const fetchHotItems = async () => {
    try {
      const response = await axios.get(`${API}/stats/hot-items?limit=6`);
      setHotItems(response.data);
    } catch (error) {
      console.error('Failed to fetch hot items:', error);
    }
  };

  const fetchEndingSoon = async () => {
    try {
      const response = await axios.get(`${API}/carousel/ending-soon?limit=12`);
      setEndingSoon(response.data);
    } catch (error) {
      console.error('Failed to fetch ending soon:', error);
    }
  };

  const fetchFeatured = async () => {
    try {
      const response = await axios.get(`${API}/carousel/featured?limit=12`);
      setFeatured(response.data);
    } catch (error) {
      console.error('Failed to fetch featured:', error);
    }
  };

  const fetchNewListings = async () => {
    try {
      const response = await axios.get(`${API}/carousel/new-listings?limit=12`);
      setNewListings(response.data);
    } catch (error) {
      console.error('Failed to fetch new listings:', error);
    }
  };

  const fetchRecentlySold = async () => {
    try {
      const response = await axios.get(`${API}/carousel/recently-sold?limit=12`);
      setRecentlySold(response.data);
    } catch (error) {
      console.error('Failed to fetch recently sold:', error);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="home-page">
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

        {/* Hero Content */}
        <div className="relative max-w-7xl mx-auto px-4 py-20 md:py-32 w-full">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left Content */}
            <div className="text-white space-y-8">
              {/* Animated Badge */}
              <div className={`transition-all duration-1000 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                <Badge className="bg-white/10 backdrop-blur-md text-white border border-cyan-400/30 text-sm px-5 py-2.5 shadow-lg shadow-cyan-500/20">
                  <Sparkles className="h-4 w-4 mr-2 inline text-cyan-400" />
                  Live Auctions Happening Now
                </Badge>
              </div>
              
              {/* Animated Headline */}
              <div className="space-y-4">
                <h1 className={`text-5xl md:text-6xl lg:text-7xl font-bold leading-[1.1] transition-all duration-1000 delay-200 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                  <span className="block text-white">Discover.</span>
                  <span className="block bg-gradient-to-r from-cyan-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
                    Bid.
                  </span>
                  <span className="block text-white">Win.</span>
                </h1>
              </div>
              
              {/* Animated Description */}
              <p className={`text-lg md:text-xl text-blue-100/90 max-w-lg leading-relaxed transition-all duration-1000 delay-400 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                Experience the thrill of live auctions. Join thousands of bidders competing for 
                unique items at unbeatable prices. Your next treasure awaits.
              </p>
              
              {/* Animated CTA Buttons */}
              <div className={`flex flex-col sm:flex-row gap-4 transition-all duration-1000 delay-500 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                <Button 
                  onClick={() => navigate('/marketplace')}
                  className="btn-shine bg-gradient-to-r from-cyan-500 to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-slate-900 font-bold px-8 py-6 text-lg shadow-xl shadow-cyan-500/30 hover:shadow-2xl hover:shadow-cyan-400/40 transition-all hover:-translate-y-1"
                >
                  <Zap className="mr-2 h-5 w-5" />
                  Browse Auctions
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
                <Button 
                  onClick={() => navigate('/how-it-works')}
                  variant="outline"
                  className="border-2 border-white/30 bg-white/5 backdrop-blur-sm text-white hover:bg-white/15 hover:border-cyan-400/50 px-8 py-6 text-lg transition-all"
                >
                  <Play className="mr-2 h-5 w-5" />
                  How It Works
                </Button>
              </div>

              {/* Trust Indicators */}
              <div className={`flex flex-wrap items-center gap-6 pt-4 transition-all duration-1000 delay-700 ${heroLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
                {[
                  { icon: <Shield className="h-5 w-5" />, text: 'Secure Payments', color: 'text-green-400' },
                  { icon: <CheckCircle2 className="h-5 w-5" />, text: 'Verified Sellers', color: 'text-cyan-400' },
                  { icon: <Trophy className="h-5 w-5" />, text: 'Buyer Protection', color: 'text-yellow-400' }
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-blue-100/80">
                    <span className={item.color}>{item.icon}</span>
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Right Side - Live Stats Cards */}
            <div className={`hidden lg:grid grid-cols-2 gap-5 transition-all duration-1000 delay-300 ${heroLoaded ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-20'}`}>
              {[
                { value: '50K+', label: 'Active Bidders', icon: <Users className="h-6 w-6" />, delay: 0 },
                { value: '10K+', label: 'Live Auctions', icon: <Gavel className="h-6 w-6" />, delay: 100 },
                { value: '$2M+', label: 'Items Won', icon: <TrendingUp className="h-6 w-6" />, delay: 200 },
                { value: '99.9%', label: 'Satisfaction', icon: <Award className="h-6 w-6" />, delay: 300 }
              ].map((stat, i) => (
                <div 
                  key={i} 
                  className="group bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20 hover:bg-white/20 hover:border-cyan-400/40 transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:shadow-cyan-500/20"
                  style={{ animationDelay: `${stat.delay}ms` }}
                >
                  <div className="text-cyan-400 mb-3 group-hover:scale-110 transition-transform">{stat.icon}</div>
                  <div className="text-4xl font-bold text-white mb-1">{stat.value}</div>
                  <div className="text-blue-200/70 text-sm">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Wave Divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full">
            <path d="M0 120L48 108C96 96 192 72 288 60C384 48 480 48 576 54C672 60 768 72 864 78C960 84 1056 84 1152 78C1248 72 1344 60 1392 54L1440 48V120H1392C1344 120 1248 120 1152 120C1056 120 960 120 864 120C768 120 672 120 576 120C480 120 384 120 288 120C192 120 96 120 48 120H0Z" fill="#F8FAFC"/>
          </svg>
        </div>
      </section>

      {/* ========== LIVE AUCTIONS SECTION ========== */}
      <LiveAuctionsSection items={endingSoon} navigate={navigate} />

      {/* Homepage Banner */}
      <section className="py-8 px-4">
        <div className="max-w-7xl mx-auto">
          <HomepageBanner />
        </div>
      </section>

      {/* ========== HOT ITEMS WITH LIVE ANIMATIONS ========== */}
      <HotItemsSection items={hotItems} navigate={navigate} />

      {/* ========== FEATURED AUCTIONS ========== */}
      <FeaturedSection items={featured} navigate={navigate} />

      {/* ========== NEW LISTINGS ========== */}
      <NewListingsSection items={newListings} navigate={navigate} />

      {/* ========== WHY CHOOSE BIDVEX ========== */}
      <FeaturesSection navigate={navigate} />

      {/* ========== TOP SELLERS ========== */}
      {topSellers.length > 0 && <TopSellersSection sellers={topSellers} />}

      {/* ========== HOW IT WORKS ========== */}
      <HowItWorksSection navigate={navigate} />
    </div>
  );
};

// ========== LIVE AUCTIONS SECTION ==========
const LiveAuctionsSection = ({ items, navigate }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-16 px-4 bg-gradient-to-b from-slate-50 to-white">
      <div className="max-w-7xl mx-auto">
        <div className={`flex items-center justify-between mb-10 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <div className="flex items-center gap-4">
            <div className="relative">
              <Clock className="h-8 w-8 text-red-500" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full animate-ping" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full" />
            </div>
            <div>
              <h2 className="text-3xl md:text-4xl font-bold text-slate-900">Ending Soon</h2>
              <p className="text-slate-600">Don't miss out! These auctions close soon</p>
            </div>
          </div>
          <Button onClick={() => navigate('/marketplace?sort=ending')} variant="outline" className="hidden md:flex border-2 border-slate-300 hover:border-cyan-500 hover:text-cyan-600">
            View All <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {items.slice(0, 4).map((item, index) => (
            <LiveAuctionCard key={item.id} item={item} index={index} isVisible={isVisible} navigate={navigate} />
          ))}
        </div>
      </div>
    </section>
  );
};

// ========== LIVE AUCTION CARD ==========
const LiveAuctionCard = ({ item, index, isVisible, navigate }) => {
  const [timeLeft, setTimeLeft] = useState('');

  useEffect(() => {
    const calculateTimeLeft = () => {
      const end = new Date(item.auction_end_date);
      const now = new Date();
      const diff = end - now;
      
      if (diff <= 0) return 'Ended';
      
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      if (hours > 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
      return `${hours}h ${minutes}m ${seconds}s`;
    };

    setTimeLeft(calculateTimeLeft());
    const timer = setInterval(() => setTimeLeft(calculateTimeLeft()), 1000);
    return () => clearInterval(timer);
  }, [item.auction_end_date]);

  const isUrgent = timeLeft.includes('m') && !timeLeft.includes('h') && !timeLeft.includes('d');

  return (
    <Card 
      className={`card-hover-pop cursor-pointer overflow-hidden border-0 shadow-lg bg-white transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
      style={{ transitionDelay: `${index * 100}ms` }}
      onClick={() => navigate(`/listing/${item.id}`)}
    >
      <div className="relative h-48 overflow-hidden bg-slate-100">
        {item.images?.[0] ? (
          <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
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
          LIVE
        </div>
      </div>
      
      <CardContent className="p-5">
        <h3 className="font-semibold text-lg mb-3 line-clamp-1 text-slate-900">{item.title}</h3>
        <div className="flex justify-between items-end">
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider">Current Bid</p>
            <p className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
              ${item.current_price?.toFixed(2)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-500">{item.total_bids || 0} bids</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ========== HOT ITEMS SECTION ==========
const HotItemsSection = ({ items, navigate }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-20 px-4 bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white relative overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500 rounded-full blur-[150px]" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500 rounded-full blur-[150px]" />
      </div>

      <div className="relative max-w-7xl mx-auto">
        <div className={`flex items-center justify-between mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <div className="flex items-center gap-4">
            <div className="p-3 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl shadow-lg shadow-orange-500/30">
              <Flame className="h-8 w-8 text-white" />
            </div>
            <div>
              <h2 className="text-3xl md:text-4xl font-bold">Hot Items</h2>
              <p className="text-blue-200/70">Trending auctions with the most activity</p>
            </div>
          </div>
          <Button onClick={() => navigate('/marketplace?sort=hot')} variant="outline" className="hidden md:flex border-2 border-white/20 text-white hover:bg-white/10">
            View All <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((item, index) => (
            <Card 
              key={item.id}
              className={`hover-glow-cyan cursor-pointer overflow-hidden bg-white/10 backdrop-blur-sm border border-white/10 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${index * 100}ms` }}
              onClick={() => navigate(`/listing/${item.id}`)}
            >
              <div className="relative h-52 overflow-hidden">
                {item.images?.[0] ? (
                  <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-700 to-slate-800">
                    <span className="text-5xl">📦</span>
                  </div>
                )}
                <Badge className="absolute top-3 right-3 bg-gradient-to-r from-orange-500 to-red-500 text-white border-0 shadow-lg">
                  🔥 {item.views || 0} views
                </Badge>
                
                {/* Activity Indicator */}
                <div className="absolute bottom-3 left-3 right-3">
                  <div className="bg-slate-900/80 backdrop-blur rounded-lg px-3 py-2 flex items-center gap-2">
                    <span className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
                    <span className="text-xs text-white/80">Active bidding</span>
                  </div>
                </div>
              </div>
              
              <CardContent className="p-5">
                <h3 className="font-semibold text-lg mb-3 line-clamp-1 text-white">{item.title}</h3>
                <div className="flex justify-between items-end">
                  <div>
                    <p className="text-xs text-blue-200/60 uppercase tracking-wider">Current Bid</p>
                    <p className="text-2xl font-bold text-cyan-400">${item.current_price?.toFixed(2)}</p>
                  </div>
                  <Button size="sm" className="bg-cyan-500 hover:bg-cyan-400 text-slate-900 font-semibold">
                    Bid Now
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

// ========== FEATURED SECTION ==========
const FeaturedSection = ({ items, navigate }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-16 px-4 bg-white">
      <div className="max-w-7xl mx-auto">
        <div className={`text-center mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Badge className="bg-gradient-to-r from-blue-600 to-cyan-500 text-white border-0 mb-4 px-4 py-2">
            <Sparkles className="h-4 w-4 mr-2 inline" />
            Featured
          </Badge>
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">Curated Auctions</h2>
          <p className="text-slate-600 max-w-2xl mx-auto">Hand-picked items from our top sellers</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          {items.slice(0, 8).map((item, index) => (
            <Card 
              key={item.id}
              className={`card-hover-pop cursor-pointer overflow-hidden border-0 shadow-md transition-all duration-700 ${isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}
              style={{ transitionDelay: `${index * 50}ms` }}
              onClick={() => navigate(`/listing/${item.id}`)}
            >
              <div className="relative aspect-square overflow-hidden bg-slate-100">
                {item.images?.[0] ? (
                  <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
                    <span className="text-4xl">📦</span>
                  </div>
                )}
              </div>
              <CardContent className="p-4">
                <h3 className="font-medium text-sm mb-2 line-clamp-1 text-slate-900">{item.title}</h3>
                <p className="text-lg font-bold text-blue-600">${item.current_price?.toFixed(2)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

// ========== NEW LISTINGS SECTION ==========
const NewListingsSection = ({ items, navigate }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  if (!items.length) return null;

  return (
    <section ref={ref} className="py-16 px-4 bg-slate-50">
      <div className="max-w-7xl mx-auto">
        <div className={`flex items-center justify-between mb-10 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <div>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900">🆕 Just Listed</h2>
            <p className="text-slate-600 mt-2">Fresh auctions added today</p>
          </div>
          <Button onClick={() => navigate('/marketplace?sort=newest')} variant="outline" className="hidden md:flex border-2 border-slate-300 hover:border-cyan-500 hover:text-cyan-600">
            View All <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {items.slice(0, 6).map((item, index) => (
            <Card 
              key={item.id}
              className={`card-hover-pop cursor-pointer overflow-hidden border-0 shadow-md transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${index * 80}ms` }}
              onClick={() => navigate(`/listing/${item.id}`)}
            >
              <div className="relative aspect-square overflow-hidden bg-slate-100">
                {item.images?.[0] ? (
                  <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
                    <span className="text-3xl">📦</span>
                  </div>
                )}
                <Badge className="absolute top-2 left-2 bg-green-500 text-white text-xs border-0">NEW</Badge>
              </div>
              <CardContent className="p-3">
                <h3 className="font-medium text-xs mb-1 line-clamp-1 text-slate-900">{item.title}</h3>
                <p className="text-sm font-bold text-blue-600">${item.current_price?.toFixed(2)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

// ========== FEATURES SECTION ==========
const FeaturesSection = ({ navigate }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  const features = [
    { icon: <Gavel className="h-7 w-7" />, title: 'Live Bidding', desc: 'Real-time auctions with instant updates' },
    { icon: <Shield className="h-7 w-7" />, title: 'Secure Payments', desc: 'Bank-level encryption via Stripe' },
    { icon: <Trophy className="h-7 w-7" />, title: 'Buyer Protection', desc: 'Full refund guarantee on disputes' },
    { icon: <Users className="h-7 w-7" />, title: 'Global Community', desc: 'Verified buyers and sellers worldwide' }
  ];

  return (
    <section ref={ref} className="py-20 px-4 bg-white">
      <div className="max-w-7xl mx-auto">
        <div className={`text-center mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">Why Choose BidVex?</h2>
          <p className="text-slate-600">The trusted platform for smart bidders</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <div 
              key={index}
              className={`group p-8 rounded-2xl bg-gradient-to-br from-slate-50 to-white border border-slate-100 hover:border-cyan-200 hover:shadow-xl hover:shadow-cyan-500/10 transition-all duration-500 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${index * 100}ms` }}
            >
              <div className="w-14 h-14 mb-5 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/30 group-hover:scale-110 transition-transform">
                {feature.icon}
              </div>
              <h3 className="text-xl font-semibold text-slate-900 mb-2">{feature.title}</h3>
              <p className="text-slate-600 leading-relaxed">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ========== TOP SELLERS SECTION ==========
const TopSellersSection = ({ sellers }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  return (
    <section ref={ref} className="py-20 px-4 bg-slate-50">
      <div className="max-w-7xl mx-auto">
        <div className={`text-center mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Badge className="bg-yellow-100 text-yellow-700 border-yellow-200 mb-4"><Award className="h-4 w-4 mr-2 inline" />Top Performers</Badge>
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900">Our Best Sellers</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {sellers.slice(0, 3).map((seller, idx) => (
            <Card 
              key={seller.user?.id || idx} 
              className={`card-hover-pop overflow-hidden border-0 shadow-lg transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${idx * 150}ms` }}
            >
              <CardContent className="p-8 text-center">
                <div className="relative inline-block mb-6">
                  {seller.user?.picture ? (
                    <img src={seller.user.picture} alt={seller.user.name} className="w-24 h-24 rounded-full mx-auto ring-4 ring-slate-100" />
                  ) : (
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white text-3xl font-bold mx-auto ring-4 ring-slate-100">
                      {seller.user?.name?.charAt(0) || 'S'}
                    </div>
                  )}
                  {idx === 0 && (
                    <div className="absolute -top-2 -right-2 w-10 h-10 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center text-white shadow-lg">
                      🏆
                    </div>
                  )}
                </div>
                <h3 className="font-bold text-xl mb-4 text-slate-900">{seller.user?.name || 'Top Seller'}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 rounded-xl p-4">
                    <p className="text-xs text-slate-500 uppercase tracking-wider">Total Sales</p>
                    <p className="text-xl font-bold text-green-600">${seller.total_sales?.toFixed(0)}</p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-4">
                    <p className="text-xs text-slate-500 uppercase tracking-wider">Items Sold</p>
                    <p className="text-xl font-bold text-slate-700">{seller.items_sold}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

// ========== HOW IT WORKS SECTION ==========
const HowItWorksSection = ({ navigate }) => {
  const [ref, isVisible] = useScrollReveal(0.1);

  const steps = [
    { icon: <Search className="h-7 w-7" />, title: 'Browse', desc: 'Find unique items from trusted sellers' },
    { icon: <Gavel className="h-7 w-7" />, title: 'Bid', desc: 'Place competitive bids in real-time' },
    { icon: <Trophy className="h-7 w-7" />, title: 'Win', desc: 'Secure your items with safe payment' }
  ];

  return (
    <section ref={ref} className="py-20 px-4 bg-gradient-to-br from-blue-900 via-slate-900 to-slate-900 text-white relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-cyan-500 rounded-full blur-[200px]" />
      </div>

      <div className="relative max-w-5xl mx-auto text-center">
        <div className={`mb-12 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Badge className="bg-white/10 backdrop-blur text-white border-cyan-400/30 mb-4">Getting Started</Badge>
          <h2 className="text-3xl md:text-5xl font-bold mb-4">How It Works</h2>
          <p className="text-blue-200/70 max-w-2xl mx-auto">Start winning amazing deals in three simple steps</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {steps.map((step, index) => (
            <div 
              key={index}
              className={`relative transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              style={{ transitionDelay: `${(index + 1) * 150}ms` }}
            >
              <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/10 hover:bg-white/15 hover:border-cyan-400/30 transition-all">
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 bg-cyan-500 rounded-full flex items-center justify-center text-sm font-bold shadow-lg shadow-cyan-500/50">
                  {index + 1}
                </div>
                <div className="w-16 h-16 mx-auto mb-5 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/30">
                  {step.icon}
                </div>
                <h3 className="text-xl font-bold mb-3">{step.title}</h3>
                <p className="text-blue-200/70">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={`transition-all duration-700 delay-500 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <Button 
            onClick={() => navigate('/how-it-works')}
            className="btn-shine bg-gradient-to-r from-cyan-500 to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-slate-900 font-bold px-10 py-6 text-lg shadow-xl shadow-cyan-500/30"
          >
            Learn More
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </div>
    </section>
  );
};

export default HomePage;
