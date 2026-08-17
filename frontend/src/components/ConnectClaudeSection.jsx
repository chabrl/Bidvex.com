/**
 * iter488 — Connect Claude (Scoped MCP Token) section.
 *
 * Renders inside `ProfileSettingsPage` under a new "Connect Claude"
 * tab. Handles the complete UX for scoped MCP tokens:
 *   - Generate a new token (label + scopes + expiration)
 *   - One-time raw-token reveal with clipboard copy + strong warning
 *   - Ready-to-copy Claude Desktop JSON config
 *   - List of active tokens (label / scopes / created / expires / last used)
 *   - Revoke button
 *
 * The raw token is NEVER stored anywhere on the client — once the user
 * navigates away from the reveal, it's gone forever (matches the
 * backend, which stores only the bcrypt hash).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../config';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Copy, Trash2, KeyRound, ShieldAlert, RefreshCw, Loader2 } from 'lucide-react';

const API = API_BASE;

const SCOPE_OPTIONS = [
  { id: 'read',       label_en: 'Read (search + listing details + bid status)',        label_fr: 'Lecture (recherche + détails + statut d\'enchère)' },
  { id: 'bid',        label_en: 'Bid (place bids on the caller\'s behalf)',            label_fr: 'Enchérir (placer des enchères pour l\'appelant)' },
  { id: 'list',       label_en: 'List (create draft auctions)',                        label_fr: 'Inscrire (créer des brouillons)' },
  { id: 'promote',    label_en: 'Promote (Meta ads + listing video stub)',             label_fr: 'Promouvoir (Meta Ads + vidéo)' },
  { id: 'analytics',  label_en: 'Analytics (inventory + performance flags)',           label_fr: 'Analytique (inventaire + performances)' },
  { id: 'matchmaker', label_en: 'B2B Matchmaker (buyer matches + campaign drafts)',    label_fr: 'Mise en relation B2B (correspondances + campagnes)' },
];

const EXPIRATION_OPTIONS = [7, 30, 90, 180, 365];

const authHeader = () => {
  const t = localStorage.getItem('token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const ConnectClaudeSection = ({ lang = 'en' }) => {
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [tokens, setTokens] = useState([]);
  const [label, setLabel] = useState('');
  const [selectedScopes, setSelectedScopes] = useState(['read']);
  const [expiresInDays, setExpiresInDays] = useState(90);
  const [newlyCreated, setNewlyCreated] = useState(null);

  const fr = lang === 'fr';

  const fetchTokens = useCallback(async () => {
    try {
      setLoading(true);
      const r = await axios.get(`${API}/mcp/tokens`, { headers: authHeader() });
      setTokens(r.data?.tokens || []);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 402) {
        setTokens([]);
      } else if (status !== 401) {
        toast.error(fr ? 'Impossible de charger les jetons MCP' : 'Failed to load MCP tokens');
      }
    } finally {
      setLoading(false);
    }
  }, [fr]);

  useEffect(() => { fetchTokens(); }, [fetchTokens]);

  const toggleScope = (id) => {
    setSelectedScopes((prev) => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]);
  };

  const handleGenerate = async (e) => {
    e?.preventDefault?.();
    const trimmed = label.trim();
    if (!trimmed) {
      toast.error(fr ? 'Ajoutez une étiquette pour ce jeton' : 'Please add a label for this token');
      return;
    }
    if (!selectedScopes.length) {
      toast.error(fr ? 'Sélectionnez au moins une portée' : 'Select at least one scope');
      return;
    }
    setCreating(true);
    try {
      const r = await axios.post(
        `${API}/mcp/token`,
        { label: trimmed, scopes: selectedScopes, expires_in_days: expiresInDays },
        { headers: { ...authHeader(), 'Content-Type': 'application/json' } },
      );
      setNewlyCreated(r.data);
      setLabel('');
      setSelectedScopes(['read']);
      setExpiresInDays(90);
      await fetchTokens();
      toast.success(fr ? 'Jeton MCP créé — copiez-le maintenant' : 'MCP token created — copy it now');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object' ? (fr ? detail?.message_fr : detail?.message_en) : null)
        || (fr ? 'Échec de la création du jeton' : 'Failed to create MCP token');
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (tokenId) => {
    if (!window.confirm(fr ? 'Révoquer ce jeton ? Cette action est immédiate.' : 'Revoke this token? This is immediate.')) return;
    try {
      await axios.delete(`${API}/mcp/token/${tokenId}`, { headers: authHeader() });
      toast.success(fr ? 'Jeton révoqué' : 'Token revoked');
      await fetchTokens();
    } catch (err) {
      toast.error(fr ? 'Échec de la révocation' : 'Failed to revoke token');
    }
  };

  const copy = (text, tip) => {
    if (!navigator.clipboard) {
      toast.error(fr ? 'Presse-papiers indisponible' : 'Clipboard unavailable');
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => toast.success(tip || (fr ? 'Copié' : 'Copied')),
      () => toast.error(fr ? 'Échec de la copie' : 'Copy failed'),
    );
  };

  const bridgeConfig = useMemo(() => {
    if (!newlyCreated?.token) return null;
    const origin = window?.location?.origin || 'https://bidvex.com';
    return {
      mcpServers: {
        bidvex: {
          command: 'python',
          args: ['/absolute/path/to/backend/mcp_bridge.py'],
          env: {
            BIDVEX_MCP_URL: origin,
            BIDVEX_MCP_JWT: newlyCreated.token,
          },
        },
      },
    };
  }, [newlyCreated]);

  return (
    <div className="space-y-6" data-testid="connect-claude-section">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-blue-600" />
            <CardTitle>{fr ? 'Se connecter à Claude Desktop' : 'Connect Claude Desktop'}</CardTitle>
          </div>
          <CardDescription>
            {fr
              ? 'Générez un jeton MCP à portée limitée pour connecter Claude Desktop à votre compte BidVex sans exposer votre jeton de session.'
              : 'Generate a scoped MCP token so Claude Desktop can connect to your BidVex account without exposing your session JWT.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="mcp-token-label">{fr ? 'Étiquette' : 'Label'}</Label>
            <Input
              id="mcp-token-label"
              data-testid="mcp-token-label-input"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={fr ? 'ex. Ordinateur portable de travail' : 'e.g. Work laptop'}
              maxLength={64}
            />
          </div>

          <div className="space-y-2">
            <Label>{fr ? 'Portées' : 'Scopes'}</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {SCOPE_OPTIONS.map((s) => (
                <label key={s.id}
                  className={`flex items-start gap-2 p-2 rounded-lg border cursor-pointer ${selectedScopes.includes(s.id) ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' : 'border-slate-200 dark:border-slate-700'}`}
                  data-testid={`mcp-scope-option-${s.id}`}
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={selectedScopes.includes(s.id)}
                    onChange={() => toggleScope(s.id)}
                    data-testid={`mcp-scope-checkbox-${s.id}`}
                  />
                  <div className="text-sm">
                    <div className="font-medium text-slate-800 dark:text-slate-200">{s.id}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">{fr ? s.label_fr : s.label_en}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>{fr ? 'Expiration' : 'Expiration'}</Label>
            <div className="flex gap-2 flex-wrap">
              {EXPIRATION_OPTIONS.map((d) => (
                <Button
                  key={d}
                  type="button"
                  variant={expiresInDays === d ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setExpiresInDays(d)}
                  data-testid={`mcp-expiration-${d}`}
                >
                  {d} {fr ? 'jours' : 'days'}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <Button
              onClick={handleGenerate}
              disabled={creating}
              data-testid="mcp-token-generate-btn"
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {creating
                ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" />{fr ? 'Création...' : 'Creating...'}</>)
                : (fr ? 'Générer un jeton MCP' : 'Generate MCP Token')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {newlyCreated?.token && (
        <Card className="border-amber-400 bg-amber-50/50 dark:bg-amber-950/20" data-testid="mcp-one-time-token">
          <CardHeader>
            <div className="flex items-center gap-2 text-amber-800 dark:text-amber-300">
              <ShieldAlert className="h-5 w-5" />
              <CardTitle>{fr ? 'Jeton MCP — affiché une seule fois' : 'MCP Token — shown once'}</CardTitle>
            </div>
            <CardDescription className="text-amber-800 dark:text-amber-300">
              {fr
                ? 'Ce jeton ne sera plus jamais affiché par BidVex. Stockez-le en lieu sûr dès maintenant.'
                : 'This token will only be shown once. Store it securely. BidVex cannot display it again after you leave this screen.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              <Input
                readOnly
                value={newlyCreated.token}
                data-testid="mcp-one-time-token-value"
                className="font-mono text-xs"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => copy(newlyCreated.token, fr ? 'Jeton copié' : 'Token copied')}
                data-testid="mcp-copy-token-btn"
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>

            {bridgeConfig && (
              <div className="space-y-2">
                <Label>{fr ? 'Configuration Claude Desktop' : 'Claude Desktop configuration'}</Label>
                <div className="relative">
                  <pre
                    data-testid="mcp-claude-config"
                    className="text-xs bg-slate-900 text-slate-100 p-3 rounded-lg overflow-x-auto"
                  >
{JSON.stringify(bridgeConfig, null, 2)}
                  </pre>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="absolute top-2 right-2"
                    onClick={() => copy(JSON.stringify(bridgeConfig, null, 2), fr ? 'Configuration copiée' : 'Config copied')}
                    data-testid="mcp-copy-config-btn"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {fr
                    ? 'Remplacez /absolute/path/to/backend/mcp_bridge.py par le chemin réel du fichier sur votre machine, puis redémarrez Claude Desktop.'
                    : 'Replace /absolute/path/to/backend/mcp_bridge.py with the actual path on your machine, then restart Claude Desktop.'}
                </p>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setNewlyCreated(null)}
                data-testid="mcp-dismiss-token-btn"
              >
                {fr ? 'Fermer' : 'Dismiss'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>{fr ? 'Jetons actifs' : 'Active tokens'}</CardTitle>
            <CardDescription>
              {fr ? 'Gérez les jetons MCP émis pour votre compte.' : 'Manage MCP tokens issued for your account.'}
            </CardDescription>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={fetchTokens}
            data-testid="mcp-tokens-refresh"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            {fr ? 'Actualiser' : 'Refresh'}
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> {fr ? 'Chargement...' : 'Loading...'}
            </div>
          ) : tokens.length === 0 ? (
            <div className="text-sm text-slate-500" data-testid="mcp-tokens-empty">
              {fr ? 'Aucun jeton MCP émis pour ce compte.' : 'No MCP tokens issued for this account yet.'}
            </div>
          ) : (
            <div className="space-y-3" data-testid="mcp-tokens-list">
              {tokens.map((t) => (
                <div
                  key={t.token_id}
                  className="flex flex-col sm:flex-row sm:items-center gap-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg"
                  data-testid={`mcp-token-row-${t.token_id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm text-slate-800 dark:text-slate-200 truncate">
                      {t.label}
                      {t.status !== 'active' && (
                        <span className={`ml-2 text-[10px] uppercase px-1.5 py-0.5 rounded ${t.status === 'revoked' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'}`}>
                          {t.status}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 truncate">
                      {t.token_id} · {(t.scopes || []).join(', ')}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">
                      {fr ? 'Créé' : 'Created'}: {t.created_at?.slice(0, 10)} ·{' '}
                      {fr ? 'Expire' : 'Expires'}: {t.expires_at?.slice(0, 10)} ·{' '}
                      {fr ? 'Dernière utilisation' : 'Last used'}: {t.last_used_at ? t.last_used_at.slice(0, 10) : '—'}
                    </div>
                  </div>
                  {!t.revoked && t.status === 'active' && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handleRevoke(t.token_id)}
                      data-testid={`mcp-token-revoke-${t.token_id}`}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      {fr ? 'Révoquer' : 'Revoke'}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ConnectClaudeSection;
