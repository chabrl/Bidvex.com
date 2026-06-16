/**
 * AdminErrorLogsPage — iter306
 *
 * Admin-only page combining frontend + backend error logs with date/user/endpoint
 * filtering, expand-to-full-message rows, and message-truncation by default.
 *
 * Route: /admin/error-logs (added in App.js)
 */
import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import {
  AlertTriangle, Bug, Server, Globe, ChevronDown, ChevronUp, Loader2, RefreshCw, ArrowLeft,
} from 'lucide-react';

const API = API_BASE;

const formatTs = (ts) => {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
};

const ErrorRow = ({ row, kind, isFr }) => {
  const [expanded, setExpanded] = useState(false);
  const message = row.error_message || '';
  const truncated = message.length > 200;
  return (
    <div className="border-b border-slate-200 dark:border-slate-700 py-3" data-testid={`error-row-${kind}-${row.id}`}>
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <Badge variant="outline" className="text-[10px]">{row.error_type || (kind === 'frontend' ? 'FrontendError' : 'BackendError')}</Badge>
            {kind === 'backend' && row.method && <Badge className="text-[10px] bg-slate-700">{row.method}</Badge>}
            <span className="text-xs text-slate-500">{formatTs(row.timestamp)}</span>
            {row.user_id && <span className="text-xs text-slate-500" title={row.user_id}>👤 {String(row.user_id).slice(0, 8)}…</span>}
          </div>
          <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 font-mono break-words">
            {expanded ? message : (message.length > 200 ? message.slice(0, 200) + '…' : message)}
          </p>
          {kind === 'backend' && row.endpoint && (
            <p className="text-[11px] text-slate-500 mt-1 truncate">{isFr ? 'Endpoint :' : 'Endpoint:'} <code>{row.endpoint}</code></p>
          )}
          {kind === 'frontend' && row.url && (
            <p className="text-[11px] text-slate-500 mt-1 truncate">URL: <code>{row.url}</code></p>
          )}
          {expanded && row.stack_trace && (
            <pre className="mt-2 text-[10px] bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-auto max-h-48">{row.stack_trace}</pre>
          )}
          {expanded && row.component_stack && (
            <pre className="mt-2 text-[10px] bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-auto max-h-48">{row.component_stack}</pre>
          )}
        </div>
        {(truncated || row.stack_trace || row.component_stack) && (
          <Button variant="ghost" size="sm" onClick={() => setExpanded((v) => !v)} className="flex-shrink-0">
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? (isFr ? 'Replier' : 'Collapse') : (isFr ? 'Détails' : 'Details')}
          </Button>
        )}
      </div>
    </div>
  );
};

