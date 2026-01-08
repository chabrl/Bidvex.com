/**
 * BidVex Notification Center Component
 * A persistent hub for all platform notifications with the Bell icon
 * 
 * Features:
 * - Bell icon with unread count badge
 * - Slide-out panel with notification list
 * - Categories: Outbid, Auction Ending, New Messages, System
 * - Mark all as read functionality
 * - Click-to-navigate to relevant pages
 * - Real-time updates via socket.io
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Bell, X, Gavel, MessageCircle, Clock, DollarSign, 
  CheckCheck, Trash2, AlertCircle, ShoppingCart, 
  ExternalLink, Sparkles, Volume2, VolumeX
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Notification type icons and colors
const NOTIFICATION_TYPES = {
  outbid: {
    icon: Gavel,
    color: 'text-red-500',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    borderColor: 'border-red-200 dark:border-red-800',
    label: 'Outbid'
  },
  auction_ending: {
    icon: Clock,
    color: 'text-amber-500',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-amber-200 dark:border-amber-800',
    label: 'Ending Soon'
  },
  auction_won: {
    icon: Sparkles,
    color: 'text-green-500',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
    borderColor: 'border-green-200 dark:border-green-800',
    label: 'You Won!'
  },
  new_message: {
    icon: MessageCircle,
    color: 'text-[#06B6D4]',
    bgColor: 'bg-cyan-50 dark:bg-cyan-900/20',
    borderColor: 'border-cyan-200 dark:border-cyan-800',
    label: 'New Message'
  },
  buy_now_purchase: {
    icon: ShoppingCart,
    color: 'text-green-500',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
    borderColor: 'border-green-200 dark:border-green-800',
    label: 'Purchase'
  },
  bid_placed: {
    icon: DollarSign,
    color: 'text-[#1E3A8A]',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    label: 'Bid Placed'
  },
  system: {
    icon: AlertCircle,
    color: 'text-slate-500',
    bgColor: 'bg-slate-50 dark:bg-slate-800/50',
    borderColor: 'border-slate-200 dark:border-slate-700',
    label: 'System'
  }
};

const NotificationCenter = () => {
  const { user, token } = useAuth();
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(() => 
    localStorage.getItem('notificationSound') !== 'false'
  );
  const panelRef = useRef(null);
  const isFrench = i18n.language === 'fr';

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    if (!user || !token) return;
    
    try {
      setLoading(true);
      const response = await axios.get(`${API}/notifications`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotifications(response.data.notifications || []);
      setUnreadCount(response.data.unread_count || 0);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  }, [user, token]);

  // Initial fetch
  useEffect(() => {
    fetchNotifications();
    
    // Poll for new notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close panel on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // Mark all as read
  const markAllAsRead = async () => {
    if (!token) return;
    
    try {
      await axios.post(`${API}/notifications/mark-all-read`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
      toast.success(isFrench ? 'Toutes les notifications lues' : 'All notifications marked as read');
    } catch (error) {
      console.error('Failed to mark all as read:', error);
      toast.error(isFrench ? 'Échec de la mise à jour' : 'Failed to update');
    }
  };

  // Mark single notification as read and navigate
  const handleNotificationClick = async (notification) => {
    // Mark as read
    if (!notification.read) {
      try {
        await axios.post(`${API}/notifications/${notification.id}/read`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setNotifications(prev => 
          prev.map(n => n.id === notification.id ? { ...n, read: true } : n)
        );
        setUnreadCount(prev => Math.max(0, prev - 1));
      } catch (error) {
        console.error('Failed to mark as read:', error);
      }
    }

    // Navigate based on notification type
    const data = notification.data || {};
    setIsOpen(false);
    
    switch (notification.type) {
      case 'outbid':
      case 'auction_ending':
      case 'auction_won':
        if (data.listing_id) {
          navigate(`/listing/${data.listing_id}`);
        } else if (data.auction_id) {
          navigate(`/multi-item-listing/${data.auction_id}`);
        }
        break;
      case 'new_message':
        if (data.conversation_id) {
          navigate(`/messages?conversation=${data.conversation_id}`);
        } else {
          navigate('/messages');
        }
        break;
      case 'buy_now_purchase':
        if (data.conversation_id) {
          navigate(`/messages?conversation=${data.conversation_id}`);
        } else if (data.auction_id) {
          navigate(`/multi-item-listing/${data.auction_id}`);
        }
        break;
      default:
        // No navigation for system notifications
        break;
    }
  };

  // Delete notification
  const deleteNotification = async (e, notificationId) => {
    e.stopPropagation();
    
    try {
      await axios.delete(`${API}/notifications/${notificationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      toast.success(isFrench ? 'Notification supprimée' : 'Notification deleted');
    } catch (error) {
      console.error('Failed to delete notification:', error);
    }
  };

  // Toggle sound
  const toggleSound = () => {
    const newValue = !soundEnabled;
    setSoundEnabled(newValue);
    localStorage.setItem('notificationSound', newValue.toString());
    toast.info(newValue 
      ? (isFrench ? 'Son activé' : 'Sound enabled')
      : (isFrench ? 'Son désactivé' : 'Sound muted')
    );
  };

  // Format time ago
  const formatTimeAgo = (timestamp) => {
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return isFrench ? "À l'instant" : 'Just now';
    if (diffMins < 60) return isFrench ? `il y a ${diffMins}m` : `${diffMins}m ago`;
    if (diffHours < 24) return isFrench ? `il y a ${diffHours}h` : `${diffHours}h ago`;
    if (diffDays < 7) return isFrench ? `il y a ${diffDays}j` : `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (!user) return null;

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell Icon Button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className="relative navbar-icon-btn hover:bg-slate-100 dark:hover:bg-slate-800"
        data-testid="notification-bell"
      >
        <Bell className={`h-5 w-5 transition-transform navbar-icon text-slate-900 dark:text-slate-100 ${isOpen ? 'scale-110' : ''}`} />
        
        {/* Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full animate-pulse">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </Button>

      {/* Notification Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden z-50 animate-in slide-in-from-top-2 duration-200">
          {/* Header */}
          <div className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] p-4 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                <h3 className="font-semibold">
                  {isFrench ? 'Notifications' : 'Notifications'}
                </h3>
                {unreadCount > 0 && (
                  <Badge className="bg-white/20 text-white text-xs">
                    {unreadCount} {isFrench ? 'nouvelles' : 'new'}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleSound}
                  className="h-8 w-8 text-white/80 hover:text-white hover:bg-white/10"
                >
                  {soundEnabled ? (
                    <Volume2 className="h-4 w-4" />
                  ) : (
                    <VolumeX className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsOpen(false)}
                  className="h-8 w-8 text-white/80 hover:text-white hover:bg-white/10"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            
            {/* Mark All as Read */}
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={markAllAsRead}
                className="mt-2 w-full bg-white/10 hover:bg-white/20 text-white text-xs"
              >
                <CheckCheck className="h-3 w-3 mr-2" />
                {isFrench ? 'Tout marquer comme lu' : 'Mark all as read'}
              </Button>
            )}
          </div>

          {/* Notification List */}
          <div className="max-h-[400px] overflow-y-auto">
            {loading ? (
              <div className="p-8 text-center">
                <div className="animate-spin h-8 w-8 border-4 border-[#06B6D4] border-t-transparent rounded-full mx-auto" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center">
                <Bell className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                <p className="text-slate-500 dark:text-slate-400">
                  {isFrench ? 'Aucune notification' : 'No notifications yet'}
                </p>
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                  {isFrench 
                    ? "Vous serez informé des enchères et messages"
                    : "You'll be notified about bids and messages"}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {notifications.map((notification) => {
                  const typeConfig = NOTIFICATION_TYPES[notification.type] || NOTIFICATION_TYPES.system;
                  const Icon = typeConfig.icon;
                  
                  return (
                    <div
                      key={notification.id}
                      onClick={() => handleNotificationClick(notification)}
                      className={`p-4 cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50 group relative ${
                        !notification.read ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''
                      }`}
                    >
                      <div className="flex gap-3">
                        {/* Icon */}
                        <div className={`flex-shrink-0 w-10 h-10 rounded-lg ${typeConfig.bgColor} flex items-center justify-center`}>
                          <Icon className={`h-5 w-5 ${typeConfig.color}`} />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className={`text-sm ${!notification.read ? 'font-semibold' : ''} text-slate-900 dark:text-white`}>
                                {notification.title}
                              </p>
                              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-2">
                                {notification.message}
                              </p>
                            </div>
                            
                            {/* Delete Button */}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => deleteNotification(e, notification.id)}
                              className="h-6 w-6 opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 flex-shrink-0"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>

                          {/* Footer */}
                          <div className="flex items-center justify-between mt-2">
                            <span className="text-[10px] text-slate-400 dark:text-slate-500">
                              {formatTimeAgo(notification.created_at)}
                            </span>
                            
                            {notification.data && (notification.data.listing_id || notification.data.conversation_id) && (
                              <span className="flex items-center gap-1 text-[10px] text-[#06B6D4]">
                                <ExternalLink className="h-3 w-3" />
                                {isFrench ? 'Voir' : 'View'}
                              </span>
                            )}
                          </div>

                          {/* Unread Indicator */}
                          {!notification.read && (
                            <div className="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-[#06B6D4]" />
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="p-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
              <Button
                variant="ghost"
                className="w-full text-sm text-[#06B6D4] hover:text-[#1E3A8A] hover:bg-[#06B6D4]/10"
                onClick={() => {
                  setIsOpen(false);
                  navigate('/settings?tab=notifications');
                }}
              >
                {isFrench ? 'Gérer les notifications' : 'Manage notification settings'}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NotificationCenter;
