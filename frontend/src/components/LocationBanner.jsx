/**
 * iter238 Mission 1.3 — Dismissible "Add your location" banner for users
 * who already finished onboarding but have no city/postal on file.
 *
 * Hidden when:
 *   • The user is anonymous (no token)
 *   • The user already has a city/postal on file
 *   • The user dismissed it within the last 7 days (localStorage)
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, X } from 'lucide-react';
import { getAuthToken } from '../utils/authToken';

const DISMISS_KEY = 'bidvex.locationBannerDismissedAt';
const DISMISS_WINDOW_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export default function LocationBanner() {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const backendUrl = process.env.REACT_APP_BACKEND_URL
    ? `${process.env.REACT_APP_BACKEND_URL}/api`
    : '/api';

  useEffect(() => {
    const token = getAuthToken();
    if (!token) return;
    const dismissedAt = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
    if (Date.now() - dismissedAt < DISMISS_WINDOW_MS) return;

    // Probe onboarding/status to see if the user has location.
    fetch(`${backendUrl}/onboarding/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && !data.has_location) setVisible(true);
      })
      .catch(() => undefined);
  }, [backendUrl]);

  if (!visible) return null;

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setVisible(false);
  };

  return (
    <div
      className="w-full bg-amber-50 border-y border-amber-200 text-amber-900 px-4 py-2 text-sm flex items-center gap-2"
      data-testid="location-update-banner"
    >
      <MapPin className="h-4 w-4 flex-shrink-0" />
      <span className="flex-1">
        📍 Add your location to see nearby listings.
      </span>
      <button
        type="button"
        onClick={() => navigate('/onboarding')}
        className="text-amber-900 font-semibold underline-offset-2 hover:underline"
        data-testid="location-banner-update-btn"
      >
        Update Profile
      </button>
      <button
        type="button"
        onClick={dismiss}
        className="ml-2 p-1 rounded hover:bg-amber-100"
        aria-label="Dismiss"
        data-testid="location-banner-dismiss-btn"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