const AdminErrorLogsPage = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const L = (en, frTxt) => (fr ? frTxt : en);

  const [active, setActive] = useState('frontend');
  const [days, setDays] = useState(7);
  const [userFilter, setUserFilter] = useState('');
  const [endpointFilter, setEndpointFilter] = useState('');
  const [fe, setFe] = useState({ items: [], total: 0 });
  const [be, setBe] = useState({ items: [], total: 0 });
  const [loadingFe, setLoadingFe] = useState(false);
  const [loadingBe, setLoadingBe] = useState(false);

  const fetchFrontend = useCallback(async () => {
    setLoadingFe(true);
    try {
      const token = localStorage.getItem('token');
      const params = { days, limit: 100 };
      if (userFilter) params.user_id = userFilter;
      const r = await axios.get(`${API}/admin/errors/frontend`, {
        headers: { Authorization: `Bearer ${token}` },
        params,
      });
      setFe(r.data);
    } catch {
      setFe({ items: [], total: 0 });
    } finally {
      setLoadingFe(false);
    }
  }, [days, userFilter]);

  const fetchBackend = useCallback(async () => {
    setLoadingBe(true);
    try {
      const token = localStorage.getItem('token');
      const params = { days, limit: 100 };
      if (endpointFilter) params.endpoint = endpointFilter;
      const r = await axios.get(`${API}/admin/errors/backend`, {
        headers: { Authorization: `Bearer ${token}` },
        params,
      });
      setBe(r.data);
    } catch {
      setBe({ items: [], total: 0 });
    } finally {
      setLoadingBe(false);
    }
  }, [days, endpointFilter]);

  useEffect(() => { fetchFrontend(); }, [fetchFrontend]); // eslint-disable-line
  useEffect(() => { fetchBackend(); }, [fetchBackend]); // eslint-disable-line

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="admin-error-logs-page">
      <div className="max-w-5xl mx-auto px-4 py-6 sm:py-8">
        <button onClick={() => navigate('/admin')} className="text-sm text-slate-600 hover:text-slate-900 mb-3 inline-flex items-center" data-testid="back-to-admin-btn">
          <ArrowLeft className="h-4 w-4 mr-1" /> {L('Back to Admin', "Retour à l'admin")}
        </button>

        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-5">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2">
              <Bug className="h-7 w-7 text-rose-600" />
              {L('Error Logs', "Journaux d'erreurs")}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              {L(
                'Frontend and backend unhandled errors captured automatically.',
                'Erreurs non gérées du frontend et du backend capturées automatiquement.',
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <label className="text-xs text-slate-500">{L('Days', 'Jours')}:</label>
            <Input type="number" min={1} max={90} value={days} onChange={(e) => setDays(parseInt(e.target.value, 10) || 7)} className="w-20" data-testid="error-logs-days-input" />
            <Button size="sm" variant="outline" onClick={() => { fetchFrontend(); fetchBackend(); }} data-testid="error-logs-refresh-btn">
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> {L('Refresh', 'Actualiser')}
            </Button>
          </div>
        </div>

        <Tabs value={active} onValueChange={setActive}>
          <TabsList>
            <TabsTrigger value="frontend" data-testid="tab-error-logs-frontend">
              <Globe className="h-4 w-4 mr-1" /> {L('Frontend', 'Frontend')} ({fe.total})
            </TabsTrigger>
            <TabsTrigger value="backend" data-testid="tab-error-logs-backend">
              <Server className="h-4 w-4 mr-1" /> {L('Backend', 'Backend')} ({be.total})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="frontend">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  {L('Frontend Errors', 'Erreurs du frontend')}
                  {loadingFe && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                </CardTitle>
                <div className="flex gap-2 mt-2">
                  <Input placeholder={L('Filter by user ID', 'Filtrer par ID utilisateur')} value={userFilter} onChange={(e) => setUserFilter(e.target.value)} className="text-sm" data-testid="error-logs-user-filter" />
                </div>
              </CardHeader>
              <CardContent>
                {fe.items.length === 0 ? (
                  <div className="text-center py-10 text-sm text-slate-500" data-testid="error-logs-frontend-empty">
                    <AlertTriangle className="h-10 w-10 mx-auto text-slate-300 mb-2" />
                    {L('No frontend errors in this range.', 'Aucune erreur frontend dans cette période.')}
                  </div>
                ) : (
                  <div data-testid="error-logs-frontend-list">
                    {fe.items.map((row) => (
                      <ErrorRow key={row.id} row={row} kind="frontend" isFr={fr} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="backend">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  {L('Backend Errors', 'Erreurs du backend')}
                  {loadingBe && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                </CardTitle>
                <div className="flex gap-2 mt-2">
                  <Input placeholder={L('Filter by endpoint (regex)', 'Filtrer par endpoint (regex)')} value={endpointFilter} onChange={(e) => setEndpointFilter(e.target.value)} className="text-sm" data-testid="error-logs-endpoint-filter" />
                </div>
              </CardHeader>
              <CardContent>
                {be.items.length === 0 ? (
                  <div className="text-center py-10 text-sm text-slate-500" data-testid="error-logs-backend-empty">
                    <AlertTriangle className="h-10 w-10 mx-auto text-slate-300 mb-2" />
                    {L('No backend errors in this range.', 'Aucune erreur backend dans cette période.')}
                  </div>
                ) : (
                  <div data-testid="error-logs-backend-list">
                    {be.items.map((row) => (
                      <ErrorRow key={row.id} row={row} kind="backend" isFr={fr} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminErrorLogsPage;
