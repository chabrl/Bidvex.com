import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, ChevronLeft, ChevronRight, Bell, Sparkles, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TrendyAnnouncementBar = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const [dismissedIds, setDismissedIds] = useState([]);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    const dismissed = JSON.parse(localStorage.getItem('dismissedAnnouncements') || '[]');
    setDismissedIds(dismissed);
    fetchAnnouncements();
  }, []);

  const fetchAnnouncements = async () => {
    try {
      const response = await axios.get(`${API}/announcements/active`);
      const data = response.data || [];
      setAnnouncements(data);
      if (data.length > 0) {
        setIsVisible(true);
      }
    } catch (error) {
      console.error('Failed to fetch announcements:', error);
    }
  };

  // Auto-rotate announcements every 5 seconds
  useEffect(() => {
    if (visibleAnnouncements.length <= 1 || isPaused) return;
    
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % visibleAnnouncements.length);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [visibleAnnouncements.length, isPaused]);

  const handleDismiss = (announcementId) => {
    const newDismissed = [...dismissedIds, announcementId];
    setDismissedIds(newDismissed);
    localStorage.setItem('dismissedAnnouncements', JSON.stringify(newDismissed));
    
    // If all dismissed, hide bar
    if (newDismissed.length >= announcements.length) {
      setIsVisible(false);
    }
  };

  const handleDismissAll = () => {
    const allIds = announcements.map(a => a.id);
    setDismissedIds(allIds);
    localStorage.setItem('dismissedAnnouncements', JSON.stringify(allIds));
    setIsVisible(false);
  };

  const nextAnnouncement = () => {
    setCurrentIndex((prev) => (prev + 1) % visibleAnnouncements.length);
    setIsPaused(true);
    setTimeout(() => setIsPaused(false), 10000); // Pause auto-rotate for 10s
  };

  const prevAnnouncement = () => {
    setCurrentIndex((prev) => (prev - 1 + visibleAnnouncements.length) % visibleAnnouncements.length);
    setIsPaused(true);
    setTimeout(() => setIsPaused(false), 10000);
  };

  const visibleAnnouncements = announcements.filter(
    announcement => !dismissedIds.includes(announcement.id)
  );

  if (!isVisible || visibleAnnouncements.length === 0) {
    return null;
  }

  const currentAnnouncement = visibleAnnouncements[currentIndex];

  const getStyle = (type) => {
    switch (type) {
      case 'warning':
        return {
          gradient: 'from-amber-500 via-orange-500 to-red-500',
          icon: <AlertTriangle className="h-5 w-5" />,
          glow: 'shadow-orange-500/50'
        };
      case 'success':
        return {
          gradient: 'from-emerald-500 via-green-500 to-teal-500',
          icon: <CheckCircle className="h-5 w-5" />,
          glow: 'shadow-green-500/50'
        };
      case 'special':
        return {
          gradient: 'from-purple-600 via-pink-500 to-red-500',
          icon: <Sparkles className="h-5 w-5 animate-pulse" />,
          glow: 'shadow-pink-500/50'
        };
      case 'info':
      default:
        return {
          gradient: 'from-blue-600 via-cyan-500 to-blue-700',
          icon: <Info className="h-5 w-5" />,
          glow: 'shadow-blue-500/50'
        };
    }
  };

  const style = getStyle(currentAnnouncement.type || 'info');

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ y: -100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -100, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 100, damping: 20 }}
          className="fixed top-0 left-0 right-0 z-[60] backdrop-blur-sm"
        >
          {/* Glassmorphism Background */}
          <div className={`relative overflow-hidden bg-gradient-to-r ${style.gradient} ${style.glow} shadow-2xl`}>
            {/* Animated Background Pattern */}
            <div className="absolute inset-0 opacity-20">
              <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMC41Ii8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-30"></div>
            </div>

            {/* Content */}
            <div className="relative">
              <div className="max-w-7xl mx-auto px-4 py-3 md:py-4">
                <div className="flex items-center gap-3 md:gap-4">
                  {/* Animated Bell Icon */}
                  <div className="relative flex-shrink-0">
                    <motion.div
                      animate={{ rotate: [0, -15, 15, -10, 10, 0] }}
                      transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 3 }}
                    >
                      <div className="p-2 md:p-2.5 bg-white/20 backdrop-blur-md rounded-full border border-white/30">
                        {style.icon}
                      </div>
                    </motion.div>
                    {visibleAnnouncements.length > 1 && (
                      <div className="absolute -top-1 -right-1 bg-white text-xs font-bold px-1.5 py-0.5 rounded-full text-blue-600 shadow-lg">
                        {visibleAnnouncements.length}
                      </div>
                    )}
                  </div>

                  {/* Message Content with Slide Animation */}
                  <div className="flex-1 min-w-0">
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={currentIndex}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ duration: 0.3 }}
                        className="text-white"
                      >
                        <h4 className="font-bold text-sm md:text-base mb-0.5 flex items-center gap-2">
                          {currentAnnouncement.title}
                          {currentAnnouncement.type === 'special' && (
                            <Sparkles className="h-4 w-4 animate-pulse" />
                          )}
                        </h4>
                        <p className="text-xs md:text-sm opacity-95 line-clamp-2">
                          {currentAnnouncement.message}
                        </p>
                      </motion.div>
                    </AnimatePresence>
                  </div>

                  {/* Navigation Controls (if multiple announcements) */}
                  {visibleAnnouncements.length > 1 && (
                    <div className="hidden md:flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={prevAnnouncement}
                        className="p-1.5 hover:bg-white/20 rounded-full transition-colors"
                        aria-label="Previous announcement"
                      >
                        <ChevronLeft className="h-4 w-4 text-white" />
                      </button>
                      <div className="text-xs text-white/80 font-medium min-w-[40px] text-center">
                        {currentIndex + 1} / {visibleAnnouncements.length}
                      </div>
                      <button
                        onClick={nextAnnouncement}
                        className="p-1.5 hover:bg-white/20 rounded-full transition-colors"
                        aria-label="Next announcement"
                      >
                        <ChevronRight className="h-4 w-4 text-white" />
                      </button>
                    </div>
                  )}

                  {/* Dismiss Buttons */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {visibleAnnouncements.length > 1 && (
                      <button
                        onClick={handleDismissAll}
                        className="hidden md:block px-3 py-1.5 text-xs font-semibold bg-white/20 hover:bg-white/30 backdrop-blur-sm rounded-full transition-colors text-white"
                      >
                        Dismiss All
                      </button>
                    )}
                    <button
                      onClick={() => handleDismiss(currentAnnouncement.id)}
                      className="p-1.5 md:p-2 hover:bg-white/20 rounded-full transition-colors"
                      aria-label="Dismiss announcement"
                    >
                      <X className="h-4 w-4 md:h-5 md:w-5 text-white" />
                    </button>
                  </div>
                </div>

                {/* Progress Dots (if multiple) */}
                {visibleAnnouncements.length > 1 && (
                  <div className="flex justify-center gap-1.5 mt-2 md:hidden">
                    {visibleAnnouncements.map((_, idx) => (
                      <button
                        key={idx}
                        onClick={() => setCurrentIndex(idx)}
                        className={`h-1.5 rounded-full transition-all ${
                          idx === currentIndex 
                            ? 'w-6 bg-white' 
                            : 'w-1.5 bg-white/50 hover:bg-white/70'
                        }`}
                        aria-label={`Go to announcement ${idx + 1}`}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Spacer to prevent content from going under the bar */}
          <div className="h-20 md:h-24"></div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default TrendyAnnouncementBar;
