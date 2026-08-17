/**
 * iter489 — OAuth 2.1 Consent page for the BidVex Remote MCP connector.
 *
 * URL pattern:
 *   /mcp-consent?client_id=…&redirect_uri=…&code_challenge=…&scope=…&state=…&resource=…&client_name=…
 *
 * The backend's `GET /api/mcp/oauth/authorize` redirects to this route
 * after validating the OAuth params. The user's session JWT is used
 * to authorise the grant — an unauthenticated user is sent to /auth
 * with a next-param round trip.
 *
 * On approve/deny we POST to /api/mcp/oauth/authorize/decision, which
 * returns a `redirect_to` URL with the OAuth code (or the RFC 6749
 * error). We then hard-redirect the browser to that URL — that step
 * is what actually hands the code back to Claude.ai.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../config';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { ShieldCheck, ShieldAlert, Bot, Loader2 } from 'lucide-react';

const SCOPE_DESCRIPTIONS = {
  read:       'Search auctions, read listing details, and view bid statuses',
  bid:        'Place bids on your behalf (still gated by trust/payment verification)',
  list:       'Create draft auction listings (still gated by tax-ID verification)',
  promote:    'Create Meta Ad promotions and listing videos',
  analytics:  'Read inventory + performance analytics',
  matchmaker: 'Analyse inventory and generate B2B campaign drafts (approval-gated)',
};

const authHeader = () => {
  const t = localStorage.getItem('token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export default function McpConsentPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [decision, setDecision] = useState(null);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  const clientId      = params.get('client_id') || '';
  const clientName    = params.get('client_name') || 'Remote MCP Client';
  const redirectUri   = params.get('redirect_uri') || '';
  const codeChallenge = params.get('code_challenge') || '';
  const codeMethod    = params.get('code_challenge_method') || 'S256';
  const scopeStr      = params.get('scope') || 'read';
  const state         = params.get('state') || '';
  const resource      = params.get('resource') || '';

  const scopes = useMemo(() =>
    scopeStr.split(/[\s+]+/).filter(Boolean),
    [scopeStr],
  );

  useEffect(() => {
    (async () => {
      const t = localStorage.getItem('token');
      if (!t) {
        // Bounce to auth with the full consent URL as next-param
        const next = window.location.pathname + window.location.search;
        navigate(`/auth?next=${encodeURIComponent(next)}`, { replace: true });
        return;
      }
      try {
        const r = await axios.get(`${API_BASE}/auth/me`, { headers: authHeader() });
        setMe(r.data);
      } catch (err) {
        const next = window.location.pathname + window.location.search;
        navigate(`/auth?next=${encodeURIComponent(next)}`, { replace: true });
        return;
      }
      setLoading(false);
    })();
  }, [navigate]);

  const decide = async (approved) => {
    setDecision(approved ? 'approving' : 'denying');
    try {
      const r = await axios.post(
        `${API_BASE}/mcp/oauth/authorize/decision`,
        {
          approved,
          client_id:             clientId,
          redirect_uri:          redirectUri,
          code_challenge:        codeChallenge,
          code_challenge_method: codeMethod,
          scope:                 scopeStr,
          state,
          resource: resource || undefined,
        },
        { headers: { ...authHeader(), 'Content-Type': 'application/json' } },
      );
      const target = r.data?.redirect_to;
      if (!target) throw new Error('missing redirect_to');
      // Hard-redirect to hand the code (or error) back to the client
      window.location.href = target;
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const status = err?.response?.status;
      if (status === 402) {
        toast.error('An active BidVex subscription is required to authorise MCP connectors.');
      } else {
        toast.error((detail && (detail.message_en || detail.error)) || 'Consent request failed');
      }
      setDecision(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-6" data-testid="mcp-consent-page">
      <Card className="max-w-lg w-full">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-blue-100 dark:bg-blue-900/40 p-2">
              <Bot className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <CardTitle data-testid="consent-client-name">Authorise {clientName}</CardTitle>
              <CardDescription>
                This connector is requesting access to your BidVex account as{' '}
                <span className="font-medium text-slate-800 dark:text-slate-200">{me?.email}</span>
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <div className="text-xs uppercase text-slate-400 mb-2 flex items-center gap-1">
              <ShieldCheck className="h-3 w-3" /> Requested permissions
            </div>
            <ul className="space-y-2" data-testid="consent-scopes-list">
              {scopes.map((s) => (
                <li key={s} className="text-sm flex items-start gap-2" data-testid={`consent-scope-${s}`}>
                  <span className="font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs">
                    {s}
                  </span>
                  <span className="text-slate-600 dark:text-slate-400">
                    {SCOPE_DESCRIPTIONS[s] || 'Custom scope'}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="text-xs text-amber-800 dark:text-amber-300 bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-3 flex items-start gap-2">
            <ShieldAlert className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <div>
              Approving generates a scoped MCP access token tied to your account. All existing BidVex gates
              (subscription, trust, tax-ID, admin) still apply. You can revoke this connector any time from
              Settings → Connect Claude.
            </div>
          </div>

          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => decide(false)}
              disabled={decision !== null}
              data-testid="consent-deny-btn"
            >
              {decision === 'denying' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Deny
            </Button>
            <Button
              onClick={() => decide(true)}
              disabled={decision !== null}
              data-testid="consent-approve-btn"
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {decision === 'approving' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Approve &amp; connect
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
