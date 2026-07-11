import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { FileText, Download, ShieldAlert, Clock, User as UserIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const AdminLogs = ({ searchQuery = '' }) => {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [subTab, setSubTab] = useState('actions');

  // Impersonation history state
  const [impSessions, setImpSessions] = useState([]);
  const [impLoading, setImpLoading] = useState(false);
  const [impFilter, setImpFilter] = useState({ admin_id: '', target_user_id: '', start_date: '', end_date: '' });
  const [expandedSession, setExpandedSession] = useState(null);

  useEffect(() => {
    fetchLogs();
  }, [filter]);

  // Filter action logs based on search query from parent
  const filteredLogs = searchQuery
    ? logs.filter(log => {
        const detailsStr = typeof log.details === 'object'
          ? JSON.stringify(log.details)
          : (log.details || '');
        return log.admin_email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          log.action?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          log.target_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          detailsStr.toLowerCase().includes(searchQuery.toLowerCase());
      })
    : logs;

  const fetchLogs = async () => {
    try {
      const endpoint = filter ? `/admin/logs?action_type=${filter}` : '/admin/logs';
      const response = await axios.get(`${API}${endpoint}`);
      const d = response.data;
      setLogs(Array.isArray(d) ? d : d.logs || []);
    } catch (error) {
      toast.error('Failed to load logs');
    } finally {
      setLoading(false);
    }
  };

  const fetchImpersonationHistory = useCallback(async () => {
    setImpLoading(true);
    try {
      const params = {};
      if (impFilter.admin_id.trim())        params.admin_id       = impFilter.admin_id.trim();
      if (impFilter.target_user_id.trim())  params.target_user_id = impFilter.target_user_id.trim();
      if (impFilter.start_date)             params.start_date     = new Date(impFilter.start_date).toISOString();
      if (impFilter.end_date)               params.end_date       = new Date(impFilter.end_date).toISOString();
      const response = await axios.get(`${API}/admin/impersonation-history`, { params });
      setImpSessions(response.data?.sessions || []);
    } catch (error) {
      toast.error('Failed to load impersonation history');
    } finally {
      setImpLoading(false);
    }
  }, [impFilter]);

  useEffect(() => {
    if (subTab === 'impersonation') fetchImpersonationHistory();
  }, [subTab, fetchImpersonationHistory]);

  const exportLogs = () => {
    const csv = [
      ['Date', 'Admin', 'Action', 'Target Type', 'Target ID', 'Details'],
      ...logs.map(log => [
        log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A',
        log.admin_email,
        log.action,
        log.target_type,
        log.target_id,
        typeof log.details === 'object' ? JSON.stringify(log.details) : (log.details || '')
      ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `admin-logs-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    toast.success('Logs exported');
  };

  const exportImpersonationCsv = () => {
    const csv = [
      ['Started', 'Expires', 'Duration (min)', 'Admin Email', 'Target Email', 'Actions Count'],
      ...impSessions.map(s => [
        s.started_at ? new Date(s.started_at).toLocaleString() : 'N/A',
        s.expires_at ? new Date(s.expires_at).toLocaleString() : 'N/A',
        s.duration_minutes ?? '',
        s.admin_email || s.admin_id,
        s.target_email || s.target_user_id,
        s.actions_count ?? 0,
      ])
    ].map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `impersonation-history-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    toast.success('Impersonation history exported');
  };

  if (loading) {
    return <div className="flex justify-center py-8" data-testid="admin-logs-loading">
      <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
    </div>;
  }

  return (
    <div className="space-y-6" data-testid="admin-logs-page">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><FileText className="h-6 w-6" />Admin Action Logs</h2>
          <p className="text-muted-foreground">Audit trail of all admin actions</p>
        </div>
      </div>

      <Tabs value={subTab} onValueChange={setSubTab} data-testid="admin-logs-tabs">
        <TabsList>
          <TabsTrigger value="actions" data-testid="admin-logs-tab-actions">
            <FileText className="h-4 w-4 mr-1" />Action History
          </TabsTrigger>
          <TabsTrigger value="impersonation" data-testid="admin-logs-tab-impersonation">
            <ShieldAlert className="h-4 w-4 mr-1" />Impersonation History
          </TabsTrigger>
        </TabsList>

        {/* ── Action History ── */}
        <TabsContent value="actions" className="space-y-4">
          <div className="flex justify-between items-center">
            <div className="flex gap-2 flex-wrap">
              <Button variant={!filter ? 'default' : 'outline'} onClick={() => setFilter('')} className={!filter ? 'gradient-button text-white border-0' : ''} data-testid="filter-all-actions">All Actions</Button>
              <Button variant={filter === 'user_update' ? 'default' : 'outline'} onClick={() => setFilter('user_update')} data-testid="filter-user-update">{t("admin.userUpdates")}</Button>
              <Button variant={filter === 'listing_moderate' ? 'default' : 'outline'} onClick={() => setFilter('listing_moderate')} data-testid="filter-moderate">{t("admin.moderation")}</Button>
              <Button variant={filter === 'promotion_create' ? 'default' : 'outline'} onClick={() => setFilter('promotion_create')} data-testid="filter-promotions">{t("admin.promotions")}</Button>
            </div>
            <Button onClick={exportLogs} variant="outline" data-testid="export-logs-btn"><Download className="h-4 w-4 mr-2" />Export Logs</Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Action History ({filteredLogs.length})</span>
                {searchQuery && (
                  <Badge variant="secondary" className="font-normal">
                    Showing results for &quot;{searchQuery}&quot;
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {filteredLogs.length > 0 ? (
                <div className="space-y-2">
                  {filteredLogs.map(log => (
                    <div key={log.id} className="flex justify-between items-start p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge>{log.action}</Badge>
                          <span className="text-xs text-muted-foreground">{log.admin_email}</span>
                        </div>
                        <p className="text-sm text-muted-foreground">{log.target_type}: {log.target_id}</p>
                        {log.details && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {typeof log.details === 'object'
                              ? JSON.stringify(log.details, null, 2)
                              : log.details}
                          </p>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">{log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">
                  {searchQuery ? `No logs matching "${searchQuery}"` : 'No logs yet'}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Impersonation History ── */}
        <TabsContent value="impersonation" className="space-y-4" data-testid="impersonation-history-panel">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-amber-600" />Impersonation Sessions ({impSessions.length})</span>
                <Button onClick={exportImpersonationCsv} variant="outline" size="sm" data-testid="export-impersonation-csv"><Download className="h-4 w-4 mr-2" />Export CSV</Button>
              </CardTitle>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mt-4">
                <Input placeholder="Filter by admin id" value={impFilter.admin_id}
                  onChange={(e) => setImpFilter({ ...impFilter, admin_id: e.target.value })}
                  data-testid="imp-filter-admin-id" />
                <Input placeholder="Filter by target user id" value={impFilter.target_user_id}
                  onChange={(e) => setImpFilter({ ...impFilter, target_user_id: e.target.value })}
                  data-testid="imp-filter-target-id" />
                <Input type="datetime-local" value={impFilter.start_date}
                  onChange={(e) => setImpFilter({ ...impFilter, start_date: e.target.value })}
                  data-testid="imp-filter-start" />
                <Input type="datetime-local" value={impFilter.end_date}
                  onChange={(e) => setImpFilter({ ...impFilter, end_date: e.target.value })}
                  data-testid="imp-filter-end" />
                <Button onClick={fetchImpersonationHistory} data-testid="imp-filter-apply">Apply filters</Button>
              </div>
            </CardHeader>
            <CardContent>
              {impLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
                </div>
              ) : impSessions.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No impersonation sessions yet.</p>
              ) : (
                <div className="space-y-3">
                  {impSessions.map((s) => (
                    <div key={s.session_id} className="border rounded-lg p-3 hover:bg-gray-50 transition-colors" data-testid={`imp-session-${s.session_id}`}>
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge className="bg-amber-100 text-amber-800 border border-amber-300">
                              <UserIcon className="h-3 w-3 mr-1" />
                              {s.admin_email || s.admin_id}
                            </Badge>
                            <span className="text-xs text-muted-foreground">→ impersonated →</span>
                            <Badge variant="outline">
                              {s.target_email || s.target_user_id}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                              {s.actions_count} action{s.actions_count === 1 ? '' : 's'}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                            <Clock className="h-3 w-3" />
                            {s.started_at ? new Date(s.started_at).toLocaleString() : 'N/A'}
                            {' — '}
                            duration: {s.duration_minutes ?? '—'} min
                          </p>
                        </div>
                        <Button size="sm" variant="ghost"
                          onClick={() => setExpandedSession(expandedSession === s.session_id ? null : s.session_id)}
                          data-testid={`imp-session-expand-${s.session_id}`}>
                          {expandedSession === s.session_id ? 'Hide actions' : 'Show actions'}
                        </Button>
                      </div>
                      {expandedSession === s.session_id && (
                        <div className="mt-3 pl-3 border-l-2 border-amber-200 space-y-2">
                          {(s.actions || []).length === 0 ? (
                            <p className="text-xs text-muted-foreground italic">No actions logged during this session.</p>
                          ) : (
                            (s.actions || []).map((a, idx) => (
                              <div key={`${s.session_id}-${idx}`} className="text-xs bg-gray-50 p-2 rounded">
                                <div className="flex items-center gap-2">
                                  <Badge variant="outline" className="text-xs">{a.action}</Badge>
                                  <span className="text-muted-foreground">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</span>
                                </div>
                                {a.target_type && (
                                  <p className="text-muted-foreground mt-1">{a.target_type}: {a.target_id}</p>
                                )}
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminLogs;
