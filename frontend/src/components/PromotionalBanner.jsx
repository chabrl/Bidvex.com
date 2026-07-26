/**
 * iter243 Mission 1 — Platform-wide promotional banner.
 * iter256 — Dynamic-stack rewrite.
 *
 * Polls `GET /api/promotions/active-banners` every 5 minutes, renders a
 * dismissible top-of-page banner per active promotion that matches the
 * calling user's tier/province/eligibility. Dismissals are persisted to
 * localStorage so users don't see the same banner again for 24h.
 *
 * iter256 — the banner stack now uses `position: fixed; top: 0;
 * z-[80]` so the red banner row ALWAYS sits above the fixed Navbar
 * (z-[70]) and its dismiss `X` button is fully clickable on mobile.
 * A ResizeObserver pushes the live rendered height into
 * `PromoBannerContext`, which the Navbar consumes to dynamically bind
 * its own `top` offset (and which the global spacer consumes to push
 * page content below the combined banner + nav stack). This kills the
 * need for hardcoded `pt-16 / pt-20` hotfixes on individual B2B
 * dashboards — the layout self-balances at every viewport.
 *
 * Mounted globally inside `App.js`. iter388 — public banners (target=all)
 * are now surfaced to anonymous visitors too; the previous version
 * short-circuited on missing token and silently hid every banner. */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Sparkles, X, Copy, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { usePromoBanner } from '../contexts/PromoBannerContext';
import API_BASE from '../config';

const POLL_MS = 5 * 60_000;           // 5 minutes
const DISMISS_TTL_MS = 24 * 60 * 60_000; // 24 hours

const dismissKey = (promoId) => `bidvex.banner.dismissed.${promoId}`;

const isDismissed = (promoId) => {
  try {
    const raw = localStorage.getItem(dismissKey(promoId));
    if (!raw) return false;
    const ts = parseInt(raw, 10);
    if (Number.isNaN(ts)) return false;
    return Date.now() - ts < DISMISS_TTL_MS;
  } catch {
    return false;
  }
};

const dismissBanner = (promoId) => {
  try { localStorage.setItem(dismissKey(promoId), String(Date.now())); } catch { /* noop */ }
};

const PromotionalBanner = () => {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const { setBannerHeight } = usePromoBanner();
  const isFr = (i18n.language || 'en').startsWith('fr');
  const t = (en, fr) => (isFr ? fr : en);

  const stackRef = useRef(null);
  const [banners, setBanners] = useState([]);
  const [hidden, setHidden] = useState(() => new Set());
  const [copied, setCopied] = useState(null);

  const visible = useMemo(
    () => banners.filter((b) => !hidden.has(b.id) && !isDismissed(b.id)),
    [banners, hidden]
  );

  const fetchBanners = useCallback(async () => {
    // iter388 — Fetch active banners for BOTH anonymous and signed-in
    // visitors. The backend already gates targeting: anonymous callers
    // receive only `target=all` public banners; signed-in callers get
    // those plus tier/province/custom matches. Attaching the token is
    // optional and only adds targeting eligibility.
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const r = await axios.get(`${API_BASE}/promotions/active-banners`, { headers });
      setBanners(Array.isArray(r?.data?.banners) ? r.data.banners : []);
    } catch {
      setBanners([]);
    }
  }, [token]);

  useEffect(() => {
    fetchBanners();
    // Poll for updates for every visitor — a fresh public promotion
    // launched by an admin should surface on the homepage within 5 min
    // whether the visitor is signed in or not.
    const id = setInterval(fetchBanners, POLL_MS);
    return () => clearInterval(id);
  }, [fetchBanners]);

  // iter256 — Live-measure the rendered banner stack height so the
  // Navbar can dynamically bind its `top` offset. ResizeObserver fires
  // on mount, on text wrap, on font-load reflow, and on viewport
  // changes — covering every visual reflow path.
  useEffect(() => {
    const node = stackRef.current;
    if (!node) {
      setBannerHeight(0);
      return undefined;
    }
    setBannerHeight(node.getBoundingClientRect().height);
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setBannerHeight(entry.contentRect.height);
      }
    });
    ro.observe(node);
    return () => {
      ro.disconnect();
      setBannerHeight(0);
    };
  }, [setBannerHeight, visible.length]);

  const handleDismiss = (id) => {
    dismissBanner(id);
    setHidden((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  const handleCopy = async (code) => {
    if (!code) return;
    try { await navigator.clipboard.writeText(code); } catch { /* noop */ }
    setCopied(code);
    setTimeout(() => setCopied(null), 1800);
  };

  if (visible.length === 0) return null;

  return (
    <div
      ref={stackRef}
      className="fixed top-0 left-0 right-0 z-[80] w-full space-y-1"
      data-testid="promotional-banner-stack"
    >
      {visible.slice(0, 2).map((b) => (
        <div
          key={b.id}
          className="bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 text-white px-3 sm:px-4 py-2 text-sm flex items-center gap-3 shadow-sm"
          data-testid={`promotional-banner-${b.id}`}
          role="status"
        >
          <Sparkles className="h-4 w-4 flex-shrink-0" />
          <div className="flex-1 min-w-0 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-semibold truncate" data-testid={`promotional-banner-title-${b.id}`}>
              {isFr ? b.name_fr : b.name_en}
            </span>
            {b.discount_percent != null && (
              <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
                {Math.round(b.discount_percent)}% OFF
              </span>
            )}
            {b.coupon_code && (
              <button
                type="button"
                onClick={() => handleCopy(b.coupon_code)}
                className="inline-flex items-center gap-1.5 bg-white/15 hover:bg-white/25 px-2 py-0.5 rounded-full text-xs font-mono uppercase tracking-wide transition-colors"
                data-testid={`promotional-banner-coupon-${b.id}`}
                aria-label={t('Copy coupon code', 'Copier le code promo')}
              >
                {copied === b.coupon_code ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                {b.coupon_code}
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => handleDismiss(b.id)}
            className="flex-shrink-0 p-1 rounded-full hover:bg-white/20 transition-colors"
            aria-label={t('Dismiss', 'Fermer')}
            data-testid={`promotional-banner-dismiss-${b.id}`}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
};

export default PromotionalBanner;
