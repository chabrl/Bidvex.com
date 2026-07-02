/**
 * iter335 — AdminAICoachSessions
 *
 * Admin console listing OUTBOUND contractor→client calls that were
 * silently analyzed by the BidVex AI Coach (Gemini eavesdrop). Rows
 * expand into: speaker-labelled transcript · full coaching hints log ·
 * AI summary + action items · aggregate sentiment metrics · compliance
 * flags that fired during the call.
 *
 * Backend endpoints (admin-only):
 *   GET /api/admin/ai-coach/sessions
 *   GET /api/admin/ai-coach/sessions/{call_log_id}
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  PhoneCall, Loader2, Bot, User as UserIcon, ChevronDown, ChevronUp,
  RefreshCw, Clock, MessageSquare, AlertTriangle, TrendingUp, TrendingDown,
  Sparkles, Radio, Download,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';

function fmtDuration(sec) {
  if (!sec && sec !== 0) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}
function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function TrendBadge({ trend }) {
  if (trend === 'improving') {
    return <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300"><TrendingUp className="h-3 w-3 mr-1" />Improving</Badge>;
  }
  if (trend === 'declining') {
    return <Badge className="bg-rose-100 text-rose-800 border-rose-300"><TrendingDown className="h-3 w-3 mr-1" />Declining</Badge>;
  }
  if (trend === 'stable') {
    return <Badge className="bg-slate-100 text-slate-700">Stable</Badge>;
  }
  return <span className="text-xs text-slate-400">—</span>;
}

function DetailView({ callLogId, token }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await axios.get(`${API_BASE}/admin/ai-coach/sessions/${callLogId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setDoc(r.data);
      } catch (e) {
        if (!cancelled) toast.error(`Failed to load session: ${e?.response?.data?.detail || e?.message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [callLogId, token]);

  if (loading) return <div className="p-4 flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>;
  if (!doc) return null;
  const turns = doc.transcript || [];
  const hints = doc.coaching_hints_log || [];
  const flags = doc.compliance_flags_triggered || [];

  return (
    <div className="p-4 space-y-4 bg-slate-50 border-t" data-testid={`coach-detail-${callLogId}`}>
      {/* AI summary */}
      {doc.ai_summary && (
        <div className="rounded-lg p-3 bg-indigo-50 border border-indigo-200" data-testid="coach-detail-summary">
          <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-indigo-800 font-bold mb-1">
            <Sparkles className="h-3 w-3" /> AI Summary
          </div>
          <p className="text-sm text-slate-800">{doc.ai_summary}</p>
        </div>
      )}

      {/* Metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
        <div className="rounded p-2 bg-white border">
          <div className="text-slate-500">Avg sentiment</div>
          <div className="font-bold text-sm">
            {typeof doc.avg_client_sentiment === 'number' ? doc.avg_client_sentiment.toFixed(2) : '—'}
          </div>
        </div>
        <div className="rounded p-2 bg-white border">
          <div className="text-slate-500">Trend</div>
          <div className="font-bold text-sm"><TrendBadge trend={doc.sentiment_trend} /></div>
        </div>
        <div className="rounded p-2 bg-white border">
          <div className="text-slate-500">Peak positive</div>
          <div className="font-bold text-sm">{doc.peak_positive_moment_seconds ? `${doc.peak_positive_moment_seconds}s` : '—'}</div>
        </div>
        <div className="rounded p-2 bg-white border">
          <div className="text-slate-500">Peak negative</div>
          <div className="font-bold text-sm">{doc.peak_negative_moment_seconds ? `${doc.peak_negative_moment_seconds}s` : '—'}</div>
        </div>
      </div>

      {/* Compliance flags */}
      {flags.length > 0 && (
        <div className="rounded-lg p-3 bg-amber-50 border-2 border-amber-400" data-testid="coach-detail-flags">
          <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-amber-900 font-bold mb-1">
            <AlertTriangle className="h-3 w-3" /> Compliance flags triggered
          </div>
          <div className="flex flex-wrap gap-1">
            {flags.map((f) => (<Badge key={f} className="bg-amber-200 text-amber-900 border-amber-400">{f}</Badge>))}
          </div>
        </div>
      )}

      {/* Transcript */}
      <div>
        <h4 className="font-semibold text-sm mb-2 flex items-center gap-1"><MessageSquare className="h-4 w-4" /> Transcript</h4>
        {turns.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No transcript persisted.</p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {turns.map((t, i) => (
              <div key={i} className={`flex gap-2 ${t.speaker === 'contractor' ? 'justify-end' : 'justify-start'}`}>
                {t.speaker !== 'contractor' && (
                  <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                    <UserIcon className="h-3 w-3 text-slate-600" />
                  </div>
                )}
                <div className={`max-w-[75%] rounded-xl px-3 py-2 text-sm ${
                  t.speaker === 'contractor' ? 'bg-indigo-600 text-white' : 'bg-white border border-slate-200'
                }`}>
                  <div className="text-[10px] opacity-75 mb-0.5 flex items-center justify-between gap-2">
                    <span>{t.speaker}</span>
                    {typeof t.timestamp_seconds === 'number' && <span className="font-mono">{t.timestamp_seconds}s</span>}
                    {typeof t.sentiment_at_moment === 'number' && (
                      <span className="font-mono">sent={t.sentiment_at_moment.toFixed(2)}</span>
                    )}
                  </div>
                  <div className="whitespace-pre-wrap text-sm">{t.text}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Coaching hints log */}
      <div>
        <h4 className="font-semibold text-sm mb-2 flex items-center gap-1"><Bot className="h-4 w-4" /> Coaching hints ({hints.length})</h4>
        {hints.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No hints logged.</p>
        ) : (
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {hints.map((h, i) => (
              <div key={i} className="text-xs px-2 py-1 bg-white border rounded flex items-center gap-2">
                <span className="font-mono text-slate-500">{h.t}s</span>
                <Badge variant="outline" className="text-[10px]">{h.sentiment}</Badge>
                {h.tone_alert && <Badge className="bg-cyan-100 text-cyan-800 text-[10px]">{h.tone_alert}</Badge>}
                <span className="text-slate-700 truncate flex-1">{h.coaching_hint}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminAICoachSessions() {
  const { token } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [filter, setFilter] = useState({ contractor: '', trend: '', lang: '', complianceOnly: false });

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/ai-coach/sessions?limit=200`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSessions(r.data?.sessions || []);
    } catch (e) {
      toast.error(`Failed to load coach sessions: ${e?.response?.data?.detail || e?.message}`);
    } finally { setLoading(false); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const filtered = sessions.filter((s) => {
    if (filter.contractor && !(s.contractor_id || '').includes(filter.contractor)) return false;
    if (filter.trend && s.sentiment_trend !== filter.trend) return false;
    if (filter.lang && s.language_detected !== filter.lang) return false;
    if (filter.complianceOnly && (!s.compliance_flags_triggered || s.compliance_flags_triggered.length === 0)) return false;
    return true;
  });

  const exportCsv = () => {
    const rows = [
      ['call_log_id', 'contractor_id', 'client_phone_masked', 'call_started_at', 'duration_seconds', 'language_detected', 'sentiment_trend', 'avg_client_sentiment', 'ai_session_status', 'compliance_flags'],
      ...filtered.map((s) => [
        s.call_log_id, s.contractor_id, s.client_phone_masked, s.call_started_at, s.duration_seconds,
        s.language_detected, s.sentiment_trend, s.avg_client_sentiment, s.ai_session_status,
        (s.compliance_flags_triggered || []).join('|'),
      ]),
    ];
    const csv = rows.map((r) => r.map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bidvex-ai-coach-sessions-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4" data-testid="admin-ai-coach-sessions">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Bot className="h-6 w-6 text-indigo-600" />
            AI Coach Sessions — Outbound (Silent)
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Silent Gemini analysis of contractor→client calls. Phone numbers masked. No audio storage.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={exportCsv} data-testid="coach-export-csv-btn">
            <Download className="h-4 w-4 mr-1" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="coach-refresh-btn">
            {loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-3 flex flex-wrap items-center gap-2">
          <Input
            placeholder="Contractor ID contains…"
            value={filter.contractor}
            onChange={(e) => setFilter({ ...filter, contractor: e.target.value })}
            className="max-w-xs"
            data-testid="coach-filter-contractor"
          />
          <select
            value={filter.trend}
            onChange={(e) => setFilter({ ...filter, trend: e.target.value })}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            data-testid="coach-filter-trend"
          >
            <option value="">Any trend</option>
            <option value="improving">Improving</option>
            <option value="stable">Stable</option>
            <option value="declining">Declining</option>
          </select>
          <select
            value={filter.lang}
            onChange={(e) => setFilter({ ...filter, lang: e.target.value })}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            data-testid="coach-filter-lang"
          >
            <option value="">Any lang</option>
            <option value="en">EN</option>
            <option value="fr">FR</option>
            <option value="mixed">Mixed</option>
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={filter.complianceOnly}
              onChange={(e) => setFilter({ ...filter, complianceOnly: e.target.checked })}
              data-testid="coach-filter-compliance"
            />
            Compliance flagged only
          </label>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-16"><Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading…</div>
      ) : filtered.length === 0 ? (
        <Card data-testid="coach-empty">
          <CardContent className="p-8 text-center text-slate-500">
            <MessageSquare className="w-10 h-10 mx-auto mb-3 text-slate-400" />
            <p>No AI Coach sessions yet — sessions are logged when contractors place calls via the dialer.</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="coach-table">
                <thead className="bg-slate-50">
                  <tr className="text-xs text-slate-500 text-left border-b">
                    <th className="px-4 py-3">Call log</th>
                    <th className="px-4 py-3">Contractor</th>
                    <th className="px-4 py-3">Client phone</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Lang</th>
                    <th className="px-4 py-3">Trend</th>
                    <th className="px-4 py-3">Compliance</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s) => {
                    const isOpen = expanded === s.call_log_id;
                    const flags = s.compliance_flags_triggered || [];
                    return (
                      <React.Fragment key={s.call_log_id}>
                        <tr className="border-b last:border-b-0 hover:bg-slate-50" data-testid={`coach-row-${s.call_log_id}`}>
                          <td className="px-4 py-3 font-mono text-xs text-slate-700">{(s.call_log_id || '').slice(0, 12)}…</td>
                          <td className="px-4 py-3 font-mono text-xs">{(s.contractor_id || '').slice(0, 10)}…</td>
                          <td className="px-4 py-3 font-mono text-xs">{s.client_phone_masked || '—'}</td>
                          <td className="px-4 py-3 text-xs">{fmtDate(s.call_started_at)}</td>
                          <td className="px-4 py-3 text-xs flex items-center gap-1"><Clock className="h-3 w-3" /> {fmtDuration(s.duration_seconds)}</td>
                          <td className="px-4 py-3"><Badge variant="outline">{(s.language_detected || '?').toUpperCase()}</Badge></td>
                          <td className="px-4 py-3"><TrendBadge trend={s.sentiment_trend} /></td>
                          <td className="px-4 py-3">
                            {flags.length > 0
                              ? <Badge className="bg-amber-100 text-amber-800 border-amber-300"><AlertTriangle className="h-3 w-3 mr-1" />{flags.length}</Badge>
                              : <span className="text-xs text-slate-400">—</span>}
                          </td>
                          <td className="px-4 py-3">
                            <Badge className={
                              s.ai_session_status === 'completed' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                              s.ai_session_status === 'in_progress' ? 'bg-indigo-100 text-indigo-800' :
                              'bg-slate-200 text-slate-700'
                            }>
                              {s.ai_session_status || 'unknown'}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <Button size="sm" variant="outline" onClick={() => setExpanded(isOpen ? null : s.call_log_id)} data-testid={`coach-toggle-${s.call_log_id}`}>
                              {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            </Button>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr>
                            <td colSpan={10} className="p-0">
                              <DetailView callLogId={s.call_log_id} token={token} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
