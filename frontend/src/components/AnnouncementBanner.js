import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Info, AlertTriangle, CheckCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AnnouncementBanner = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [dismissedIds, setDismissedIds] = useState([]);

  useEffect(() => {
    // Load dismissed IDs from localStorage
    const dismissed = JSON.parse(localStorage.getItem('dismissedAnnouncements') || '[]');
    setDismissedIds(dismissed);
    
    fetchAnnouncements();
  }, []);

  const fetchAnnouncements = async () => {
    try {
      const response = await axios.get(`${API}/announcements/active`);
      setAnnouncements(response.data || []);
    } catch (error) {
      console.error('Failed to fetch announcements:', error);
    }
  };

  const handleDismiss = (announcementId) => {
    const newDismissed = [...dismissedIds, announcementId];
    setDismissedIds(newDismissed);
    localStorage.setItem('dismissedAnnouncements', JSON.stringify(newDismissed));
  };

  // Filter out dismissed announcements
  const visibleAnnouncements = announcements.filter(
    announcement => !dismissedIds.includes(announcement.id)
  );

  if (visibleAnnouncements.length === 0) {
    return null;
  }

  const getAnnouncementStyle = (type) => {
    switch (type) {
      case 'warning':
        return {
          bg: 'bg-yellow-500 dark:bg-yellow-600',
          text: 'text-white',
          icon: <AlertTriangle className="h-5 w-5 flex-shrink-0" />
        };
      case 'success':
        return {
          bg: 'bg-green-500 dark:bg-green-600',
          text: 'text-white',
          icon: <CheckCircle className="h-5 w-5 flex-shrink-0" />
        };
      case 'info':
      default:
        return {
          bg: 'bg-blue-600 dark:bg-blue-700',
          text: 'text-white',
          icon: <Info className="h-5 w-5 flex-shrink-0" />
        };
    }
  };

  return (
    <div className="w-full space-y-2 mb-4">
      {visibleAnnouncements.map((announcement) => {
        const style = getAnnouncementStyle(announcement.type || 'info');
        
        return (
          <div
            key={announcement.id}
            className={`${style.bg} ${style.text} px-4 py-3 md:px-6 md:py-4 shadow-lg relative animate-slideDown`}
            role="alert"
          >
            <div className="max-w-7xl mx-auto flex items-start gap-3">
              {/* Icon */}
              <div className="mt-0.5">
                {style.icon}
              </div>
              
              {/* Content */}
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-base md:text-lg mb-1">
                  {announcement.title}
                </h3>
                <p className="text-sm md:text-base opacity-95 leading-relaxed">
                  {announcement.message}
                </p>
              </div>
              
              {/* Dismiss Button */}
              <button
                onClick={() => handleDismiss(announcement.id)}
                className="p-1 hover:bg-white/20 rounded-full transition-colors flex-shrink-0"
                aria-label="Dismiss announcement"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default AnnouncementBanner;
