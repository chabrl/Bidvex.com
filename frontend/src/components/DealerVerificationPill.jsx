/**
 * iter428 — DealerVerificationPill
 *
 * A compact status pill for the top navbar, visible only to users with
 * a dealer account. Shows one of three states based on the current
 * verification_status returned from `/api/vehicle-sellers/me`:
 *
 *   ✓ Verified    — emerald  — verification_status === 'approved'
 *                             AND user.vehicle_dealer_suspended !== true
 *   ⏳ Under Review — amber   — verification_status ∈ {pending, under_review}
 *   ⚠ Suspended    — red     — user.vehicle_dealer_suspended === true
 *                             OR verification_status === 'suspended'
 *                             OR verification_status === 'rejected'
 *
 * Clicking the pill navigates to `/vehicle-auctions/seller/register`
 * (registration + status page). Uses `t('nav.dealerStatus.*')` for the
 * bilingual labels + tooltips already added to en.json / fr.json.
 *
 * Never renders for non-dealers (404 from the API → null). Does not
 * touch navbar layout, auth logic, or any other component — it's a
 * standalone pill dropped in next to <NotificationCenter />.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { ShieldCheck, Clock, ShieldAlert } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import API_BASE from '../config';

const STATE_STYLES = {
  verified:      'bg-emerald-100 text-emerald-800 border-emerald-300 hover:bg-emerald-200',
  under_review:  'bg-amber-100 text-amber-800 border-amber-300 hover:bg-amber-200',
  suspended:     'bg-rose-100 text-rose-800 border-rose-300 hover:bg-rose-200',
};

const DealerVerificationPill = () => {
  const { user, token } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [state, setState] = useState(null);   // 'verified' | 'under_review' | 'suspended' | null

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      if (!user || !token) { setState(null); return; }
      // Reuse the same source of truth as <DealerVerificationGate>:
      // GET /api/vehicle-sellers/me — 404 means "not a dealer".
      try {
        const r = await axios.get(`${API_BASE}/vehicle-sellers/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;
        const status = r.data?.verification_status;
        if (user.vehicle_dealer_suspended === true || status === 'suspended' || status === 'rejected') {
          setState('suspended');
        } else if (status === 'approved') {
          setState('verified');
        } else if (status === 'pending' || status === 'under_review') {
          setState('under_review');
        } else {
          setState(null);
        }
      } catch (err) {
        if (cancelled) return;
        // 404 = not a dealer at all → do not render the pill.
        if (err?.response?.status === 404) {
          setState(null);
          return;
        }
        // Network / auth errors → also skip the pill to avoid noise.
        setState(null);
      }
    };
    probe();
    return () => { cancelled = true; };
  }, [user, token]);

  if (!state) return null;

  const config = {
    verified:     { Icon: ShieldCheck, label: t('nav.dealerStatus.verified'),      tip: t('nav.dealerStatus.tooltipVerified')     },
    under_review: { Icon: Clock,       label: t('nav.dealerStatus.underReview'),   tip: t('nav.dealerStatus.tooltipUnderReview')  },
    suspended:    { Icon: ShieldAlert, label: t('nav.dealerStatus.suspended'),     tip: t('nav.dealerStatus.tooltipSuspended')    },
  }[state];

  const symbol = { verified: '✓', under_review: '⏳', suspended: '⚠' }[state];
  const Icon = config.Icon;

  return (
    <button
      type="button"
      onClick={() => navigate('/vehicle-auctions/seller/register')}
      title={config.tip}
      className={`hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-semibold transition ${STATE_STYLES[state]}`}
      data-testid={`dealer-status-pill-${state}`}
      aria-label={config.tip}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span aria-hidden="true">{symbol}</span>
      <span>{config.label}</span>
    </button>
  );
};

export default DealerVerificationPill;
