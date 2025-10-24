import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Search, ArrowRight, Clock } from 'lucide-react';
import axios from 'axios';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const HeroBanner = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [nextAuction, setNextAuction] = useState(null);

  useEffect(() => {
    fetchNextAuction();
  }, []);

  const fetchNextAuction = async () => {
    try {
      const response = await axios.get(`${API}/listings?status=active&sort=auction_end_date&limit=1`);
      if (response.data && response.data.length > 0) {
        setNextAuction(response.data[0]);
      }
    } catch (error) {
      console.error('Failed to fetch next auction:', error);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/marketplace?search=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <section className="relative min-h-[600px] md:min-h-[700px] px-4 py-20 overflow-hidden">
      {/* Animated Gradient Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-teal-500/10 animate-gradient-shift"></div>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(120,119,198,0.3),rgba(255,255,255,0))]"></div>
      
      {/* Animated Background Shapes */}
      <motion.div
        className="absolute top-20 left-10 w-64 h-64 bg-primary/10 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      />
      <motion.div
        className="absolute bottom-20 right-10 w-96 h-96 bg-accent/10 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.3, 0.6, 0.3],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 1
        }}
      />

      <div className="max-w-6xl mx-auto relative z-10">
        <div className="text-center space-y-8">
          {/* Kinetic Typography Headline */}
          <motion.h1
            className="text-5xl sm:text-6xl lg:text-7xl font-bold leading-tight"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <motion.span
              className="inline-block bg-gradient-to-r from-primary via-purple-600 to-accent bg-clip-text text-transparent"
              animate={{
                backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
              }}
              transition={{
                duration: 5,
                repeat: Infinity,
                ease: "linear"
              }}
              style={{
                backgroundSize: '200% auto',
              }}
            >
              Discover
            </motion.span>{' '}
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="inline-block"
            >
              Unique
            </motion.span>{' '}
            <motion.span
              initial={{ opacity: 0, rotateX: -90 }}
              animate={{ opacity: 1, rotateX: 0 }}
              transition={{ delay: 0.5, duration: 0.6 }}
              className="inline-block"
            >
              Treasures
            </motion.span>
          </motion.h1>

          {/* Subline */}
          <motion.p
            className="text-xl sm:text-2xl text-muted-foreground max-w-3xl mx-auto font-medium"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7, duration: 0.6 }}
          >
            Bid on rare finds, trusted listings, and exclusive deals — all in one secure marketplace.
          </motion.p>

          {/* Integrated Search Bar */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.9, duration: 0.5 }}
            className="max-w-2xl mx-auto"
          >
            <form onSubmit={handleSearch} className="relative">
              <div className="relative flex items-center">
                <Search className="absolute left-4 h-5 w-5 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search for items, categories, or sellers..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-12 pr-32 py-6 text-lg rounded-full border-2 shadow-lg focus:shadow-xl transition-shadow"
                />
                <Button
                  type="submit"
                  className="absolute right-2 gradient-button text-white border-0 rounded-full px-6"
                >
                  Search
                </Button>
              </div>
            </form>
          </motion.div>

          {/* CTA Buttons */}
          <motion.div
            className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.1, duration: 0.5 }}
          >
            <Button
              className="gradient-button text-white border-0 text-lg px-8 py-6 rounded-full shadow-lg hover:shadow-xl transition-shadow group"
              onClick={() => navigate('/marketplace')}
            >
              Browse Auctions
              <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button
              variant="outline"
              className="text-lg px-8 py-6 rounded-full border-2 shadow-lg hover:shadow-xl transition-shadow"
              onClick={() => navigate('/how-it-works')}
            >
              How Bidding Works
            </Button>
          </motion.div>

          {/* Countdown Ticker for Next Auction */}
          {nextAuction && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.3, duration: 0.5 }}
              className="mt-12 inline-flex items-center gap-3 px-6 py-4 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md rounded-full shadow-xl border border-gray-200 dark:border-gray-700"
            >
              <Clock className="h-5 w-5 text-primary animate-pulse" />
              <span className="text-sm font-medium text-muted-foreground">
                Next auction ends in:
              </span>
              <Countdown
                date={new Date(nextAuction.auction_end_date)}
                renderer={({ days, hours, minutes, seconds }) => (
                  <span className="font-bold text-lg gradient-text">
                    {days > 0 && `${days}d `}
                    {hours}h {minutes}m
                  </span>
                )}
              />
              <Button
                size="sm"
                variant="ghost"
                className="ml-2 text-primary hover:text-primary"
                onClick={() => navigate(`/listing/${nextAuction.id}`)}
              >
                View Auction →
              </Button>
            </motion.div>
          )}
        </div>
      </div>

      {/* Custom CSS for gradient animation */}
      <style jsx>{`
        @keyframes gradient-shift {
          0%, 100% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
        }
        .animate-gradient-shift {
          background-size: 200% 200%;
          animation: gradient-shift 15s ease infinite;
        }
      `}</style>
    </section>
  );
};

export default HeroBanner;
