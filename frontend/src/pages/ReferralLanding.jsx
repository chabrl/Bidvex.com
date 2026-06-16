/**
 * iter307 — Referral Landing Page
 *
 * Public route: `/r/:code`
 *
 * Behavior:
 *   1. Read `:code` from the path.
 *   2. Set `bidvex_ref` cookie (30-day expiry, lax, secure on https).
 *   3. Store the same value in localStorage as a belt-and-braces fallback
 *      for the registration form to read.
 *   4. Fire-and-forget POST/GET to /api/affiliate/track/{code} so admin
 *      analytics see the click.
 *   5. Redirect to `/` (with any incoming ?query passed through except `r`).
 *
 * No UI is rendered — just a microsecond-long redirect.
 */
import { useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';

const COOKIE_DAYS = 30;
const COOKIE_NAME = 'bidvex_ref';
const STORAGE_KEY = 'bidvex_ref';

function setReferralCookie(code) {
  try {
    const d = new Date();
    d.setTime(d.getTime() + COOKIE_DAYS * 24 * 60 * 60 * 1000);
    const isSecure = typeof window !== 'undefined' && window.location.protocol === 'https:';
    document.cookie =
      `${COOKIE_NAME}=${encodeURIComponent(code)}; expires=${d.toUTCString()}; path=/; samesite=lax${isSecure ? '; secure' : ''}`;
  } catch (_) { /* ignore */ }
  try { localStorage.setItem(STORAGE_KEY, code); } catch (_) { /* ignore */ }
}

const ReferralLanding = () => {
  const { code } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!code) {
      navigate('/', { replace: true });
      return;
    }
    setReferralCookie(code);

    // Fire-and-forget click tracking — never block the redirect on this.
    axios.get(`${API_BASE}/affiliate/track/${encodeURIComponent(code)}`).catch(() => { /* ignore */ });

    // Preserve incoming search params except `r`.
    const qp = new URLSearchParams(location.search);
    qp.delete('r');
    const search = qp.toString();
    navigate(search ? `/?${search}` : '/', { replace: true });
  }, [code, location.search, navigate]);

  return null;
};

export default ReferralLanding;
