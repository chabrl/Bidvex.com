/**
 * iter197 — Pilot Welcome Banner
 * Renders a 7-day "welcome to the BidVex Pilot" banner once a dealer-license is approved.
 * Self-fetches /api/dealer-licenses/me; computes days remaining since reviewed_at.
 * Hides itself when:
 *   - License not approved
 *   - More than 7 days since approval
 *   - User has dismissed it (localStorage flag)
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Sparkles, Car, X } from 'lucide-react';

const API = API_BASE;
const PILOT_WINDOW_DAYS = 7;
const DISMISS_KEY = 'bidvex.pilot_welcome.dismissed';

const PilotWelcomeBanner = ({ user, token }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [license, setLicense] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === '1';
    } catch (_e) {
      return false;
    }
  });

  useEffect(() => {
    if (!user || !token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/dealer-licenses/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setLicense(res.data?.license || null);
      } catch (_err) {
        // 404 / unauth -> no banner; silent
      }
    })();
    return () => { cancelled = true; };
  }, [user, token]);

  if (dismissed || !license || license.status !== 'approved') return null;

  const reviewedAtRaw = license.reviewed_at || license.approved_at;
  if (!reviewedAtRaw) return null;
  const reviewedAt = new Date(reviewedAtRaw);
  if (Number.isNaN(reviewedAt.getTime())) return null;

  const elapsedMs = Date.now() - reviewedAt.getTime();
  const elapsedDays = elapsedMs / (1000 * 60 * 60 * 24);
  if (elapsedDays > PILOT_WINDOW_DAYS) return null;
  const daysLeft = Math.max(0, Math.ceil(PILOT_WINDOW_DAYS - elapsedDays));

  const handleDismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, '1'); } catch (_e) {}
    setDismissed(true);
  };

  const firstName = (user?.name || '').split(' ')[0] || (user?.email || '').split('@')[0] || '';

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-cyan-300/30 bg-gradient-to-br from-cyan-600 via-blue-600 to-indigo-700 p-5 sm:p-6 text-white shadow-lg"
      data-testid="pilot-welcome-banner"
    >
      {/* Decorative grain overlay */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-30 mix-blend-overlay"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.18) 0, transparent 40%), radial-gradient(circle at 80% 80%, rgba(255,255,255,0.10) 0, transparent 50%)",
        }}
      />
      <button
        type="button"
        onClick={handleDismiss}
        className="absolute top-3 right-3 rounded-full p-1.5 text-white/80 hover:bg-white/15 hover:text-white transition"
        aria-label={t('dashboard.seller.pilotWelcomeDismiss', 'Dismiss')}
        data-testid="pilot-welcome-dismiss-btn"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex-1 min-w-0">
          <span
            className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold uppercase tracking-wide backdrop-blur"
            data-testid="pilot-welcome-badge"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {t('dashboard.seller.pilotWelcomeBadge', 'Pilot Project')}
          </span>
          <h2
            className="mt-3 text-xl sm:text-2xl font-bold leading-tight"
            data-testid="pilot-welcome-title"
          >
            {t('dashboard.seller.pilotWelcomeTitle', { name: firstName, defaultValue: `Welcome to the BidVex Pilot, ${firstName}!` })}
          </h2>
          <p className="mt-2 text-sm sm:text-base text-white/90 max-w-2xl">
            {t('dashboard.seller.pilotWelcomeBody')}
          </p>
          <p className="mt-2 text-xs text-white/75" data-testid="pilot-welcome-days-left">
            {daysLeft > 0
              ? t('dashboard.seller.pilotWelcomeDaysLeft', { days: daysLeft })
              : t('dashboard.seller.pilotWelcomeApprovedJustNow', 'Approved just now')}
          </p>
        </div>

        <div className="flex-shrink-0">
          <Button
            size="lg"
            onClick={() => navigate('/vehicle-auctions/seller/register')}
            className="bg-white text-blue-700 hover:bg-cyan-50 hover:text-blue-800 font-semibold shadow-md w-full sm:w-auto"
            data-testid="pilot-welcome-cta-btn"
          >
            <Car className="mr-2 h-5 w-5" />
            {t('dashboard.seller.pilotWelcomeCta', 'List Your First Vehicle')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PilotWelcomeBanner;
