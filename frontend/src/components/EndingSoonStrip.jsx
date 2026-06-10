import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Clock } from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';

const API = API_BASE;

// iter298 BUG 1 — shared router: same logic as FlattenedMarketplace's
// getDetailLink so every section deep-links to its own detail page.
const getDetailLink = (item) => {
  const cat = (item.category || '').toLowerCase();
  const lt = (item.listing_type || '').toLowerCase();
  const sec = (item.section || '').toLowerCase();
  if (
    lt === 'storage_locker' || lt === 'storage_auction' || lt === 'storage' ||
    lt === 'unit' || lt === 'unit_auction' || sec === 'storage' ||
    cat === 'storage_locker' || cat === 'storage'
  ) return `/storage-auctions/${item.id}`;
  if (
    lt === 'vehicle_auction' || lt === 'vehicles' || lt === 'vehicle' ||
    sec === 'vehicles' || cat === 'vehicle' || cat === 'vehicles' ||
    cat === 'car' || cat === 'auto' || cat === 'vehicle parts'
  ) return `/vehicle-auctions/${item.id}`;
  return item.auction_id ? `/lots/${item.auction_id}` : `/listing/${item.id}`;
};

const timeLeftLabel = (endDate, isFrench) => {
  const ms = new Date(endDate) - new Date();
  if (ms <= 0) return isFrench ? 'Terminé' : 'Ended';
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  if (h > 0) return isFrench ? `${h}h ${m}min restantes` : `${h}h ${m}m left`;
  return isFrench ? `${m} min restantes` : `${m}m left`;
};

/**
 * iter298 BUG 1 — "Ending Soon" strip for the Marketplace homepage.
 * Renders ONLY when active listings ending within 24h exist. Always
 * computed dynamically server-side from end_time (never a scheduler flag).
 */
const EndingSoonStrip = () => {
  const { i18n } = useTranslation();
  const isFrench = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancelled = false;
    axios
      .get(`${API}/marketplace/items`, { params: { ending_soon: 'true', limit: 12 } })
      .then((r) => { if (!cancelled) setItems(r.data?.items || []); })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, []);

  if (!items.length) return null;

  return (
    <div className="mb-6" data-testid="ending-soon-section">
      <div className="flex items-center gap-2 mb-3">
        <span
          className="inline-flex items-center justify-center w-8 h-8 rounded-full"
          style={{ background: '#fef2f2', color: '#dc2626' }}
        >
          <Clock className="h-4 w-4" />
        </span>
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">
          {isFrench ? 'Se termine bientôt' : 'Ending Soon'}
        </h2>
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full"
          style={{ background: '#fee2e2', color: '#b91c1c' }}
          data-testid="ending-soon-count"
        >
          {items.length}
        </span>
        <span className="text-xs text-slate-500 hidden sm:inline">
          {isFrench ? '— dans les prochaines 24 h' : '— within the next 24h'}
        </span>
      </div>
      <div
        className="-mx-4 md:mx-0 px-4 md:px-0"
        style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}
      >
        <div className="flex gap-3" style={{ minWidth: 'min-content', paddingBottom: 6 }}>
          {items.map((item) => (
            <Link
              key={item.id}
              to={getDetailLink(item)}
              className="flex-shrink-0 w-[200px] bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900/60 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow"
              data-testid={`ending-soon-card-${item.id}`}
            >
              <div className="h-[110px] bg-slate-100 dark:bg-slate-800">
                {(item.images && item.images[0]) ? (
                  <img
                    src={item.images[0]}
                    alt={item.title}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-2xl">📦</div>
                )}
              </div>
              <div className="p-2.5">
                <p className="text-[13px] font-semibold text-slate-900 dark:text-white truncate">
                  {item.title}
                </p>
                <p className="text-[14px] font-bold mt-0.5" style={{ color: '#2d6be4' }}>
                  {formatCurrency(item.current_price || item.starting_price || 0)}
                </p>
                <p className="text-[11px] font-semibold mt-1" style={{ color: '#dc2626' }}>
                  ⏰ {timeLeftLabel(item.auction_end_date, isFrench)}
                </p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export default EndingSoonStrip;
