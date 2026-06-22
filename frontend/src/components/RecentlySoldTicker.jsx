/**
 * iter310 — RecentlySoldTicker
 *
 * Anonymized rolling ticker of the last completed sales platform-wide.
 * Renders beside the "Live Auctions" pill on the homepage as a social-
 * proof / trust signal. Bilingual (EN/FR). Rotates one item every 4s.
 *
 * Pulls from GET /api/public/recently-sold (60s server-side cache).
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ROTATE_MS = 4000;

const formatPrice = (price, currency, lang) => {
  try {
    return new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency: currency || 'CAD',
      maximumFractionDigits: 0,
    }).format(price);
  } catch {
    return `$${Math.round(price)} ${currency || 'CAD'}`;
  }
};

const RecentlySoldTicker = () => {
  const { i18n } = useTranslation();
  const lang = (i18n.language || 'en').startsWith('fr') ? 'fr' : 'en';
  const [items, setItems] = useState([]);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/public/recently-sold?limit=10`);
        if (!cancelled && Array.isArray(r.data?.items)) {
          setItems(r.data.items.filter((it) => it.title && it.price > 0));
        }
      } catch {
        // Silent fail — ticker is purely cosmetic.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (items.length < 2) return undefined;
    const id = setInterval(() => {
      setIdx((i) => (i + 1) % items.length);
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, [items.length]);

  if (items.length === 0) return null;
  const current = items[idx];
  if (!current) return null;

  const soldFor = lang === 'fr' ? 'vendu pour' : 'sold for';

  return (
    <div
      className="inline-flex items-center gap-2 bg-white/10 backdrop-blur rounded-full px-4 py-2 text-white border border-white/20 max-w-md"
      data-testid="recently-sold-ticker"
      aria-live="polite"
    >
      <span className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" />
      <span className="text-sm truncate" data-testid="recently-sold-item">
        <span className="font-semibold truncate max-w-[220px] inline-block align-bottom">
          {current.title}
        </span>
        <span className="opacity-80"> {soldFor} </span>
        <span className="font-bold tabular-nums">
          {formatPrice(current.price, current.currency, lang)}
        </span>
      </span>
    </div>
  );
};

export default RecentlySoldTicker;
