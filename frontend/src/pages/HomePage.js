import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ArrowRight, Gavel, TrendingUp, Shield, Users, Award, Flame } from 'lucide-react';
import Countdown from 'react-countdown';
import HeroBanner from '../components/HeroBanner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const HomePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [topSellers, setTopSellers] = useState([]);
  const [hotItems, setHotItems] = useState([]);

  useEffect(() => {
    fetchTopSellers();
    fetchHotItems();
  }, []);

  const fetchTopSellers = async () => {
    try {
      const response = await axios.get(`${API}/stats/top-sellers?limit=3`);
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

  return (
    <div className="min-h-screen" data-testid="home-page">
      {/* Enhanced Hero Banner */}
      <HeroBanner />

      <section className="py-20 px-4 bg-white/50 dark:bg-gray-800/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <FeatureCard 
              icon={<Gavel className="h-8 w-8" />}
              title="Live Auctions"
              description="Real-time bidding with instant updates"
            />
            <FeatureCard 
              icon={<TrendingUp className="h-8 w-8" />}
              title="Best Deals"
              description="Competitive pricing for buyers and sellers"
            />
            <FeatureCard 
              icon={<Shield className="h-8 w-8" />}
              title="Secure Payments"
              description="Protected transactions with Stripe"
            />
            <FeatureCard 
              icon={<Users className="h-8 w-8" />}
              title="Global Community"
              description="Connect with buyers worldwide"
            />
          </div>
        </div>
      </section>

      {topSellers.length > 0 && (
        <section className="py-20 px-4 bg-white/50 dark:bg-gray-800/50">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold flex items-center gap-3">
                  <Award className="h-8 w-8 text-yellow-500" />
                  Top Sellers
                </h2>
                <p className="text-muted-foreground mt-2">Meet our highest performing sellers</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {topSellers.map((seller, idx) => (
                <Card key={seller.user.id} className="glassmorphism card-hover">
                  <CardContent className="p-6 text-center">
                    <div className="relative inline-block mb-4">
                      {seller.user.picture ? (
                        <img src={seller.user.picture} alt={seller.user.name} className="w-24 h-24 rounded-full mx-auto" />
                      ) : (
                        <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white text-2xl font-bold mx-auto">
                          {seller.user.name.charAt(0)}
                        </div>
                      )}
                      {idx === 0 && <Badge className="absolute -top-2 -right-2 bg-yellow-500 text-white">🏆 #1</Badge>}
                    </div>
                    <h3 className="font-bold text-lg mb-2">{seller.user.name}</h3>
                    <div className="space-y-1 text-sm">
                      <p className="text-muted-foreground">Total Sales: <span className="font-bold text-green-600">${seller.total_sales.toFixed(2)}</span></p>
                      <p className="text-muted-foreground">Items Sold: <span className="font-bold">{seller.items_sold}</span></p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      {hotItems.length > 0 && (
        <section className="py-20 px-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold flex items-center gap-3">
                  <Flame className="h-8 w-8 text-orange-500" />
                  Hot Items
                </h2>
                <p className="text-muted-foreground mt-2">Trending auctions everyone is watching</p>
              </div>
              <Button onClick={() => navigate('/marketplace')} variant="outline">View All</Button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {hotItems.map(item => (
                <Card key={item.id} className="card-hover cursor-pointer glassmorphism" onClick={() => navigate(`/listing/${item.id}`)}>
                  <div className="relative h-48 overflow-hidden bg-gray-100 rounded-t-lg">
                    {item.images && item.images[0] ? (
                      <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/10 to-accent/10">
                        <span className="text-4xl">📦</span>
                      </div>
                    )}
                    <Badge className="absolute top-2 right-2 bg-orange-500 text-white">🔥 Hot</Badge>
                  </div>
                  <CardContent className="p-4">
                    <h3 className="font-semibold mb-2 line-clamp-1">{item.title}</h3>
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-xs text-muted-foreground">Current Bid</p>
                        <p className="text-lg font-bold gradient-text">${item.current_price.toFixed(2)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-muted-foreground">Views</p>
                        <p className="font-semibold">{item.views}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <h2 className="text-3xl md:text-4xl font-bold">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8">
            <Step number="1" title="Browse" description="Explore unique items from trusted sellers" />
            <Step number="2" title="Bid" description="Place competitive bids or buy instantly" />
            <Step number="3" title="Win" description="Secure your purchase with safe payments" />
          </div>
        </div>
      </section>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => (
  <div className="p-6 rounded-2xl glassmorphism card-hover text-center space-y-3">
    <div className="gradient-bg w-16 h-16 rounded-xl flex items-center justify-center text-white mx-auto">
      {icon}
    </div>
    <h3 className="text-xl font-semibold">{title}</h3>
    <p className="text-muted-foreground text-sm">{description}</p>
  </div>
);

const Step = ({ number, title, description }) => (
  <div className="space-y-3">
    <div className="gradient-bg w-12 h-12 rounded-full flex items-center justify-center text-white text-xl font-bold mx-auto">
      {number}
    </div>
    <h3 className="text-lg font-semibold">{title}</h3>
    <p className="text-muted-foreground text-sm">{description}</p>
  </div>
);

export default HomePage;
