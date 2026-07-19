/**
 * iter364 — Admin notification bell.
 *
 * Polls /api/admin/notifications/summary every 60s. Renders a Bell icon
 * with a red count badge if total_unread > 0. Click → dropdown with the
 * 4 category counts, each linking to the relevant admin section.
 */
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Bell, AlertTriangle, ShieldCheck, Gavel, CreditCard } from 'lucide-react';
import API_BASE from '../../config';

const COPY = {
  en: {
    title: 'Notifications',
    empty: 'You are all caught up 🎉',
    categories: {
      unread_flagged_listings: 'Flagged listings',
      pending_dealer_reviews:  'Dealer licence reviews',
      open_disputes:           'Open disputes',
      payment_failures:        'Payment failures',
    },
    viewAll: 'View all',
  },
  fr: {
    title: 'Notifications',
    empty: 'Vous êtes à jour 🎉',
    categories: {
      unread_flagged_listings: 'Annonces signalées',
      pending_dealer_reviews:  'Vérif. permis concessionnaires',
      open_disputes:           'Litiges ouverts',
      payment_failures:        'Échecs de paiement',
    },
    viewAll: 'Voir tout',
  },
};

const ICON = {
  unread_flagged_listings: AlertTriangle,
  pending_dealer_reviews:  ShieldCheck,
  open_disputes:           Gavel,
  payment_failures:        CreditCard,
};

const TAB_FOR = {
  unread_flagged_listings: { primary: 'marketplace', secondary: 'flagged-listings' },
  pending_dealer_reviews:  { primary: 'vehicles',    secondary: 'dealer-licenses' },
  open_disputes:           { primary: 'marketplace', secondary: 'disputed-settlements' },
  payment_failures:        { primary: 'finance',     secondary: 'transactions' },
};

export default function NotificationBell({ token, lang = 'en', onNavigate }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const t = COPY[lang === 'fr' ? 'fr' : 'en'];

  const fetchSummary = async () => {
    try {
      const res = await axios.get(`${API_BASE}/admin/notifications/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (err) {
      // Silent — bell simply won't show a badge until backend recovers.
    }
  };

  useEffect(() => {
    if (!token) return;
    fetchSummary();
    const int = setInterval(fetchSummary, 60_000);
    return () => clearInterval(int);
  }, [token]);

  // Close on outside click.
  useEffect(() => {
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const total = data?.total_unread || 0;
  const categories = [
    'unread_flagged_listings',
    'pending_dealer_reviews',
    'open_disputes',
    'payment_failures',
  ];

  return (
    <div ref={rootRef} className="relative" data-testid="admin-notification-bell">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors min-h-[40px] min-w-[40px] flex items-center justify-center"
        aria-label={t.title}
        aria-expanded={open}
        data-testid="admin-notification-bell-btn"
      >
        <Bell className="h-5 w-5 text-slate-700 dark:text-slate-200" />
        {total > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold ring-2 ring-white"
            data-testid="admin-notification-badge"
          >
            {total > 99 ? '99+' : total}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-80 max-w-[calc(100vw-2rem)] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50"
          role="menu"
          data-testid="admin-notification-dropdown"
        >
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 flex items-center justify-between">
            <span className="font-bold text-sm text-[#0B2545] dark:text-white">{t.title}</span>
            {total > 0 && (
              <span className="text-[11px] font-semibold text-red-600" data-testid="admin-notification-total">
                {total}
              </span>
            )}
          </div>
          {total === 0 && (
            <div className="p-6 text-center text-sm text-slate-500 dark:text-slate-400" data-testid="admin-notification-empty">
              {t.empty}
            </div>
          )}
          {total > 0 && (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800" data-testid="admin-notification-list">
              {categories.map((key) => {
                const count = data?.[key] || 0;
                if (count === 0) return null;
                const Icon = ICON[key];
                return (
                  <li key={key}>
                    <button
                      type="button"
                      onClick={() => {
                        const dest = TAB_FOR[key];
                        if (dest && typeof onNavigate === 'function') onNavigate(dest);
                        setOpen(false);
                      }}
                      className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
                      data-testid={`admin-notification-item-${key}`}
                    >
                      <Icon className="h-5 w-5 text-primary flex-shrink-0" />
                      <span className="flex-1 text-sm text-slate-700 dark:text-slate-200">
                        {t.categories[key]}
                      </span>
                      <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full bg-red-600 text-white text-xs font-bold">
                        {count}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
