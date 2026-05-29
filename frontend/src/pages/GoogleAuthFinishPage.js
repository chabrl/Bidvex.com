import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getAuthToken } from '../utils/authToken';

/**
 * Lands here after the backend OAuth callback redirects with
 *   /auth/google/finish#token=<JWT>&redirect=/marketplace
 *
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS,
 *           THIS BREAKS THE AUTH.
 * Reads the token from the URL fragment (never logged), persists it, then
 * forwards the user to the original destination.
 *
 * iter238 Mission 1.1 — Suppress the "no token received" false-positive
 * error. Google's popup callback can fire intermediate events BEFORE the
 * token arrives. We wait 1500 ms before deciding the auth actually failed:
 * if the auth state confirms the user is signed in (token present), we
 * navigate to the redirect target silently. Also: route first-time users
 * to /onboarding instead of /marketplace when their profile flag says so.
 */
const GoogleAuthFinishPage = () => {
  const navigate = useNavigate();
  const { setUserFromToken } = useAuth();
  const backendUrl = process.env.REACT_APP_BACKEND_URL
    ? `${process.env.REACT_APP_BACKEND_URL}/api`
    : '/api';

  useEffect(() => {
    const fragment = window.location.hash.replace(/^#/, '');
    const params = new URLSearchParams(fragment);
    const token = params.get('token');
    const redirect = params.get('redirect') || '/marketplace';
    const errorCode = params.get('error') || params.get('error_code');

    // Strip sensitive tokens from URL immediately.
    window.history.replaceState({}, '', '/auth/google/finish');

    // Cancellations aren't failures — silently bail.
    if (errorCode === 'popup_closed_by_user' || errorCode === 'access_denied_by_user') {
      navigate('/auth', { replace: true });
      return;
    }

    if (!token) {
      // iter238 — Debounced false-error suppression. Wait 1500ms; if the
      // auth context (or localStorage) confirms a session, treat as success.
      const tid = setTimeout(() => {
        const persistedToken = getAuthToken();
        if (persistedToken) {
          // Already signed in via another tab / racing callback — silent redirect.
          navigate(redirect.startsWith('/') ? redirect : '/marketplace', { replace: true });
          return;
        }
        toast.error('Google sign-in failed: no token received.');
        navigate('/auth', { replace: true });
      }, 1500);
      return () => clearTimeout(tid);
    }

    (async () => {
      try {
        await setUserFromToken(token);

        // iter238 Mission 1.2 — Route first-time Google users to /onboarding.
        let nextRoute = redirect;
        try {
          const res = await fetch(`${backendUrl}/onboarding/status`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const data = await res.json();
            if (!data.onboarding_complete) nextRoute = '/onboarding';
          }
        } catch { /* silent — fall through to default redirect */ }

        toast.success('Welcome to BidVex!');
        navigate(nextRoute.startsWith('/') ? nextRoute : '/marketplace', { replace: true });
      } catch (err) {
        // Same debounce trick — if a token was just persisted by a parallel call, suppress.
        setTimeout(() => {
          if (getAuthToken()) {
            navigate(redirect.startsWith('/') ? redirect : '/marketplace', { replace: true });
            return;
          }
          toast.error('Google sign-in failed. Please try again.');
          navigate('/auth', { replace: true });
        }, 1500);
      }
    })();
  }, [navigate, setUserFromToken, backendUrl]);

  return (
    <div className="min-h-screen flex items-center justify-center" data-testid="google-finish-page">
      <div className="text-center space-y-3">
        <Loader2 className="h-10 w-10 animate-spin mx-auto text-blue-600" />
        <p className="text-sm text-muted-foreground">Signing you in…</p>
      </div>
    </div>
  );
};

export default GoogleAuthFinishPage;
