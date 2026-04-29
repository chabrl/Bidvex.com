import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Lands here after the backend OAuth callback redirects with
 *   /auth/google/finish#token=<JWT>&redirect=/marketplace
 *
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS,
 *           THIS BREAKS THE AUTH.
 * Reads the token from the URL fragment (never logged), persists it, then
 * forwards the user to the original destination.
 */
const GoogleAuthFinishPage = () => {
  const navigate = useNavigate();
  const { setUserFromToken } = useAuth();

  useEffect(() => {
    const fragment = window.location.hash.replace(/^#/, '');
    const params = new URLSearchParams(fragment);
    const token = params.get('token');
    const redirect = params.get('redirect') || '/marketplace';

    // Strip the token from the URL immediately
    window.history.replaceState({}, '', '/auth/google/finish');

    if (!token) {
      toast.error('Google sign-in failed: no token received.');
      navigate('/auth', { replace: true });
      return;
    }

    (async () => {
      try {
        await setUserFromToken(token);
        toast.success('Welcome to BidVex!');
        navigate(redirect.startsWith('/') ? redirect : '/marketplace', { replace: true });
      } catch (err) {
        toast.error('Google sign-in failed. Please try again.');
        navigate('/auth', { replace: true });
      }
    })();
  }, [navigate, setUserFromToken]);

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
