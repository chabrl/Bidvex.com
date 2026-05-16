/**
 * iter217 Phase 4 — Dedicated /notifications page
 *
 * Full list of every notification for the current user. Each row navigates
 * to the resolved action_url; rows are marked as read on click; bulk
 * actions ("Mark all as read", "Clear all") at the top.
 */
import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Bell, CheckCheck, Trash2, AlertCircle, Info, ShoppingCart, Gavel,
  CreditCard, FileText, MessageSquare, Award, Warehouse, Car,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card } from '../components/ui/card';
import { useAuth } from '../contexts/AuthContext';

const API = API_BASE;

const TYPE_ICON = {
  outbid: ShoppingCart,
  auction_ending: Gavel,
  auction_won: Award,
  auction_lost: Gavel,
  auction_sold: ShoppingCart,
  auction_ended_no_bids: AlertCircle,
  new_bid: Gavel,
  new_message: MessageSquare,
  message_received: MessageSquare,
  buy_now_purchase: ShoppingCart,
  payment_required: CreditCard,
  payment_overdue: AlertCircle,
  invoice_issued: FileText,
  invoice_paid: FileText,
  pickup_code_ready: ShoppingCart,
  admin_rejection: AlertCircle,
  admin_document_request: FileText,
  admin_general: Info,
  admin_notification: Info,
  document_request: FileText,
  partner_activated: Award,
  partner_approved: Award,
  storage_facility_verified: Warehouse,
  storage_facility_rejected: Warehouse,
  vehicle_dealer_approved: Car,
  vehicle_dealer_rejected: Car,
  new_review: Award,
  warning: AlertCircle,
  info: Info,
  general: Info,
};

const NotificationsPage = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  const isFr = (i18n.language || '').startsWith('fr');

  const fetchNotifications = useCallback(async () => {
    if (!token) return;
    try {
      const { data } = await axios.get(`${API}/notifications?limit=200`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications(data.notifications || []);
    } catch (err) {
      console.error('Fetch notifications failed', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleClick = async (n) => {
    // Mark as read
    if (!n.read) {
      try {
        await axios.post(`${API}/notifications/${n.id}/read`, {}, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setNotifications((prev) =>
          prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
        );
      } catch (err) {
        // non-blocking
      }
    }
    // Navigate (guaranteed)
    const url = n.action_url
      || (n.data?.listing_id && `/listing/${n.data.listing_id}`)
      || (n.data?.auction_id && `/lots/${n.data.auction_id}`)
      || '/notifications';
    if (/^https?:\/\//i.test(url)) {
      window.open(url, '_blank', 'noopener,noreferrer');
    } else if (url !== '/notifications') {
      navigate(url);
    }
  };

  const markAllRead = async () => {
    try {
      await axios.post(`${API}/notifications/mark-all-read`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      toast.success(isFr ? 'Toutes les notifications marquées comme lues' : 'All notifications marked as read');
    } catch (err) {
      toast.error(isFr ? 'Échec' : 'Failed');
    }
  };

  const clearAll = async () => {
    if (!window.confirm(isFr ? 'Tout effacer ?' : 'Clear all notifications?')) return;
    try {
      await Promise.all(
        notifications.map((n) =>
          axios.delete(`${API}/notifications/${n.id}`, {
            headers: { Authorization: `Bearer ${token}` },
          }).catch(() => null)
        )
      );
      setNotifications([]);
      toast.success(isFr ? 'Notifications effacées' : 'Notifications cleared');
    } catch (err) {
      toast.error(isFr ? 'Échec' : 'Failed');
    }
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div className="min-h-screen" style={{ background: '#f8fafc' }}>
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg" style={{ background: '#eff6ff' }}>
              <Bell className="h-6 w-6" style={{ color: '#2563eb' }} />
            </div>
            <div>
              <h1 className="text-2xl font-bold" style={{ color: '#0f172a' }}>
                {t('notifications.title', 'Notifications')}
              </h1>
              <p className="text-sm" style={{ color: '#64748b' }}>
                {t('notifications.subtitle', { unread: unreadCount, total: notifications.length, defaultValue: '{{unread}} unread of {{total}} total' })}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {unreadCount > 0 && (
              <Button onClick={markAllRead} size="sm" variant="outline" data-testid="mark-all-read-btn">
                <CheckCheck className="h-4 w-4 mr-1.5" />
                {t('notifications.markAllRead', 'Mark all as read')}
              </Button>
            )}
            {notifications.length > 0 && (
              <Button onClick={clearAll} size="sm" variant="outline" className="text-red-600 hover:bg-red-50" data-testid="clear-all-btn">
                <Trash2 className="h-4 w-4 mr-1.5" />
                {t('notifications.clearAll', 'Clear all')}
              </Button>
            )}
          </div>
        </div>

        {loading ? (
          <Card className="p-12 text-center">
            <p className="text-slate-400">{t('common.loading', 'Loading…')}</p>
          </Card>
        ) : notifications.length === 0 ? (
          <Card className="p-12 text-center">
            <Bell className="h-12 w-12 mx-auto mb-3" style={{ color: '#cbd5e1' }} />
            <p className="text-slate-500">{t('notifications.empty', 'No notifications yet')}</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {notifications.map((n) => {
              const Icon = TYPE_ICON[n.type?.toLowerCase()] || Info;
              return (
                <Card
                  key={n.id}
                  data-testid="notification-row"
                  onClick={() => handleClick(n)}
                  className={`p-4 cursor-pointer transition-all hover:shadow-md ${n.read ? '' : 'border-l-4'}`}
                  style={!n.read ? { borderLeftColor: '#2563eb', background: '#eff6ff' } : {}}
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg flex-shrink-0" style={{ background: n.read ? '#f1f5f9' : '#dbeafe' }}>
                      <Icon className="h-4 w-4" style={{ color: n.read ? '#64748b' : '#2563eb' }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className={`text-sm ${n.read ? 'font-medium text-slate-700' : 'font-bold text-slate-900'}`}>
                          {n.title || t('notifications.noTitle', '(no title)')}
                        </h3>
                        {!n.read && <Badge className="bg-blue-600 text-white text-[10px] px-1.5 py-0">{t('notifications.new', 'New')}</Badge>}
                      </div>
                      {n.message && (
                        <p className="text-sm" style={{ color: '#475569', lineHeight: 1.5 }}>
                          {n.message}
                        </p>
                      )}
                      <p className="text-xs mt-2" style={{ color: '#94a3b8' }}>
                        {new Date(n.created_at).toLocaleString(isFr ? 'fr-CA' : 'en-CA')}
                      </p>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default NotificationsPage;
