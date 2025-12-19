import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  ArrowRight, Gavel, TrendingUp, Shield, Users, Award, Flame, 
  Search, Trophy, CreditCard, Sparkles, Clock, CheckCircle2 
} from 'lucide-react';
import HomepageBanner from '../components/HomepageBanner';
import AuctionCarousel from '../components/AuctionCarousel';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
  const [recentlyViewed, setRecentlyViewed] = useState([]);

  useEffect(() => {
    fetchTopSellers();
    fetchHotItems();
    fetchEndingSoon();
    fetchFeatured();
    fetchNewListings();
    fetchRecentlySold();
    if (user) {
      fetchRecentlyViewed();
    }
  }, [user]);

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

  const fetchRecentlyViewed = async () => {
    try {
      const response = await axios.get(`${API}/tracking/recently-viewed?limit=12`);
      setRecentlyViewed(response.data);
    } catch (error) {
      console.error('Failed to fetch recently viewed:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white" data-testid="home-page">
      {/* Modern Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white">
        {/* Animated background pattern */}
        <div className="absolute inset-0 opacity-20">
          <div className="absolute inset-0" style={{
            backgroundImage: `radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)`,
            backgroundSize: '40px 40px'
          }} />
        </div>
        
        {/* Gradient orbs */}
        <div className="absolute top-10 left-10 w-72 h-72 bg-blue-500/30 rounded-full blur-[100px]" />
        <div className="absolute bottom-10 right-10 w-96 h-96 bg-purple-500/20 rounded-full blur-[120px]" />
        
        <div className="relative max-w-7xl mx-auto px-4 py-20 md:py-28">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <Badge className="bg-white/10 backdrop-blur-sm text-white border-white/20 text-sm px-4 py-2 w-fit">
                <Sparkles className="h-4 w-4 mr-2 inline" />
                #1 Trusted Auction Platform
              </Badge>
              
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight">
                Discover. Bid.
                <span className="block bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
                  Win Amazing Deals.
                </span>
              </h1>
              
              <p className="text-lg md:text-xl text-blue-100/80 max-w-lg leading-relaxed">
                Join thousands of savvy bidders on BidVex. Find unique items, place competitive bids, 
                and win incredible deals with our secure auction platform.
              </p>
              
              <div className="flex flex-col sm:flex-row gap-4">
                <Button 
                  onClick={() => navigate('/marketplace')}
                  className="bg-white text-slate-900 hover:bg-blue-50 px-8 py-6 text-lg font-semibold shadow-xl hover:shadow-2xl transition-all"
                >
                  Browse Auctions
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
                <Button 
                  onClick={() => navigate('/how-it-works')}
                  variant="outline"
                  className="border-2 border-white/30 text-white hover:bg-white/10 px-8 py-6 text-lg"
                >
                  How It Works
                </Button>
              </div>

              {/* Trust indicators */}
              <div className="flex flex-wrap items-center gap-6 pt-4 text-sm text-blue-200/80">
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-green-400" />
                  <span>Secure Payments</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                  <span>Verified Sellers</span>
                </div>
                <div className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-yellow-400" />
                  <span>Buyer Protection</span>
                </div>
              </div>
            </div>

            {/* Stats cards */}
            <div className="hidden md:grid grid-cols-2 gap-4">
              {[
                { value: '50K+', label: 'Active Users', icon: <Users className="h-6 w-6" /> },
                { value: '10K+', label: 'Daily Auctions', icon: <Gavel className="h-6 w-6" /> },
                { value: '$2M+', label: 'Items Sold', icon: <TrendingUp className="h-6 w-6" /> },
                { value: '99.9%', label: 'Uptime', icon: <Shield className="h-6 w-6" /> }
              ].map((stat, i) => (
                <div key={i} className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/10 hover:bg-white/15 transition-all">
                  <div className="text-blue-400 mb-3">{stat.icon}</div>
                  <div className="text-3xl font-bold text-white">{stat.value}</div>
                  <div className="text-blue-200/70">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Wave divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 120L60 110C120 100 240 80 360 70C480 60 600 60 720 65C840 70 960 80 1080 85C1200 90 1320 90 1380 90L1440 90V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0Z" fill="rgb(248 250 252)" />
          </svg>
        </div>
      </section>

      {/* Homepage Banner Carousel */}
      <section className="py-8 px-4">
        <div className="max-w-7xl mx-auto">
          <HomepageBanner />
        </div>
      </section>

      {/* Auction Carousels */}
      <div className="space-y-0">
        {/* Ending Soon Carousel */}
        {endingSoon.length > 0 && (
          <section className="py-12 px-4">
            <div className="max-w-7xl mx-auto">
              <AuctionCarousel 
                title="⏰ Ending Soon" 
                items={endingSoon}
                type="auction"
              />
            </div>
          </section>
        )}

        {/* Featured Auctions Carousel */}
        {featured.length > 0 && (
          <section className="py-12 px-4 bg-gradient-to-r from-slate-50 via-blue-50/50 to-slate-50">
            <div className="max-w-7xl mx-auto">
              <AuctionCarousel 
                title="✨ Featured Auctions" 
                items={featured}
                type="auction"
              />
            </div>
          </section>
        )}

        {/* New Listings Carousel */}
        {newListings.length > 0 && (
          <section className="py-12 px-4">
            <div className="max-w-7xl mx-auto">
              <AuctionCarousel 
                title="🆕 New Listings" 
                items={newListings}
                type="auction"
              />
            </div>
          </section>
        )}

        {/* Recently Sold Carousel */}
        {recentlySold.length > 0 && (
          <section className="py-12 px-4 bg-gradient-to-r from-slate-50 via-purple-50/30 to-slate-50">
            <div className="max-w-7xl mx-auto">
              <AuctionCarousel 
                title="💰 Recently Sold" 
                items={recentlySold}
                type="auction"
              />
            </div>
          </section>
        )}

        {/* Recently Viewed Carousel - Only for logged-in users */}
        {user && recentlyViewed.length > 0 && (
          <section className="py-12 px-4">
            <div className="max-w-7xl mx-auto">
              <AuctionCarousel 
                title="👁️ Recently Viewed" 
                items={recentlyViewed}
                type="auction"
              />
            </div>
          </section>
        )}
      </div>

      {/* Hot Items Section - Modern Grid */}
      {hotItems.length > 0 && (
        <section className="py-20 px-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold text-slate-900 flex items-center gap-3">
                  <Flame className="h-8 w-8 text-orange-500" />
                  Hot Items
                </h2>
                <p className="text-slate-600 mt-2">Trending auctions everyone is watching</p>
              </div>
              <Button onClick={() => navigate('/marketplace')} variant="outline" className="hidden md:flex">
                View All
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {hotItems.map(item => (
                <Card 
                  key={item.id} 
                  className="group cursor-pointer overflow-hidden border-0 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-1" 
                  onClick={() => navigate(`/listing/${item.id}`)}
                >
                  <div className="relative h-52 overflow-hidden bg-slate-100">
                    {item.images && item.images[0] ? (
                      <img 
                        src={item.images[0]} 
                        alt={item.title} 
                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" 
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
                        <span className="text-5xl">📦</span>
                      </div>
                    )}
                    <Badge className="absolute top-3 right-3 bg-orange-500 text-white border-0 shadow-lg">
                      🔥 Hot
                    </Badge>
                  </div>
                  <CardContent className="p-5">
                    <h3 className="font-semibold text-lg mb-3 line-clamp-1 text-slate-900">{item.title}</h3>
                    <div className="flex justify-between items-end">
                      <div>
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Current Bid</p>
                        <p className="text-2xl font-bold text-blue-600">${item.current_price?.toFixed(2)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Views</p>
                        <p className="text-lg font-semibold text-slate-700">{item.views}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            <div className="text-center mt-8 md:hidden">
              <Button onClick={() => navigate('/marketplace')} variant="outline">
                View All Hot Items
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        </section>
      )}

      {/* Features Section */}
      <section className="py-20 px-4 bg-slate-900 text-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Why Choose BidVex?</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">The trusted platform for buyers and sellers worldwide</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <FeatureCard 
              icon={<Gavel className="h-7 w-7" />}
              title="Live Auctions"
              description="Real-time bidding with instant updates and notifications"
            />
            <FeatureCard 
              icon={<TrendingUp className="h-7 w-7" />}
              title="Best Deals"
              description="Competitive pricing for buyers and great returns for sellers"
            />
            <FeatureCard 
              icon={<Shield className="h-7 w-7" />}
              title="Secure Payments"
              description="Bank-level encryption with Stripe protection"
            />
            <FeatureCard 
              icon={<Users className="h-7 w-7" />}
              title="Global Community"
              description="Connect with verified buyers and sellers worldwide"
            />
          </div>
        </div>
      </section>

      {/* Top Sellers Section */}
      {topSellers.length > 0 && (
        <section className="py-20 px-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold text-slate-900 flex items-center gap-3">
                  <Award className="h-8 w-8 text-yellow-500" />
                  Top Sellers
                </h2>
                <p className="text-slate-600 mt-2">Meet our highest performing sellers</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {topSellers.slice(0, 3).map((seller, idx) => (
                <Card key={seller.user?.id || idx} className="overflow-hidden border-0 shadow-lg hover:shadow-xl transition-all">
                  <CardContent className="p-8 text-center">
                    <div className="relative inline-block mb-6">
                      {seller.user?.picture ? (
                        <img src={seller.user.picture} alt={seller.user.name} className="w-24 h-24 rounded-full mx-auto ring-4 ring-slate-100" />
                      ) : (
                        <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center text-white text-3xl font-bold mx-auto ring-4 ring-slate-100">
                          {seller.user?.name?.charAt(0) || 'S'}
                        </div>
                      )}
                      {idx === 0 && (
                        <Badge className="absolute -top-1 -right-1 bg-yellow-500 text-white border-0 shadow-lg px-3">
                          🏆 #1
                        </Badge>
                      )}
                    </div>
                    <h3 className="font-bold text-xl mb-4 text-slate-900">{seller.user?.name || 'Top Seller'}</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-50 rounded-xl p-4">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Total Sales</p>
                        <p className="text-xl font-bold text-green-600">${seller.total_sales?.toFixed(2)}</p>
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
      )}

      {/* How It Works Summary - Modern Style */}
      <section className="py-20 px-4 bg-gradient-to-br from-slate-50 to-blue-50">
        <div className="max-w-4xl mx-auto text-center">
          <Badge className="bg-blue-100 text-blue-700 mb-4">Getting Started</Badge>
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">How It Works</h2>
          <p className="text-slate-600 mb-12 max-w-2xl mx-auto">
            Start winning amazing deals in just three simple steps
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <StepCard 
              number="1" 
              icon={<Search className="h-6 w-6" />}
              title="Browse" 
              description="Explore thousands of unique items from trusted sellers" 
            />
            <StepCard 
              number="2" 
              icon={<Gavel className="h-6 w-6" />}
              title="Bid" 
              description="Place competitive bids or use Buy Now for instant purchase" 
            />
            <StepCard 
              number="3" 
              icon={<Trophy className="h-6 w-6" />}
              title="Win" 
              description="Secure your items with safe, encrypted payments" 
            />
          </div>
          
          <div className="mt-12">
            <Button 
              onClick={() => navigate('/how-it-works')}
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white px-8 py-6 text-lg font-semibold shadow-lg shadow-blue-500/30"
            >
              Learn More
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
};

// Feature Card Component - Modern Style
const FeatureCard = ({ icon, title, description }) => (
  <div className="p-8 rounded-2xl bg-white/5 backdrop-blur border border-white/10 hover:bg-white/10 transition-all text-center">
    <div className="w-14 h-14 mx-auto mb-5 rounded-xl bg-blue-600/20 flex items-center justify-center text-blue-400">
      {icon}
    </div>
    <h3 className="text-xl font-semibold mb-3">{title}</h3>
    <p className="text-slate-400 leading-relaxed">{description}</p>
  </div>
);

// Step Card Component - Modern Style with Icons
const StepCard = ({ number, icon, title, description }) => (
  <div className="relative group">
    <div className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border border-slate-100">
      <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center text-white shadow-lg shadow-blue-500/30">
        {icon}
      </div>
      <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-slate-900 text-white text-sm font-bold flex items-center justify-center">
        {number}
      </div>
      <h3 className="text-xl font-bold text-slate-900 mb-3">{title}</h3>
      <p className="text-slate-600 leading-relaxed">{description}</p>
    </div>
  </div>
);

export default HomePage;
